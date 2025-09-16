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

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from evo_schemas.objects import DownholeCollection_V1_3_0 as DownholeCollectionGo
from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.common.objects.downhole_collection import DownholeCollection
from evo.data_converters.common.objects.downhole_collection_to_geoscience_object import (
    DownholeCollectionToGeoscienceObject,
)
from evo.data_converters.gef.importer import convert_gef
from evo.objects.data import ObjectMetadata


class TestConvertGef:
    """Test the convert_gef function behaves as intended."""

    @pytest.fixture
    def sample_filepaths(self):
        """Sample file paths for testing."""
        return [Path("test1.gef"), Path("test2.gef")]

    @pytest.fixture
    def workspace_metadata(self):
        """Mock workspace metadata with hub_url."""
        hub_url = "https://example.org"
        cache_root = tempfile.TemporaryDirectory()
        return EvoWorkspaceMetadata(workspace_id=str(uuid4()), cache_root=cache_root.name, hub_url=hub_url)

    @pytest.fixture
    def mock_downhole_collection_go(self):
        """Mock downhole collection geoscience object."""
        dhc_go = Mock(spec=DownholeCollectionGo)
        dhc_go.tags = {}
        return dhc_go

    @pytest.fixture
    def mock_downhole_collection(self):
        """Mock downhole collection intermediary object."""
        dhc = Mock(spec=DownholeCollection)
        return dhc

    @pytest.fixture
    def mock_object_metadata(self):
        """Mock object metadata."""
        return Mock(spec=ObjectMetadata)

    @patch("evo.data_converters.gef.importer.gef_to_evo.publish_geoscience_objects")
    @patch("evo.data_converters.gef.importer.gef_to_evo.create_evo_object_service_and_data_client")
    @patch("evo.data_converters.gef.importer.gef_to_evo.create_from_parsed_gef_cpts")
    @patch("evo.data_converters.gef.importer.gef_to_evo.parse_gef_files")
    @patch("evo.data_converters.gef.importer.gef_to_evo.DownholeCollectionToGeoscienceObject")
    def test_convert_gef_with_workspace_metadata_and_hub_url(
        self,
        mock_converter,
        mock_parse_files,
        mock_create_collection,
        mock_create_clients,
        mock_publish,
        sample_filepaths,
        workspace_metadata,
        mock_downhole_collection,
        mock_downhole_collection_go,
        mock_object_metadata,
    ):
        """Test conversion with workspace metadata and hub_url - should publish."""
        collection_name = "Test Collection"

        mock_create_clients.return_value = (Mock(), Mock())
        mock_converter.return_value = Mock(
            spec=DownholeCollectionToGeoscienceObject, convert=Mock(return_value=mock_downhole_collection_go)
        )
        mock_parse_files.return_value = Mock()
        mock_create_collection.return_value = mock_downhole_collection
        mock_publish.return_value = mock_object_metadata

        result = convert_gef(
            name=collection_name, filepaths=sample_filepaths, evo_workspace_metadata=workspace_metadata
        )

        assert result == mock_object_metadata
        assert isinstance(result, ObjectMetadata)
        mock_publish.assert_called_once()

        mock_create_collection.assert_called_once()
        assert mock_create_collection.call_args.kwargs["name"] == collection_name

        # Check tags were added
        expected_tags = {
            "Source": "GEF-CPT files (via Evo Data Converters)",
            "Stage": "Experimental",
            "InputType": "GEF-CPT",
        }
        for key, value in expected_tags.items():
            assert mock_downhole_collection_go.tags[key] == value
