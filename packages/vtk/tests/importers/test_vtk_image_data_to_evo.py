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
import pandas as pd
import pandas.testing as pdt
from evo.objects.typed import Regular3DGridData, RegularMasked3DGridData, EpsgCode, Point3, Size3d, Size3i, BoundingBox, Rotation
from vtk.util.numpy_support import numpy_to_vtk
from vtk_test_helpers import add_ghost_value

from evo.data_converters.common import crs_from_epsg_code
from evo.data_converters.vtk.importer.exceptions import GhostValueError
from evo.data_converters.vtk.importer.vtk_image_data_to_evo import convert_vtk_image_data


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

    result = convert_vtk_image_data("Test", vtk_data, epsg_code=4326)
    assert isinstance(result, Regular3DGridData)
    assert result.name == "Test"
    assert result.coordinate_reference_system == EpsgCode(4326)
    assert result.origin == Point3(12.0, 10.0, -8.0)
    assert result.cell_size == Size3d(1.5, 2.5, 5.0)
    assert result.size == Size3i(2, 3, 6)
    assert result.rotation == Rotation(dip_azimuth=0.0, dip=0.0, pitch=0.0)
    assert result.cell_data is None
    assert result.vertex_data is None


def test_rotated_and_extent() -> None:
    vtk_data = vtk.vtkImageData()
    vtk_data.SetOrigin(12.0, 10.0, -8.0)
    vtk_data.SetSpacing(1.5, 2.5, 5.0)
    vtk_data.SetExtent(2, 9, 1, 10, -1, 5)
    # 90-degree clockwise rotation around X-axis
    vtk_data.SetDirectionMatrix(1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 0.0)

    result = convert_vtk_image_data("Test", vtk_data, epsg_code=4326)
    # As Geoscience Objects don't support a offset origin, the origin is shifted to the corner of the grid extent. So:
    # x origin value is shifted to 12.0 + 1.5 * 2 = 15.0
    # y origin value is shifted to 10.0 + 5.0 * -1 = 5.0  (as the grid's z-axis is pointing along the y-axis)
    # z origin value is shifted to -8.0 + -(2.5 * 1) = -10.5  (as the grid's y-axis is pointing down)
    assert result.origin == Point3(15.0, 5.0, -10.5)
    assert result.cell_size == Size3d(1.5, 2.5, 5.0)
    assert result.size == Size3i(7, 9, 6)
    assert result.rotation == Rotation(dip_azimuth=0.0, dip=90.0, pitch=0.0)


def test_point_and_cell_data_attributes() -> None:
    vtk_data = vtk.vtkImageData()
    vtk_data.SetDimensions(3, 3, 2)

    point_data = numpy_to_vtk(np.linspace(0, 1, 18), deep=True)
    point_data.SetName("point_data")
    vtk_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, 4), deep=True)
    cell_data.SetName("cell_data")
    vtk_data.GetCellData().AddArray(cell_data)

    result = convert_vtk_image_data("Test", vtk_data, epsg_code=4326)

    pdt.assert_frame_equal(
        result.vertex_data,
        pd.DataFrame({
            "point_data": np.linspace(0, 1, 18),
        })
    )
    pdt.assert_frame_equal(
        result.cell_data,
        pd.DataFrame({
            "cell_data": np.linspace(0, 1, 4),
        })
    )

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

    result = convert_vtk_image_data("Test", vtk_data, epsg_code=4326)
    assert isinstance(result, RegularMasked3DGridData)
    numpy.testing.assert_array_equal(result.mask, [True, True, False, True])
    pdt.assert_frame_equal(
        result.cell_data,
        pd.DataFrame({
            "cell_data": [0.0, 0.33333333, 1.0],
        })
    )
    assert "Blank cells are not supported with point data, skipping the point data" in caplog.text


def test_blanked_point(caplog: pytest.LogCaptureFixture) -> None:
    vtk_data = vtk.vtkImageData()
    vtk_data.SetDimensions(3, 3, 2)
    vtk_data.BlankPoint(3)

    with pytest.raises(GhostValueError) as ctx:
        convert_vtk_image_data("Test", vtk_data, epsg_code=4326)
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
    vtk_data = vtk.vtkImageData()
    vtk_data.SetDimensions(3, 3, 2)

    add_ghost_value(vtk_data, geometry, ghost_value)

    with pytest.raises(GhostValueError) as ctx:
        convert_vtk_image_data("Test", vtk_data, epsg_code=4326)
    assert warning_message in str(ctx.value)
