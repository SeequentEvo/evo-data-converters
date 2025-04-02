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
import resqpy.olio.xml_et as rqet
from evo_schemas.components import Crs_V1_0_1_EpsgCode as CrsEpsgCode
from evo_schemas.components import OneOfAttribute_V1_1_0 as OneOfAttribute
from evo_schemas.components import Triangles_V1_1_0 as Triangles
from evo_schemas.components import Triangles_V1_1_0_Indices as TrianglesIndices
from evo_schemas.components import Triangles_V1_1_0_Vertices as TrianglesVertices
from evo_schemas.objects import TriangleMesh_V2_0_0 as TriangleMesh
from resqpy.crs import Crs
from resqpy.model import Model
from resqpy.property import Property
from resqpy.surface import Surface

import evo.logging
from evo.data_converters.common.utils import vertices_bounding_box
from evo.data_converters.resqml.importer._attribute_converters import (
    convert_categorical_property,
    convert_continuous_property,
    convert_discrete_property,
    convert_points_property,
)
from evo.objects.utils.data import ObjectDataClient

from ._utils import get_metadata
from .conversion_options import ResqmlConversionOptions

logger = evo.logging.getLogger("data_converters.resqml")


def convert_surface(
    model: Model,
    surface: Surface,
    epsg_code: int,
    options: ResqmlConversionOptions,
    data_client: ObjectDataClient,
) -> Optional[TriangleMesh]:
    """Convert a resqpy Surface into a Evo TriangleMesh geo science object

    :param model: The resqpy model, representing the file being converted
    :param surface: The resqpy Surface object to be converted
    :param epsg_code: The EPSG code to be used if the Surface does not have one
    :param options: The conversion options
    :param data_client: ObjectDataClient used to create the Geo Science objects

    :return: an Evo TriangleMesh created from the RESQML surface.
    """
    (triangles, points) = surface.triangles_and_points()
    if triangles is None:
        logger.warning(
            f"Surface {surface.citation_title} {surface.uuid} does not have any triangles, it will be ignored"
        )
        return None
    if points is None:
        logger.warning(f"Surface {surface.citation_title} {surface.uuid} does not have any points, it will be ignored")
        return None

    #
    # Check the triangles, for any out of bound indices into the points array.
    # Currently, we just log a warning and ignore the surface
    #
    np = len(points)
    if not all([t[0] < np and t[1] < np and t[2] < np for t in triangles]):
        logger.warning(
            f"Surface {surface.citation_title} {surface.uuid} has triangles with invalid points indicies, it will be ignored"
        )
        return None

    crs = _get_crs(model, surface)
    if crs is not None:
        crs.local_to_global_array(points, global_z_inc_down=False)
    if crs is not None and crs.epsg_code is not None:
        evo_crs = CrsEpsgCode(epsg_code=int(crs.epsg_code))
    else:
        logger.warning(
            f"Surface {surface.citation_title} {surface.uuid} does not have an EPSG Code , using the default {epsg_code}"
        )
        evo_crs = CrsEpsgCode(epsg_code=epsg_code)

    (node_attributes, face_attributes, triangle_attributes) = _convert_attributes(model, surface, data_client)

    vertices = _build_vertices(points, data_client, node_attributes)
    indices = _build_indices(triangles, data_client, triangle_attributes)

    assert model.epc_file is not None  # Keep Pyright happy, can't happen as will have opened the file in the caller.
    source = f"{pathlib.Path(model.epc_file).name} (via Evo Data Converters)"
    mesh = TriangleMesh(
        name=_get_surface_name(surface),
        uuid=None,
        coordinate_reference_system=evo_crs,
        bounding_box=vertices_bounding_box(points),
        triangles=Triangles(vertices=vertices, indices=indices),
        tags={
            "Source": source,
            "Stage": "Experimental",
            "InputType": "RESQML",
        },
        extensions=get_metadata(surface),
    )
    return mesh


