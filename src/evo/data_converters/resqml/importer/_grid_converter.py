#  Copyright © 2025 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import pathlib
from typing import Optional

import numpy as np
import numpy.typing as npt
import pyarrow as pa
from evo_schemas.components import Crs_V1_0_1_EpsgCode as CrsEpsgCode
from evo_schemas.components import Hexahedrons_V1_1_0 as Hexahedrons
from evo_schemas.components import IntegerAttribute_V1_0_1 as IntegerAttribute
from evo_schemas.components import NanCategorical_V1_0_1 as NanCategorical
from evo_schemas.components import OneOfAttribute_V1_1_0 as OneOfAttribute
from evo_schemas.elements import IntegerArray1_V1_0_1 as IntegerArray
from evo_schemas.objects import UnstructuredHexGrid_V1_1_0 as UnstructuredHexGrid
from resqpy.crs import Crs
from resqpy.grid import Grid
from resqpy.model import Model
from resqpy.property import Property

import evo.logging
from evo.data_converters.common.hexahedrons import build_indices, build_vertices
from evo.data_converters.common.utils import vertices_bounding_box
from evo.data_converters.resqml.importer._attribute_converters import (
    convert_categorical_property,
    convert_continuous_property,
    convert_discrete_property,
    convert_points_property,
)
from evo.objects.utils.data import ObjectDataClient

from ._time_series_converter import convert_time_series
from ._utils import get_metadata
from .conversion_options import ResqmlConversionOptions

logger = evo.logging.getLogger("data_converters.resqml")


def convert_grid(
    model: Model,
    grid: Grid,
    epsg_code: int,
    options: ResqmlConversionOptions,
    data_client: ObjectDataClient,
) -> UnstructuredHexGrid:
    """Convert a resqpy Grid object to an Evo UnstructuredHexGrid

    :param model: The resqpy model, representing the file being converted
    :param grid: The resqpy Grid object to be converted
    :param epsg_code: The EPSG code to be used if the Grid does not have one
    :param options: The conversion options
    :param data_client: ObjectDataClient used to create the Geo Science objects

    :return: Evo UnstructuredHexGrid created from the RESQML grid.
    """

    cell_indices = _get_cells_to_include(grid, active_cells_only=options.active_cells_only)
    locs, idxs = _make_geometry(grid, cell_indices)
    bounding_box = vertices_bounding_box(locs)

    attributes = _convert_attributes(model, grid, cell_indices, data_client)
    attributes += convert_time_series(model, grid, cell_indices, data_client)

    if not options.active_cells_only:
        attributes.append(_build_actnum(grid, data_client))
    (k, j, i) = cell_indices
    attributes.append(_build_integer_attribute("I", i, data_client))
    attributes.append(_build_integer_attribute("J", j, data_client))
    attributes.append(_build_integer_attribute("K", k, data_client))

    vertices = build_vertices(locs, data_client)
    indices = build_indices(idxs, data_client, attributes)

    source = f"{pathlib.Path(grid.model.epc_file).name} (via Evo Data Converters)"
    hex_grid = UnstructuredHexGrid(
        name=_get_grid_name(grid),
        uuid=None,
        coordinate_reference_system=_get_crs(model, grid, epsg_code),
        bounding_box=bounding_box,
        hexahedrons=Hexahedrons(vertices=vertices, indices=indices),
        tags={
            "Source": source,
            "Stage": "Experimental",
            "InputType": "RESQML",
        },
        extensions=_get_metadata(grid, options),
    )
    return hex_grid


def _convert_attributes(
    model: Model,
    grid: Grid,
    include: tuple[npt.NDArray[np.int_], npt.NDArray[np.int_], npt.NDArray[np.int_]],
    data_client: ObjectDataClient,
) -> OneOfAttribute:
    """Convert the Grid properties to the corresponding Evo Geoscience objects

    :param model: The resqpy model, representing the file being converted
    :param grid: The resqpy Grid object to be converted
    :param include: tuple of three arrays, one for each dimension k, j, i
                    containing the indices of the elements included in each dimension.
                    [k[n], j[n], i[n]] forms the index for cell[n]
    :param data_client: ObjectDataClient used to create the properties

    :returns: list of Evo properties
    """

    assert grid is not None
    properties: list[Property] = []
    pc = grid.property_collection
    if pc is None:
        return properties
    for p in pc.parts():  # pyright: ignore
        uuid = model.uuid_for_part(p)
        property = Property(model, uuid=uuid)
        if property.indexable_element() != "cells":
            logger.warning(
                "Ignoring property %s %s, as its indexed by %s which are currently not supported for grids"
                % (property.citation_title, str(property.uuid), property.indexable_element())
            )
        elif property.time_series_uuid() is not None:
            # Ignore attributes that are part of a time series, they get
            # processed separately
            logger.debug(
                "Ignoring property %s %s, as its a Time Series" % (property.citation_title, str(property.uuid))
            )
        elif property.is_points():
            go = convert_points_property(property, data_client, include)
            properties.append(go)
        elif property.is_categorical():
            go = convert_categorical_property(model, property, data_client, include)
            properties.append(go)
        elif property.is_continuous():
            go = convert_continuous_property(property, data_client, include)
            properties.append(go)
        elif _is_discrete(property):
            go = convert_discrete_property(property, data_client, include)
            properties.append(go)
        else:
            # Unexpected property type, log a warning and continue
            logger.warning(
                "Ignoring property %s %s , As this is not a known type" % (property.citation_title, str(property.uuid))
            )

    return properties


