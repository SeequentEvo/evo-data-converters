#  Copyright © 2026 Bentley Systems, Incorporated
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
from unittest.mock import MagicMock, patch
from evo.data_converters.xyz.importer import convert_xyz
from evo.data_converters.common import EvoWorkspaceMetadata

this_dir = Path(__file__).parent

def test_convert_xyz_parser() -> None:
    xyz_file = this_dir / "data" / "ThreePointTable.xyz"
    evo_workspace_metadata = EvoWorkspaceMetadata(hub_url="http://example.com")
    tags = {"tagtest": "testvalue"}
    upload_path = "upload/path"

    with (
        patch(
            "evo.data_converters.xyz.importer.xyz_main.create_evo_object_service_and_data_client"
        ) as mock_create_client,
        patch(
            "evo.data_converters.xyz.importer.xyz_parser.save_array_to_parquet"
        ) as mock_save_parquet_file,
    ):
        mock_create_client.return_value = (MagicMock(), MagicMock())
        mock_save_parquet_file.return_value = None

        result = convert_xyz(
            filepath=str(xyz_file),
            evo_workspace_metadata=evo_workspace_metadata,
            tags=tags,
            upload_path=upload_path,
            publish_objects=False,
        )

        assert len(result) == 1
        assert result[0].coordinate_reference_system == "unspecified"
        assert result[0].bounding_box.min_x == 444001.07
        assert result[0].bounding_box.min_y == 492001.5
        assert result[0].bounding_box.min_z == 2390.96
        assert result[0].bounding_box.max_x == 447004.076
        assert result[0].bounding_box.max_y == 495057.8947
        assert result[0].bounding_box.max_z == 3682.755318

        assert result[0].locations.coordinates.length == 702355