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

from unittest.mock import MagicMock

import numpy as np
import numpy.testing
import pyarrow as pa
import pytest
import vtk
from evo_schemas.components import BoundingBox_V1_0_1, Crs_V1_0_1_EpsgCode
from evo_schemas.objects import (
    UnstructuredGrid_V1_2_0,
    UnstructuredHexGrid_V1_2_0,
    UnstructuredTetGrid_V1_2_0,
)
from vtk.util.numpy_support import numpy_to_vtk
from vtk_test_helpers import MockDataClient, add_ghost_value

from evo.data_converters.vtk.importer.exceptions import GhostValueError, UnsupportedCellTypeError
from evo.data_converters.vtk.importer.vtk_unstructured_grid_to_evo import convert_vtk_unstructured_grid


def _remove_unused_points(unstructured_grid: vtk.vtkUnstructuredGrid) -> vtk.vtkUnstructuredGrid:
    clean_filter = vtk.vtkRemoveUnusedPoints()
    clean_filter.SetInputData(unstructured_grid)
    clean_filter.Update()
    return clean_filter.GetOutput()


def _create_unstructured_grid(include_tetra: bool, include_hex: bool) -> vtk.vtkUnstructuredGrid:
    points = vtk.vtkPoints()
    points.InsertNextPoint(0, 0, 0)
    points.InsertNextPoint(1, 0, 0)
    points.InsertNextPoint(1, 1, 0)
    points.InsertNextPoint(0, 0, 2)

    points.InsertNextPoint(0, 1, 0)
    points.InsertNextPoint(0, 0, -1)
    points.InsertNextPoint(0, 1, -1)
    points.InsertNextPoint(1, 0, -1)
    points.InsertNextPoint(1, 1, -1)

    unstructured_grid = vtk.vtkUnstructuredGrid()
    unstructured_grid.SetPoints(points)
    if include_tetra:
        unstructured_grid.InsertNextCell(vtk.VTK_TETRA, 4, [0, 1, 2, 3])
    if include_hex:
        unstructured_grid.InsertNextCell(vtk.VTK_HEXAHEDRON, 8, [0, 1, 4, 2, 5, 6, 7, 8])

    point_data = numpy_to_vtk(np.linspace(0, 1, unstructured_grid.GetNumberOfPoints()), deep=True)
    point_data.SetName("point_data")
    unstructured_grid.GetPointData().AddArray(point_data)
    unstructured_grid = _remove_unused_points(unstructured_grid)

    cell_values = []
    if include_tetra:
        cell_values.append(2.1)
    if include_hex:
        cell_values.append(3.2)
    cell_data = numpy_to_vtk(cell_values, deep=True)
    cell_data.SetName("cell_data")
    unstructured_grid.GetCellData().AddArray(cell_data)
    return unstructured_grid


def _convert_md_table(table: pa.Table) -> np.ndarray:
    return np.column_stack([table[i].to_numpy() for i in range(len(table.columns))])


def test_convert_tetra_grid() -> None:
    vtk_data = _create_unstructured_grid(include_tetra=True, include_hex=False)

    data_client = MockDataClient()
    result = convert_vtk_unstructured_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)
    assert isinstance(result, UnstructuredTetGrid_V1_2_0)
    assert result.name == "Test"
    assert result.coordinate_reference_system == Crs_V1_0_1_EpsgCode(epsg_code=4326)
    assert result.bounding_box == BoundingBox_V1_0_1(min_x=0.0, min_y=0.0, min_z=0.0, max_x=1.0, max_y=1.0, max_z=2.0)

    points_table = data_client.tables[result.tetrahedra.vertices.data]
    points = _convert_md_table(points_table)
    numpy.testing.assert_array_equal(points, [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 2]])
    vertex_attributes = result.tetrahedra.vertices.attributes
    assert len(vertex_attributes) == 1
    assert vertex_attributes[0].name == "point_data"
    vertex_attribute_table = data_client.tables[vertex_attributes[0].values.data]
    numpy.testing.assert_array_equal(vertex_attribute_table[0].to_numpy(), [0.0, 0.125, 0.25, 0.375])

    cell_table = data_client.tables[result.tetrahedra.indices.data]
    cell_array = _convert_md_table(cell_table)
    numpy.testing.assert_array_equal(cell_array, [[0, 1, 2, 3]])
    cell_attributes = result.tetrahedra.indices.attributes
    assert len(cell_attributes) == 1
    assert cell_attributes[0].name == "cell_data"
    cell_attribute_table = data_client.tables[cell_attributes[0].values.data]
    numpy.testing.assert_array_equal(cell_attribute_table[0].to_numpy(), [2.1])