def _is_discrete(p: Property) -> bool:
    """Is the property a discrete property?

    RESQML does not provide an explicit function to do this.
    However the values should be integers, so check the underlying numpy
    array type and require that it be an integer type

    requires:
        p is not None
    ensures:
        IF    p is None
           OR p.array_ref() is None
           OR p.is_continuous
           OR p.is_points
           OR p.is_categorical
        THEN
            False
        ELSE IF p.array_ref().dtype.kind is u
             OR p.array_ref().dtype.kind is i
            True
        ELSE
            False
    """

    if p.is_continuous() or p.is_points() or p.is_categorical():
        return False

    array_ref = p.array_ref()
    if array_ref is None:
        return False
    if array_ref.dtype.kind != "i" and array_ref.dtype.kind != "u":
        return False
    return True


def _get_grid_name(grid: Grid) -> str:
    """
    Get the name of a Grid

    :param grid: The resqpy Grid to get the name of.

    :returns: The grid.citation_title if present otherwise "Grid-" + grid.uuid

    """
    name: Optional[str] = grid.citation_title
    if name is None:
        name = "Grid-" + str(grid.uuid)
    return name


def _get_crs(model: Model, grid: Grid, epsg_code: int) -> CrsEpsgCode:
    """
    Extract the EPSG code from the grid coordinate reference system
    and build an Evo CrsEpsgCode

    :param model: The model file containing the grid
    :param grid: The resqpy Grid object to be converted
    :param epsg_code: The EPSG code to be used if the Grid does not have one

    :return: an Evo CrsEpsgCode

    Requires:
        grid is not None

    Ensures:
           CrsEpsgCode(epsg_code=grid.crs.epsg_code))
        or CrsEpsgCode(epsg_code=epsg_code))

    """
    assert model is not None
    assert grid is not None

    # Determine the default EPSG code.
    # Use the Model crs_root if it's available
    # Otherwise use the passed in epsg_code
    crs_root = Crs(model, uuid=model.crs_uuid)
    if crs_root is not None and crs_root.epsg_code is not None:
        default_epsg = int(crs_root.epsg_code)
    else:
        logger.warning(f"File {model.epc_file} {grid.uuid} does not have a root CRS")
        default_epsg = epsg_code
    if grid.crs is None:
        logger.warning(f"Grid {grid.citation_title} {grid.uuid} does not have a CRS, defaulting to EPSG:{default_epsg}")
        return CrsEpsgCode(epsg_code=default_epsg)

    code = grid.crs.epsg_code
    if code is None:
        logger.warning(
            f"Grid {grid.citation_title} {grid.uuid} does not have an EPSG code, defaulting to EPSG:{default_epsg}"
        )
        return CrsEpsgCode(epsg_code=default_epsg)
    else:
        return CrsEpsgCode(epsg_code=int(code))


def _get_cells_to_include(
    grid: Grid, active_cells_only: bool
) -> tuple[npt.NDArray[np.int_], npt.NDArray[np.int_], npt.NDArray[np.int_]]:
    """
    Returns a tuple of three arrays, one for each dimension k, j, i
    containing the indices of the elements to include in each dimension.
     [k[n], j[n], i[n]] forms the index for cell[n]

    :param grid: The resqpy Grid object
    :param active_cells_only: should only active cells be converted?
           If true include only active cells
           If false and Geometry defined include only cells with geometry defined
           If false and Geometry NOT defined include all cells

    :return: (ak, aj, ai) - tuple containing arrays of indexes for the cells to be included

    Requires:
        grid is not None
        grid.inactive is not None if use_active == True

    Ensures:
        len(ak) == len(aj) == len(ai)
        for all k in ak: k >= 0 and k < grid.nk
        for all j in aj: j >= 0 and j < grid.nk
        for all i in ai: i >= 0 and i < grid.nk
        if use_active
            for all (k,j,i) in (ak, aj, ak): not grid.inactive(k,j,i)



    """
    assert grid is not None

    non_zero: tuple[npt.NDArray[np.int_], npt.NDArray[np.int_], npt.NDArray[np.int_]]
    if active_cells_only:
        assert grid.inactive is not None
        include = np.logical_not(grid.inactive)
        non_zero = include.nonzero()
        return non_zero

    # Include all the cells
    include = grid.cell_geometry_is_defined_ref()
    if include is None:
        # can assume ni, nj, nk are not None
        include = np.full((grid.nk, grid.nj, grid.ni), True)  # pyright: ignore
    # can assume array dimensions are correct
    non_zero = include.nonzero()
    return non_zero


