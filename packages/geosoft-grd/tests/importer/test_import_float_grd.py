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
from evo.data_converters.grd.importer import convert_grd
from evo.data_converters.common import EvoWorkspaceMetadata

this_dir = Path(__file__).parent

def test_convert_grd_parser() -> None:
    grd_file = this_dir / "data" / "mixcat.grd"
    evo_workspace_metadata = EvoWorkspaceMetadata(hub_url="http://example.com")
    tags = {"tagtest": "testvalue"}
    upload_path = "upload/path"

    with (patch("evo.data_converters.grd.importer.grid_main.create_evo_object_service_and_data_client") as mock_create_client,
          patch("evo.data_converters.grd.importer.array_to_parquet_parser.save_array_to_parquet") as mock_save_parquet_file):
        mock_create_client.return_value = (MagicMock(), MagicMock())
        mock_save_parquet_file.return_value = None
        
        result = convert_grd(
            filepath=str(grd_file), 
            evo_workspace_metadata=evo_workspace_metadata, 
            tags=tags, 
            upload_path=upload_path, 
            publish_objects=False
        )

        assert len(result) == 1
        assert result[0].coordinate_reference_system.epsg_code == 32617
        assert result[0].origin == [508438.9007118658, 5177353.641355533, 0.0]
        assert result[0].size == [226, 563]
        assert result[0].cell_size == [9.1, 9.1]

        assert result[0].cell_attributes[0].name == "2d-grid-data-continuous"
        assert result[0].cell_attributes[0].attribute_type == "scalar"
        assert result[0].cell_attributes[0].key == "08277107b6cfc6b81f956dafb06993e945fa06c7dd20d79682768a375afdf27a"
        assert result[0].cell_attributes[0].values.length == 127238
        assert result[0].cell_attributes[0].values.width == 1
        assert result[0].cell_attributes[0].values.data_type == "float64"



