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
import pandas as pd
import pandas.testing as pdt
import pytest
import vtk
from evo.objects.typed import Tensor3DGridData, EpsgCode, Point3, Size3d, Size3i, BoundingBox, Rotation
from evo_schemas.components import BoundingBox_V1_0_1, Rotation_V1_1_0
from evo_schemas.objects import Tensor3DGrid_V1_2_0
from vtk.util.numpy_support import numpy_to_vtk
from vtk_test_helpers import MockDataClient, add_ghost_value

from evo.data_converters.common import crs_from_epsg_code
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

    result = convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326)
    assert isinstance(result, Tensor3DGridData)
    assert result.name == "Test"
    assert result.coordinate_reference_system == EpsgCode(4326)
    assert result.origin == Point3(2.4, 1.2, -1.3)
    numpy.testing.assert_array_almost_equal(result.cell_sizes_x, np.array([0.8]))
    numpy.testing.assert_array_almost_equal(result.cell_sizes_y, np.array([2.1, 1.8]))
    numpy.testing.assert_array_almost_equal(result.cell_sizes_z, np.array([1.4, 4.8, 0.1]))
    assert result.size == Size3i(1, 2, 3)
    assert result.rotation == Rotation(dip_azimuth=0.0, dip=0.0, pitch=0.0)

    pdt.assert_frame_equal(
        result.vertex_data,
        pd.DataFrame({
            "point_data": np.linspace(0, 1, 24),
        })
    )
    pdt.assert_frame_equal(
        result.cell_data,
        pd.DataFrame({
            "cell_data": np.linspace(0, 1, 6),
        })
    )

def test_blanked_cell(caplog: pytest.LogCaptureFixture) -> None:
    vtk_data = _create_rectilinear_grid()

    point_data = numpy_to_vtk(np.linspace(0, 1, 24), deep=True)
    point_data.SetName("point_data")
    vtk_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, 6), deep=True)
    cell_data.SetName("cell_data")
    vtk_data.GetCellData().AddArray(cell_data)

    vtk_data.BlankCell(2)

    result = convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326)

    pdt.assert_frame_equal(
        result.cell_data,
        pd.DataFrame({
            "cell_data": [0.0, 0.2, np.nan, 0.6, 0.8, 1.0],
        })
    )
    assert result.vertex_data is None

    assert "Blank cells are not supported with point data, skipping the point dat" in caplog.text


def test_blanked_point(caplog: pytest.LogCaptureFixture) -> None:
    vtk_data = _create_rectilinear_grid()
    vtk_data.BlankPoint(3)

    with pytest.raises(GhostValueError) as ctx:
        convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326)
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

    with pytest.raises(GhostValueError) as ctx:
        convert_vtk_rectilinear_grid("Test", vtk_data, epsg_code=4326)
    assert warning_message in str(ctx.value)
