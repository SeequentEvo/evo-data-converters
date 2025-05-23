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
import pytest
import vtk
from evo_schemas.components import BoundingBox_V1_0_1, Crs_V1_0_1_EpsgCode, Rotation_V1_1_0
from evo_schemas.objects import Tensor3DGrid_V1_2_0
from vtk.util.numpy_support import numpy_to_vtk
from vtk_test_helpers import MockDataClient, add_ghost_value

from evo.data_converters.vtk.importer.exceptions import GhostValueError
from evo.data_converters.vtk.importer.vtk_rectilinear_grid_to_evo import convert_vtk_rectilinear_grid


def _create_rectilinear_grid() -> vtk.vtkRectilinearGrid:
    vtk_data = vtk.vtkRectilinearGrid()
    vtk_data.SetDimensions(2, 3, 4)
    vtk_data.SetXCoordinates(numpy_to_vtk(np.array([2.4, 3.2]), deep=True))
    vtk_data.SetYCoordinates(numpy_to_vtk(np.array([1.2, 3.3, 5.1]), deep=True))
    vtk_data.SetZCoordinates(numpy_to_vtk(np.array([-1.3, 0.1, 4.9, 5.0]), deep=True))
    return vtk_data


def test_convert() -> None:
    vtk_data = _create_rectilinear_grid()

    point_data = numpy_to_vtk(np.linspace(0, 1, 24), deep=True)
    point_data.SetName("point_data")
    vtk_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, 6), deep=True)
    cell_data.SetName("cell_data")
    vtk_data.GetCellData().AddArray(cell_data)

    data_client = MockDataClient()
    result = convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)
    assert isinstance(result, Tensor3DGrid_V1_2_0)
    assert result.name == "Test"
    assert result.coordinate_reference_system == Crs_V1_0_1_EpsgCode(epsg_code=4326)
    assert result.origin == [2.4, 1.2, -1.3]
    assert result.grid_cells_3d.cell_sizes_x == pytest.approx([0.8])
    assert result.grid_cells_3d.cell_sizes_y == pytest.approx([2.1, 1.8])
    assert result.grid_cells_3d.cell_sizes_z == pytest.approx([1.4, 4.8, 0.1])
    assert result.bounding_box == BoundingBox_V1_0_1(min_x=2.4, min_y=1.2, min_z=-1.3, max_x=3.2, max_y=5.1, max_z=5.0)
    assert result.size == [1, 2, 3]
    assert result.rotation == Rotation_V1_1_0(dip_azimuth=0.0, dip=0.0, pitch=0.0)

    assert len(result.vertex_attributes) == 1
    assert result.vertex_attributes[0].name == "point_data"
    point_attribute_table = data_client.tables[result.vertex_attributes[0].values.data]
    numpy.testing.assert_array_equal(point_attribute_table[0].to_numpy(), np.linspace(0, 1, 24))
    assert len(result.cell_attributes) == 1
    assert result.cell_attributes[0].name == "cell_data"
    cell_attribute_table = data_client.tables[result.cell_attributes[0].values.data]
    numpy.testing.assert_array_equal(cell_attribute_table[0].to_numpy(), np.linspace(0, 1, 6))


def test_blanked_cell(caplog: pytest.LogCaptureFixture) -> None:
    vtk_data = _create_rectilinear_grid()

    point_data = numpy_to_vtk(np.linspace(0, 1, 24), deep=True)
    point_data.SetName("point_data")
    vtk_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, 6), deep=True)
    cell_data.SetName("cell_data")
    vtk_data.GetCellData().AddArray(cell_data)

    vtk_data.BlankCell(2)

    data_client = MockDataClient()
    result = convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)

    assert len(result.cell_attributes) == 1
    assert result.cell_attributes[0].name == "cell_data"
    cell_attribute_table = data_client.tables[result.cell_attributes[0].values.data]
    numpy.testing.assert_almost_equal(cell_attribute_table[0].to_numpy(), [0.0, 0.2, np.nan, 0.6, 0.8, 1.0])

    assert len(result.vertex_attributes) == 0

    assert "Blank cells are not supported with point data, skipping the point dat" in caplog.text


def test_blanked_point(caplog: pytest.LogCaptureFixture) -> None:
    vtk_data = _create_rectilinear_grid()
    vtk_data.BlankPoint(3)

    data_client = MagicMock()

    with pytest.raises(GhostValueError) as ctx:
        convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)
    assert "Grid with blank points are not supported" in str(ctx.value)


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
    vtk_data = _create_rectilinear_grid()

    add_ghost_value(vtk_data, geometry, ghost_value)

    data_client = MagicMock()
    with pytest.raises(GhostValueError) as ctx:
        convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326, data_client=data_client)
    assert warning_message in str(ctx.value)
