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
from evo_schemas.objects import Regular3DGrid_V1_2_0, Tensor3DGrid_V1_2_0, UnstructuredTetGrid_V1_2_0

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.vtk.importer import VTKImportError, convert_vtk

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

    file_name = this_dir / "data" / "not_file.vtk"
    with pytest.raises(VTKImportError):
        convert_vtk(str(file_name), evo_workspace_metadata=workspace_metadata)


@pytest.mark.parametrize("test_file, n_messages", [("unsupported.vtp", 1), ("all_unsupported.vtm", 2)])
def test_unsupported(caplog: pytest.LogCaptureFixture, test_file: str, n_messages: int) -> None:
    workspace_metadata = EvoWorkspaceMetadata()

    file_name = this_dir / "data" / test_file
    result = convert_vtk(str(file_name), evo_workspace_metadata=workspace_metadata, publish_objects=False)
    assert result == []

    messages = caplog.text.splitlines()
    assert len(messages) == n_messages
    assert all(("PolyData data object are not supported." in line) for line in messages)


def test_data_with_ghosts(caplog: pytest.LogCaptureFixture) -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    file_name = this_dir / "data" / "image_data_with_ghosts.vti"
    result = convert_vtk(str(file_name), 4326, evo_workspace_metadata=workspace_metadata, publish_objects=False)
    assert len(result) == 0

    messages = caplog.text.splitlines()
    assert len(messages) == 1
    assert "Grid with ghost cells are not supported, skipping this grid" in messages[0]


def test_convert_object() -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    tags = {"First tag": "first tag value", "Second tag": "second tag value"}

    file_name = this_dir / "data" / "image_data.vti"
    result = convert_vtk(
        str(file_name), 4326, evo_workspace_metadata=workspace_metadata, tags=tags, publish_objects=False
    )
    assert len(result) == 1
    assert isinstance(result[0], Regular3DGrid_V1_2_0)

    expected_tags = {
        "Source": "image_data.vti (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "VTK",
        **tags,
    }
    assert result[0].tags == expected_tags


def test_convert_rectilinear_grid() -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    file_name = this_dir / "data" / "rectilinear_grid.vtr"
    result = convert_vtk(str(file_name), 4326, evo_workspace_metadata=workspace_metadata, publish_objects=False)
    assert len(result) == 1
    assert isinstance(result[0], Tensor3DGrid_V1_2_0)


def test_convert_unstructured_grid() -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    file_name = this_dir / "data" / "unstructured_grid.vtu"
    result = convert_vtk(str(file_name), 4326, evo_workspace_metadata=workspace_metadata, publish_objects=False)
    assert len(result) == 1
    assert isinstance(result[0], UnstructuredTetGrid_V1_2_0)


def test_convert_multiple() -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    file_name = this_dir / "data" / "collection.vtm"
    result = convert_vtk(str(file_name), 4326, evo_workspace_metadata=workspace_metadata, publish_objects=False)
    assert len(result) == 3
    assert isinstance(result[0], Regular3DGrid_V1_2_0)
    assert isinstance(result[1], Tensor3DGrid_V1_2_0)
    assert isinstance(result[2], UnstructuredTetGrid_V1_2_0)


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
    file_name = this_dir / "data" / "image_data.vti"
    result = convert_vtk(
        str(file_name),
        evo_workspace_metadata=workspace_metadata,
        coordinate_reference_system=input_crs,
        publish_objects=False,
    )
    assert len(result) == 1
    assert result[0].coordinate_reference_system == expected_crs


def test_coordinate_reference_system_conflicts_with_epsg_code() -> None:
    workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))
    file_name = this_dir / "data" / "image_data.vti"
    with pytest.raises(ValueError, match="Both epsg_code and coordinate_reference_system were provided"):
        convert_vtk(
            str(file_name),
            4326,
            evo_workspace_metadata=workspace_metadata,
            coordinate_reference_system=4326,
            publish_objects=False,
        )
