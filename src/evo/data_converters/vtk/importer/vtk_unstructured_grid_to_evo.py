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

import numpy as np
import pyarrow as pa
import vtk
from evo_schemas.components import (
    Hexahedrons_V1_2_0,
    Hexahedrons_V1_2_0_Indices,
    Hexahedrons_V1_2_0_Vertices,
    OneOfAttribute_V1_2_0,
    Tetrahedra_V1_2_0,
    Tetrahedra_V1_2_0_Indices,
    Tetrahedra_V1_2_0_Vertices,
    UnstructuredGridGeometry_V1_2_0,
    UnstructuredGridGeometry_V1_2_0_Cells,
    UnstructuredGridGeometry_V1_2_0_Vertices,
)
from evo_schemas.elements import IndexArray1_V1_0_1
from evo_schemas.objects import (
    UnstructuredGrid_V1_2_0,
    UnstructuredHexGrid_V1_2_0,
    UnstructuredTetGrid_V1_2_0,
)
from vtk.util.numpy_support import vtk_to_numpy

from evo.objects.utils.data import ObjectDataClient

from ._utils import check_for_ghosts, common_fields
from .exceptions import UnsupportedCellTypeError
from .vtk_attributes_to_evo import convert_attributes

_shape_mapping = {
    vtk.VTK_VERTEX: 0,
    vtk.VTK_LINE: 1,
    vtk.VTK_TRIANGLE: 2,
    vtk.VTK_QUAD: 3,
    vtk.VTK_TETRA: 4,
    vtk.VTK_HEXAHEDRON: 5,
    vtk.VTK_WEDGE: 6,
    vtk.VTK_PYRAMID: 7,
}


def _create_indices_table(unstructured_grid: vtk.vtkUnstructuredGrid, n_vertices: int) -> pa.Table:
    connectivity = vtk_to_numpy(unstructured_grid.GetCells().GetConnectivityArray())
    connectivity = connectivity.astype("uint64")
    offsets = vtk_to_numpy(unstructured_grid.GetCells().GetOffsetsArray())
    offsets = offsets[:-1]  # Last offset is the total number of indices
    indices_tables = pa.table({f"n{i}": connectivity[offsets + i] for i in range(n_vertices)})
    return indices_tables


def _create_tetrahedron_grid(
    name: str,
    epsg_code: int,
    unstructured_grid: vtk.vtkUnstructuredGrid,
    data_client: ObjectDataClient,
    vertex_attributes: OneOfAttribute_V1_2_0,
    points_table: pa.Table,
    cell_attributes: OneOfAttribute_V1_2_0,
) -> UnstructuredTetGrid_V1_2_0:
    indices_tables = _create_indices_table(unstructured_grid, 4)
    return UnstructuredTetGrid_V1_2_0(
        **common_fields(name, epsg_code, unstructured_grid),
        tetrahedra=Tetrahedra_V1_2_0(
            vertices=Tetrahedra_V1_2_0_Vertices(
                attributes=vertex_attributes,
                **data_client.save_table(points_table),
            ),
            indices=Tetrahedra_V1_2_0_Indices(
                attributes=cell_attributes,
                **data_client.save_table(indices_tables),
            ),
        ),
    )


def _create_hexahedron_grid(
    name: str,
    epsg_code: int,
    unstructured_grid: vtk.vtkUnstructuredGrid,
    data_client: ObjectDataClient,
    vertex_attributes: OneOfAttribute_V1_2_0,
    points_table: pa.Table,
    cell_attributes: OneOfAttribute_V1_2_0,
) -> UnstructuredHexGrid_V1_2_0:
    indices_tables = _create_indices_table(unstructured_grid, 8)
    return UnstructuredHexGrid_V1_2_0(
        **common_fields(name, epsg_code, unstructured_grid),
        hexahedrons=Hexahedrons_V1_2_0(
            vertices=Hexahedrons_V1_2_0_Vertices(
                attributes=vertex_attributes,
                **data_client.save_table(points_table),
            ),
            indices=Hexahedrons_V1_2_0_Indices(attributes=cell_attributes, **data_client.save_table(indices_tables)),
        ),
    )


