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

from unittest.mock import MagicMock, patch

import pytest
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.common.exceptions import ConflictingConnectionDetailsError, MissingConnectionDetailsError
from evo.data_converters.ubc.importer.ubc_to_evo import convert_ubc
from evo.objects.data import ObjectMetadata


def test_convert_ubc_success() -> None:
    files_path = ["dummy_file.msh"]
    epsg_code = 4326
    evo_workspace_metadata = EvoWorkspaceMetadata(hub_url="http://example.com")
    tags = {"tag1": "value1"}
    upload_path = "upload/path"

    mock_geoscience_object = MagicMock(spec=BaseSpatialDataProperties_V1_0_1)
    mock_metadata = MagicMock(spec=ObjectMetadata)

    with (
        patch(
            "evo.data_converters.ubc.importer.ubc_to_evo.create_evo_object_service_and_data_client"
        ) as mock_create_client,
        patch("evo.data_converters.ubc.importer.ubc_to_evo.publish_geoscience_objects") as mock_publish,
        patch(
            "evo.data_converters.ubc.importer.utils.get_geoscience_object_from_ubc", return_value=mock_geoscience_object
        ),
    ):
        mock_create_client.return_value = (MagicMock(), MagicMock())
        mock_publish.return_value = [mock_metadata]

        result = convert_ubc(files_path, epsg_code, evo_workspace_metadata, tags=tags, upload_path=upload_path)

        assert result == [mock_metadata]
        mock_publish.assert_called_once_with(
            [mock_geoscience_object],
            mock_create_client.return_value[0],
            mock_create_client.return_value[1],
            upload_path,
            False,
        )


def test_convert_ubc_no_publish() -> None:
    files_path = ["dummy_file.msh"]
    epsg_code = 4326
    evo_workspace_metadata = EvoWorkspaceMetadata()
    tags = {"tag1": "value1"}
    upload_path = "upload/path"

    mock_geoscience_object = MagicMock(spec=BaseSpatialDataProperties_V1_0_1)

    with (
        patch(
            "evo.data_converters.ubc.importer.ubc_to_evo.create_evo_object_service_and_data_client"
        ) as mock_create_client,
        patch(
            "evo.data_converters.ubc.importer.utils.get_geoscience_object_from_ubc", return_value=mock_geoscience_object
        ),
    ):
        mock_create_client.return_value = (MagicMock(), MagicMock())

        result = convert_ubc(files_path, epsg_code, evo_workspace_metadata, tags=tags, upload_path=upload_path)

        assert result == [mock_geoscience_object]


def test_convert_ubc_missing_connection_details_error() -> None:
    files_path = ["dummy_file.msh"]
    epsg_code = 4326

    with pytest.raises(MissingConnectionDetailsError):
        convert_ubc(files_path, epsg_code)


def test_convert_ubc_conflicting_connection_details_error() -> None:
    files_path = ["dummy_file.msh"]
    epsg_code = 4326
    evo_workspace_metadata = EvoWorkspaceMetadata()
    service_manager_widget = MagicMock()

    with pytest.raises(ConflictingConnectionDetailsError):
        convert_ubc(files_path, epsg_code, evo_workspace_metadata, service_manager_widget)