# Corner points in RESQML are specified in a different order
# to that used within Evo, this array specifies the required
# reordering
HEX_ORDER = np.array([0, 1, 3, 2, 4, 5, 7, 6])


def _make_geometry(
    grid: Grid, include: tuple[npt.NDArray[np.int_], npt.NDArray[np.int_], npt.NDArray[np.int_]]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.intp]]:
    """
    Make a hexahedral cell geometry compatible with Evo an Hexahedron
    containing only the specified cells.

    :param grid:    RESQML grid being converted
    :param include: tuple of three arrays, one for each dimension k, j, i
                    containing the indices of the elements to include in each dimension.
                    [k[n], j[n], i[n]] forms the index for cell[n]

    :return: (vertices, cells)

    Where:
        vertices is an n by 3 array of corner point coordinates (x, y, y)
        cells  is n by 8 array of indexes into vertices,
               specifying the 8 cell vertices

    Requires:
        grid is not None

    Ensures:
        If grid.corner_points is None or include is none
            len(points) == 0 and len(cells) = 0
        for all disjoint a, b in points: a !=b
        for all disjoint c, d in cells: c != d
        for all p in points: p in local_to_global_array, global_z_inc_down False



    """
    assert grid is not None

    cp = grid.corner_points(cache_resqml_array=False)
    if cp is None:
        return ([], [])  # type: ignore

    # corner points can be very large
    # doing the reshape, then invalidating corner_points
    # and deleting the reference to it
    # reduces the overall memory usage to some extent
    reshaped = cp[include].reshape(-1, 3)
    grid.invalidate_corner_points()
    del cp  # Need to invalidate the reference to corner points to ensure it gets released

    vertices, uidx = _unique_points(reshaped)
    cell_idx = uidx.reshape(-1, 8)[:, HEX_ORDER]

    if grid.crs is not None:
        grid.crs.local_to_global_array(vertices, global_z_inc_down=False)
    return vertices, cell_idx


def _unique_points(points: npt.NDArray[np.float64]) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.intp]]:
    """
    Remove duplicates from the provided list of vertices,
    and generate an array of indices into the unique points
    Such that points[n] == unique_points[indexes[n]] for all n >=0 n < len(points)

    :param points: an n x 3 array of corner point coordinates (x, y, z)

    :return: (unique_points, indexes
    Where:
        unique_points is an n X 3 array of point coordinates (x, y, z)
        indexes       is an array of indexes into the corner_points array
                      with an entry corresponding to each point in
                      the original array

    Ensures:
        for all i in 0 to length(points): points[i] == unique_points[indexes[i]]
        length(points) == length(indexes)
        for all disjoint a, b in unique_points: a != b
        for all p in unique_points: p in points
    """
    up, idx = np.unique(points, axis=0, return_inverse=True)
    return up, idx


def _build_actnum(grid: Grid, data_client: ObjectDataClient) -> IntegerAttribute:
    """Build a list of the active cells in the Grid

    :param grid: The resqpy Grid object
    :param data_client: ObjectDataClient used to create the ACTNUM attribute

    :return: the ACTNUM attribute
    """
    assert grid.inactive is not None
    active = np.logical_not(grid.inactive)
    flattened = np.array(active).flatten(order="C")
    return _build_integer_attribute("ACTNUM", flattened, data_client)


def _build_integer_attribute(
    name: str, values: npt.NDArray[np.int32], data_client: ObjectDataClient
) -> IntegerAttribute:
    """Build an Evo IntegerAttribute

    :param name: The attributes name
    :param values: The attribute values
    :param data_client: ObjectDataClient used to create the ACTNUM attribute

    :return: An IntegerAttribute
    """
    schema = pa.schema([("data", pa.int32())])
    table = pa.Table.from_arrays([values], schema=schema)
    va = data_client.save_table(table)
    int_array = IntegerArray.from_dict(va)

    return IntegerAttribute(
        name=name,
        values=int_array,
        nan_description=NanCategorical(values=[]),
    )


def _get_metadata(grid: Grid, options: ResqmlConversionOptions) -> dict[str, dict[str, str | dict[str, str]]]:
    """Generate meta data about the source file, the grid and the conversion options"""
    metadata = get_metadata(grid)
    opts = {"active_cells_only": str(options.active_cells_only)}
    metadata["resqml"]["options"] = opts
    return metadata