def _create_generic_unstructured_grid(
    name: str,
    epsg_code: int,
    unstructured_grid: vtk.vtkUnstructuredGrid,
    data_client: ObjectDataClient,
    vertex_attributes: OneOfAttribute_V1_2_0,
    points_table: pa.Table,
    cell_attributes: OneOfAttribute_V1_2_0,
    vtk_shapes: np.ndarray,
) -> UnstructuredGrid_V1_2_0:
    # Convert shape numbering from VTK to Geocience Object convention
    go_shapes = np.zeros(vtk_shapes.shape, dtype="int32")
    for vtk_shape_number, go_shape_number in _shape_mapping.items():
        go_shapes[vtk_shapes == vtk_shape_number] = go_shape_number

    offsets = vtk_to_numpy(unstructured_grid.GetCells().GetOffsetsArray())
    cell_table = pa.table(
        {
            "shape": go_shapes,
            "offset": offsets[:-1].astype("uint64"),
            "n_vertices": np.diff(offsets).astype("int32"),
        }
    )

    index_array = vtk_to_numpy(unstructured_grid.GetCells().GetConnectivityArray())
    index_table = pa.table({"index": index_array.astype("uint64")})
    return UnstructuredGrid_V1_2_0(
        **common_fields(name, epsg_code, unstructured_grid),
        geometry=UnstructuredGridGeometry_V1_2_0(
            vertices=UnstructuredGridGeometry_V1_2_0_Vertices(
                attributes=vertex_attributes, **data_client.save_table(points_table)
            ),
            cells=UnstructuredGridGeometry_V1_2_0_Cells(
                attributes=cell_attributes, **data_client.save_table(cell_table)
            ),
            indices=IndexArray1_V1_0_1(**data_client.save_table(index_table)),
        ),
    )


def convert_vtk_unstructured_grid(
    name: str,
    unstructured_grid: vtk.vtkUnstructuredGrid,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> UnstructuredGrid_V1_2_0 | UnstructuredHexGrid_V1_2_0 | UnstructuredTetGrid_V1_2_0:
    # Unstructured grids don't support blank cells/points, so no mask should be returned here.
    _ = check_for_ghosts(unstructured_grid)

    vertex_data = unstructured_grid.GetPointData()
    points = vtk_to_numpy(unstructured_grid.GetPoints().GetData())
    points = points.astype("float64")
    points_table = pa.table({"x": points[:, 0], "y": points[:, 1], "z": points[:, 2]})
    vertex_attributes = convert_attributes(vertex_data, data_client)

    cell_data = unstructured_grid.GetCellData()
    vtk_shapes = vtk_to_numpy(unstructured_grid.GetCellTypesArray())
    cell_attributes = convert_attributes(cell_data, data_client)

    shape_set = set(np.unique(vtk_shapes))
    if not shape_set.issubset(_shape_mapping.keys()):
        raise UnsupportedCellTypeError("Unsupported cell types found in the unstructured grid")

    # Check whether the grid contains only hexahedron or tetrahedron cells, if so, create the specific grid type
    if len(shape_set) == 1:
        single_shape = next(iter(shape_set))
        match single_shape:
            case vtk.VTK_TETRA:
                return _create_tetrahedron_grid(
                    name, epsg_code, unstructured_grid, data_client, vertex_attributes, points_table, cell_attributes
                )
            case vtk.VTK_HEXAHEDRON:
                return _create_hexahedron_grid(
                    name, epsg_code, unstructured_grid, data_client, vertex_attributes, points_table, cell_attributes
                )

    # Otherwise, create a generic unstructured grid, which can contain multiple cell types
    return _create_generic_unstructured_grid(
        name, epsg_code, unstructured_grid, data_client, vertex_attributes, points_table, cell_attributes, vtk_shapes
    )
