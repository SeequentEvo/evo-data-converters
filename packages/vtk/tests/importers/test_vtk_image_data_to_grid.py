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

from typing import Callable
from unittest.mock import MagicMock

import numpy as np
import numpy.testing
import pytest
import vtk
from evo.data_converters.common import RegularGridData
from evo_schemas.components import BoundingBox_V1_0_1, Rotation_V1_1_0
from vtk.util.numpy_support import numpy_to_vtk
from vtk_test_helpers import add_ghost_value

from evo.data_converters.vtk.importer.exceptions import GhostValueError
from evo.data_converters.vtk.importer.vtk_image_data_to_evo import get_vtk_image_data


@pytest.mark.parametrize(
    "data_object_type",
    [
        pytest.param(vtk.vtkImageData, id="vtkImageData"),
        pytest.param(vtk.vtkStructuredPoints, id="vtkStructuredPoints"),
        pytest.param(vtk.vtkUniformGrid, id="vtkUniformGrid"),
    ],
)
def test_metadata(data_object_type: Callable[[], vtk.vtkImageData]) -> None:
    vtk_data = data_object_type()
    vtk_data.SetDimensions(3, 4, 7)
    vtk_data.SetOrigin(12.0, 10.0, -8.0)
    vtk_data.SetSpacing(1.5, 2.5, 5.0)

    data_client = MagicMock()
    result = get_vtk_image_data(vtk_data)
    assert isinstance(result, RegularGridData)
    assert result.origin == [12.0, 10.0, -8.0]
    assert result.cell_size == [1.5, 2.5, 5.0]
    assert result.bounding_box == BoundingBox_V1_0_1(
        min_x=12.0, max_x=15.0, min_y=10.0, max_y=17.5, min_z=-8.0, max_z=22.0
    )
    assert result.size == [2, 3, 6]
    assert result.rotation == Rotation_V1_1_0(dip_azimuth=0.0, dip=0.0, pitch=0.0)
    assert result.cell_attributes == []
    assert result.vertex_attributes == []

    data_client.assert_not_called()


def test_rotated_and_extent() -> None:
    vtk_data = vtk.vtkImageData()
    vtk_data.SetOrigin(12.0, 10.0, -8.0)
    vtk_data.SetSpacing(1.5, 2.5, 5.0)
    vtk_data.SetExtent(2, 9, 1, 10, -1, 5)
    # 90-degree clockwise rotation around X-axis
    vtk_data.SetDirectionMatrix(1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 0.0)

    data_client = MagicMock()
    result = get_vtk_image_data(vtk_data)
    # As Geoscience Objects don't support a offset origin, the origin is shifted to the corner of the grid extent. So:
    # x origin value is shifted to 12.0 + 1.5 * 2 = 15.0
    # y origin value is shifted to 10.0 + 5.0 * -1 = 5.0  (as the grid's z-axis is pointing along the y-axis)
    # z origin value is shifted to -8.0 + -(2.5 * 1) = -10.5  (as the grid's y-axis is pointing down)
    assert result.origin == [15.0, 5.0, -10.5]
    assert result.cell_size == [1.5, 2.5, 5.0]
    assert result.bounding_box == BoundingBox_V1_0_1(
        min_x=15.0, max_x=25.5, min_y=5.0, max_y=35.0, min_z=-33.0, max_z=-10.5
    )
    assert result.size == [7, 9, 6]
    assert result.rotation == Rotation_V1_1_0(dip_azimuth=0.0, dip=90.0, pitch=0.0)

    data_client.assert_not_called()


def test_point_and_cell_data_attributes() -> None:
    vtk_data = vtk.vtkImageData()
    vtk_data.SetDimensions(3, 3, 2)

    point_data = numpy_to_vtk(np.linspace(0, 1, 18), deep=True)
    point_data.SetName("point_data")
    vtk_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, 4), deep=True)
    cell_data.SetName("cell_data")
    vtk_data.GetCellData().AddArray(cell_data)

    data_client = MagicMock()
    result = get_vtk_image_data(vtk_data)

    assert len(result.vertex_attributes) == 1
    assert result.vertex_attributes[0]["name"] == "point_data"
    point_attribute_table = result.vertex_attributes[0]["values"]
    numpy.testing.assert_array_equal(point_attribute_table[0].to_numpy(), np.linspace(0, 1, 18))
    assert len(result.cell_attributes) == 1
    assert result.cell_attributes[0]["name"] == "cell_data"
    cell_attribute_table = result.cell_attributes[0]["values"]
    numpy.testing.assert_array_equal(cell_attribute_table[0].to_numpy(), np.linspace(0, 1, 4))

    data_client.assert_not_called()


def test_blanked_cell(caplog: pytest.LogCaptureFixture) -> None:
    vtk_data = vtk.vtkImageData()
    vtk_data.SetDimensions(3, 3, 2)

    point_data = numpy_to_vtk(np.linspace(0, 1, 18), deep=True)
    point_data.SetName("point_data")
    vtk_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, 4), deep=True)
    cell_data.SetName("cell_data")
    vtk_data.GetCellData().AddArray(cell_data)

    vtk_data.BlankCell(2)

    data_client = MagicMock()
    result = get_vtk_image_data(vtk_data)
    assert isinstance(result, RegularGridData)
    mask_table = result.mask
    numpy.testing.assert_array_equal(mask_table, [True, True, False, True])

    assert len(result.cell_attributes) == 1
    assert result.cell_attributes[0]["name"] == "cell_data"
    cell_attribute_table = result.cell_attributes[0]["values"]
    numpy.testing.assert_almost_equal(cell_attribute_table[0].to_numpy(), [0.0, 0.33333333, 1.0])

    assert "Blank cells are not supported with point data, skipping the point data" in caplog.text

    data_client.assert_not_called()


def test_blanked_point(caplog: pytest.LogCaptureFixture) -> None:
    vtk_data = vtk.vtkImageData()
    vtk_data.SetDimensions(3, 3, 2)
    vtk_data.BlankPoint(3)

    data_client = MagicMock()

    with pytest.raises(GhostValueError) as ctx:
        get_vtk_image_data(vtk_data)
    assert "Grid with blank points are not supported" in str(ctx.value)

    data_client.assert_not_called()


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
    vtk_data = vtk.vtkImageData()
    vtk_data.SetDimensions(3, 3, 2)

    add_ghost_value(vtk_data, geometry, ghost_value)

    data_client = MagicMock()
    with pytest.raises(GhostValueError) as ctx:
        get_vtk_image_data(vtk_data)
    assert warning_message in str(ctx.value)

    data_client.assert_not_called()