def _convert_attributes(
    model: Model,
    surface: Surface,
    data_client: ObjectDataClient,
) -> tuple[OneOfAttribute, OneOfAttribute, OneOfAttribute]:
    """Convert the surface properties to the corresponding Evo Geoscience objects

    :param model: The resqpy model, representing the file being converted
    :param surface: The resqpy Surface object to be converted
    :param data_client: ObjectDataClient used to create the properties

    :returns: a tuple containing a list of node, face and triangle properties
    """

    assert surface is not None
    node_properties: list[Property] = []
    face_properties: list[Property] = []
    triangle_properties: list[Property] = []
    parts = model.parts(related_uuid=surface.uuid)
    if parts is None:
        return ([], [], [])

    for p in parts:
        go = None
        property = None
        match model.type_of_part(p):
            case "obj_CategoricalProperty":
                property = _get_property(model, p)
                if property is not None:
                    go = convert_categorical_property(model, property, data_client)
            case "obj_ContinuousProperty":
                property = _get_property(model, p)
                if property is not None:
                    go = convert_continuous_property(property, data_client)
            case "obj_DiscreteProperty":
                property = _get_property(model, p)
                if property is not None:
                    go = convert_discrete_property(property, data_client)
            case "obj_PointsProperty":
                property = _get_property(model, p)
                if property is not None:
                    go = convert_points_property(property, data_client)
            case _:
                # If it's not a property, then we ignore it
                pass
        if go is not None and property is not None:
            match property.indexable_element():
                case "nodes":
                    node_properties.append(go)
                case "faces":
                    face_properties.append(go)
                case "triangles":
                    triangle_properties.append(go)
                case _:
                    logger.warning(
                        f"Property {property.citation_title} {property.uuid} is indexable by {property.indexable_element()}. It will be ignored"
                    )

    return (node_properties, face_properties, triangle_properties)


def _get_property(model: Model, part: str) -> Optional[Property]:
    """Extract a property from the model.

    :param model: The resqpy model, representing the file being converted
    :param part: The name of the part in the model which contains the property

    :return: A resqpy Property build from part.
             OR None if the property contains multiple PatchOfValue tags


       Currently, resqpy does not support properties with
       multiple "PatchOfValues" tags. So these properties are filtered out
    """
    uuid = model.uuid_for_part(part)
    property = Property(model, uuid=uuid)
    node = property.collection.node_for_part(part)
    patch_list = rqet.list_of_tag(node, "PatchOfValues")
    if len(patch_list or "") != 1:
        logger.warning(
            "Ignoring property %s %s, properties with multiple PatchOfValues are not supported" % (part, uuid)
        )
        return None
    return property


def _get_surface_name(surface: Surface) -> str:
    """
    Get the name of a Surface

    :param surface: The resqpy Surface to get the name of.

    :returns: The surface.citation_title if present otherwise "Surface-" + surface.uuid

    """
    name: Optional[str] = surface.citation_title
    if name is None:
        name = "Surface-" + str(surface.uuid)
    return name


def _get_crs(model: Model, surface: Surface) -> Optional[Crs]:
    """

    :param model: The model file containing the surface
    :param surface: The resqpy Surface object to be converted

    :return:

    Requires:
        model is not None
        grid is not None

    Ensures:

    """
    assert model is not None
    assert surface is not None

    # Does the surface have a CRS
    if surface.crs_uuid is not None:
        return Crs(model, uuid=surface.crs_uuid)

    # Is there a Root CRS
    if model.crs_uuid is not None:
        logger.warning(f"Surface {surface.citation_title} {surface.uuid} does not have a CRS, using the root CRS")
        return Crs(model, uuid=model.crs_uuid)

    # Otherwise there's no CRS so return none.
    return None


def _build_vertices(
    vertices: npt.NDArray[np.float64], data_client: ObjectDataClient, attributes: OneOfAttribute
) -> TrianglesVertices:
    """Build a TrianglesVertices object containing the grid vertices.

    :param vertices: an n x 3 array of cell vertex coordinates (x, y, z)
    :param data_client: ObjectDataClient used to create the TriangleVertices object
    :param attributes: List of attributes

    :return: An Evo TrianglesVertices object

    """
    schema = pa.schema(
        [
            ("x", pa.float64()),
            ("y", pa.float64()),
            ("z", pa.float64()),
        ]
    )
    table = pa.Table.from_arrays([vertices[:, 0], vertices[:, 1], vertices[:, 2]], schema=schema)
    go = data_client.save_table(table)
    tv = TrianglesVertices.from_dict(go)
    tv.attributes = attributes
    return tv


def _build_indices(indices: npt.NDArray[np.intp], data_client: ObjectDataClient, attributes: list) -> TrianglesIndices:
    """Build an Evo TrianglesIndices, containing the indexes for the cell vertices
    and the associated attributes

    :param indices: a n by 3 array of indexes into vertices ,specifying the 3 corner points of each triangle
    :param data_client: ObjectDataClient used to create the TrianglesIndices object
    :param attributes: List of attributes

    :return: An Evo TrianglesIndices object

    """
    schema = pa.schema(
        [
            ("n0", pa.uint64()),
            ("n1", pa.uint64()),
            ("n2", pa.uint64()),
        ]
    )
    table = pa.Table.from_arrays(
        [
            indices[:, 0],
            indices[:, 1],
            indices[:, 2],
        ],
        schema=schema,
    )
    go = data_client.save_table(table)
    ti = TrianglesIndices.from_dict(go)
    ti.attributes = attributes
    return ti
