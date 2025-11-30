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

from pathlib import Path

import pytest

from evo.data_converters.common import RegularGridData
from evo.data_converters.common.utils import UnsupportedRotation
from evo.data_converters.gocad.importer import GocadInvalidDataError, get_gocad_grids

this_dir = Path(__file__).parent


def test_failed_to_read_file() -> None:
    file_name = this_dir / "data" / "fake_file.go"
    with pytest.raises(GocadInvalidDataError):
        get_gocad_grids(str(file_name))


@pytest.mark.parametrize("test_file, exc_message", [("non_orthogonal.vo", "skew"), ("inverted.vo", "invert")])
def test_unsupported_rotation(caplog: pytest.LogCaptureFixture, test_file: str, exc_message: str) -> None:
    file_name = this_dir / "data" / test_file
    with pytest.raises(UnsupportedRotation) as excinfo:
        get_gocad_grids(str(file_name))

    assert str(excinfo.value) == exc_message


def test_gocad_grid_data() -> None:
    file_name = this_dir / "data" / "3D_grid_GOCAD.vo"
    name, grid_data = get_gocad_grids(filepath=str(file_name))
    assert isinstance(grid_data, RegularGridData)

    assert name == "3D_grid_GOCAD"
    assert grid_data.size == [17, 10, 3]
    assert grid_data.origin == [716375.0, 6530775.0, 375.0]
    assert grid_data.cell_size == [50.0, 50.0, 50.0]
    assert len(grid_data.cell_attributes) == 1
    assert grid_data.cell_attributes[0]["name"] == "Data"
    assert len(grid_data.cell_attributes[0]["values"][0]) == 510
    assert grid_data.bounding_box == [716375.0, 717225.0, 6530775.0, 6531275.0, 375.0, 525.0]
    assert grid_data.vertex_attributes is None
