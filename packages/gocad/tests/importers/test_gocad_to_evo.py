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

import uuid
from pathlib import Path

import pytest
from pyproj import CRS
from evo_schemas.components import Crs_V1_0_1_EpsgCode, Crs_V1_0_1_OgcWkt
from evo_schemas.objects import Regular3DGrid_V1_2_0

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.common.utils import UnsupportedRotation
from evo.data_converters.gocad.importer import GocadInvalidDataError, convert_gocad

this_dir = Path(__file__).parent


_WKT2_EXAMPLE = """\
GEOGCRS["WGS 84",
    DATUM["World Geodetic System 1984",
        ELLIPSOID["WGS 84", 6378137, 298.257223563,
            LENGTHUNIT["metre", 1]]],
    PRIMEM["Greenwich", 0,
        ANGLEUNIT["degree", 0.0174532925199433]],
    CS[ellipsoidal, 2],
        AXIS["geodetic latitude", north,
            ORDER[1],
            ANGLEUNIT["degree", 0.0174532925199433]],
        AXIS["geodetic longitude", east,
            ORDER[2],
            ANGLEUNIT["degree", 0.0174532925199433]],
    ID["EPSG", 4326]]"""


def test_failed_to_read_file() -> None:
    workspace_metadata = EvoWorkspaceMetadata()

    file_name = this_dir / "data" / "fake_file.go"
    with pytest.raises(GocadInvalidDataError):
        convert_gocad(str(file_name), 4326, evo_workspace_metadata=workspace_metadata, publish_objects=False)


@pytest.mark.parametrize("test_file, exc_message", [("non_orthogonal.vo", "skew"), ("inverted.vo", "invert")])
def test_unsupported_rotation(caplog: pytest.LogCaptureFixture, test_file: str, exc_message: str) -> None:
    workspace_metadata = EvoWorkspaceMetadata()

    file_name = this_dir / "data" / test_file
    with pytest.raises(UnsupportedRotation) as excinfo:
        convert_gocad(str(file_name), 4326, evo_workspace_metadata=workspace_metadata, publish_objects=False)

    assert str(excinfo.value) == exc_message


def test_gocad_grid_converted() -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    tags = {"First tag": "first tag value", "Second tag": "second tag value"}

    file_name = this_dir / "data" / "3D_grid_GOCAD.vo"
    result = convert_gocad(
        str(file_name), 4326, evo_workspace_metadata=workspace_metadata, tags=tags, publish_objects=False
    )
    assert len(result) == 1
    assert isinstance(result[0], Regular3DGrid_V1_2_0)

    expected_tags = {
        "Source": "3D_grid_GOCAD.vo (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "GOCAD",
        **tags,
    }
    assert result[0].tags == expected_tags
    assert result[0].name == "3D_grid_GOCAD"
    assert result[0].size == [17, 10, 3]
    assert result[0].origin == [716375.0, 6530775.0, 375.0]
    assert result[0].cell_size == [50.0, 50.0, 50.0]
    assert len(result[0].cell_attributes) == 1
    assert result[0].cell_attributes[0].name == "Data"
    assert result[0].cell_attributes[0].values.length == 510
    bbox = (
        result[0].bounding_box.min_x,
        result[0].bounding_box.max_x,
        result[0].bounding_box.min_y,
        result[0].bounding_box.max_y,
        result[0].bounding_box.min_z,
        result[0].bounding_box.max_z,
    )
    assert bbox == (716375.0, 717225.0, 6530775.0, 6531275.0, 375.0, 525.0)


@pytest.mark.parametrize(
    "input_crs, expected_crs",
    [
        (4326, Crs_V1_0_1_EpsgCode(epsg_code=4326)),
        ("EPSG:4326", Crs_V1_0_1_EpsgCode(epsg_code=4326)),
        (_WKT2_EXAMPLE, Crs_V1_0_1_OgcWkt(ogc_wkt=CRS.from_wkt(_WKT2_EXAMPLE).to_wkt("WKT2_2019"))),
        (None, "unspecified"),
    ],
)
def test_coordinate_reference_system(input_crs, expected_crs) -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    file_name = this_dir / "data" / "3D_grid_GOCAD.vo"
    result = convert_gocad(
        str(file_name),
        evo_workspace_metadata=workspace_metadata,
        coordinate_reference_system=input_crs,
        publish_objects=False,
    )
    assert len(result) == 1
    assert result[0].coordinate_reference_system == expected_crs


def test_coordinate_reference_system_conflicts_with_epsg_code() -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    file_name = this_dir / "data" / "3D_grid_GOCAD.vo"
    with pytest.raises(ValueError, match="Both epsg_code and coordinate_reference_system were provided"):
        convert_gocad(
            str(file_name),
            4326,
            evo_workspace_metadata=workspace_metadata,
            coordinate_reference_system=4326,
            publish_objects=False,
        )