def test_convert_hex_tetra() -> None:
    vtk_data = _create_unstructured_grid(include_tetra=False, include_hex=True)

    data_client = MockDataClient()
    result = convert_vtk_unstructured_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)
    assert isinstance(result, UnstructuredHexGrid_V1_2_0)
    assert result.name == "Test"
    assert result.coordinate_reference_system == Crs_V1_0_1_EpsgCode(epsg_code=4326)
    assert result.bounding_box == BoundingBox_V1_0_1(min_x=0.0, min_y=0.0, min_z=-1.0, max_x=1.0, max_y=1.0, max_z=0.0)

    points_table = data_client.tables[result.hexahedrons.vertices.data]
    points = _convert_md_table(points_table)
    # The removal of unused points changed the order of the points slightly
    numpy.testing.assert_array_equal(
        points,
        [
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [1, 1, 0],
            [0, 0, -1],
            [0, 1, -1],
            [1, 0, -1],
            [1, 1, -1],
        ],
    )
    vertex_attributes = result.hexahedrons.vertices.attributes
    assert len(vertex_attributes) == 1
    assert vertex_attributes[0].name == "point_data"
    vertex_attribute_table = data_client.tables[vertex_attributes[0].values.data]
    numpy.testing.assert_array_equal(
        vertex_attribute_table[0].to_numpy(), [0.0, 0.125, 0.5, 0.25, 0.625, 0.75, 0.875, 1.0]
    )

    cell_table = data_client.tables[result.hexahedrons.indices.data]
    cell_array = _convert_md_table(cell_table)
    numpy.testing.assert_array_equal(cell_array, [[0, 1, 2, 3, 4, 5, 6, 7]])
    cell_attributes = result.hexahedrons.indices.attributes
    assert len(cell_attributes) == 1
    assert cell_attributes[0].name == "cell_data"
    cell_attribute_table = data_client.tables[cell_attributes[0].values.data]
    numpy.testing.assert_array_equal(cell_attribute_table[0].to_numpy(), [3.2])


def test_convert_multiple() -> None:
    vtk_data = _create_unstructured_grid(include_tetra=True, include_hex=True)

    data_client = MockDataClient()
    result = convert_vtk_unstructured_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)
    assert isinstance(result, UnstructuredGrid_V1_2_0)
    assert result.name == "Test"
    assert result.coordinate_reference_system == Crs_V1_0_1_EpsgCode(epsg_code=4326)
    assert result.bounding_box == BoundingBox_V1_0_1(min_x=0.0, min_y=0.0, min_z=-1.0, max_x=1.0, max_y=1.0, max_z=2.0)

    points_table = data_client.tables[result.geometry.vertices.data]
    points = _convert_md_table(points_table)
    numpy.testing.assert_array_equal(
        points,
        [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 0, 2],
            [0, 1, 0],
            [0, 0, -1],
            [0, 1, -1],
            [1, 0, -1],
            [1, 1, -1],
        ],
    )
    vertex_attributes = result.geometry.vertices.attributes
    assert len(vertex_attributes) == 1
    assert vertex_attributes[0].name == "point_data"
    vertex_attribute_table = data_client.tables[vertex_attributes[0].values.data]
    numpy.testing.assert_array_equal(vertex_attribute_table[0].to_numpy(), np.linspace(0, 1, 9))

    cell_table = data_client.tables[result.geometry.cells.data]
    numpy.testing.assert_array_equal(cell_table[0].to_numpy(), [4, 5])  # shape
    numpy.testing.assert_array_equal(cell_table[1].to_numpy(), [0, 4])  # offset
    numpy.testing.assert_array_equal(cell_table[2].to_numpy(), [4, 8])  # number o vertices
    cell_attributes = result.geometry.cells.attributes
    assert len(cell_attributes) == 1
    assert cell_attributes[0].name == "cell_data"
    cell_attribute_table = data_client.tables[cell_attributes[0].values.data]
    numpy.testing.assert_array_equal(cell_attribute_table[0].to_numpy(), [2.1, 3.2])

    index_table = data_client.tables[result.geometry.indices.data]
    numpy.testing.assert_array_equal(index_table[0].to_numpy(), [0, 1, 2, 3, 0, 1, 4, 2, 5, 6, 7, 8])


@pytest.mark.parametrize(
    "geometry, ghost_value, warning_message",
    [
        pytest.param(
            vtk.vtkDataSet.CELL,
            vtk.vtkDataSetAttributes.DUPLICATECELL,
            "Grid with ghost cells are not supported",
            id="cell",
        ),
        pytest.param(
            vtk.vtkDataSet.POINT,
            vtk.vtkDataSetAttributes.DUPLICATEPOINT,
            "Grid with ghost points are not supported",
            id="point",
        ),
    ],
)
def test_ghost(caplog: pytest.LogCaptureFixture, geometry: int, ghost_value: int, warning_message: str) -> None:
    vtk_data = _create_unstructured_grid(include_hex=True, include_tetra=True)

    add_ghost_value(vtk_data, geometry, ghost_value, index=0)

    data_client = MagicMock()
    with pytest.raises(GhostValueError) as ctx:
        convert_vtk_unstructured_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)
    assert warning_message in str(ctx.value)


def test_unsupported_shape() -> None:
    # Create a pentagonal that is extruded in the z direction
    points = vtk.vtkPoints()
    for z in range(2):
        points.InsertNextPoint(0, 0, z)
        points.InsertNextPoint(1, 0, z)
        points.InsertNextPoint(1, 1, z)
        points.InsertNextPoint(0.5, 2, z)
        points.InsertNextPoint(0, 1, z)

    unstructured_grid = vtk.vtkUnstructuredGrid()
    unstructured_grid.SetPoints(points)
    unstructured_grid.InsertNextCell(vtk.VTK_PENTAGONAL_PRISM, 10, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

    data_client = MagicMock()
    with pytest.raises(UnsupportedCellTypeError):
        convert_vtk_unstructured_grid("Test", unstructured_grid, epsg_code=4326, data_client=data_client)
