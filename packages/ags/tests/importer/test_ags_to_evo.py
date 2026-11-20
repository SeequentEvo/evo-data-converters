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

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from evo.data_converters.ags.importer.ags_to_downhole_collection import create_from_parsed_ags
from evo.data_converters.ags.importer.ags_to_evo import convert_ags, publish_downhole_collections
from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.common.exceptions import ConflictingConnectionDetailsError
from evo.objects.data import ObjectMetadata
from evo.objects.typed import DownholeCollectionData


def test_convert_ags_saves_elevation_from_selected_coordinate_family(
    evo_metadata: EvoWorkspaceMetadata, test_elevations_ags_path: str
) -> None:
    result = asyncio.run(
        convert_ags(filepaths=[test_elevations_ags_path], evo_workspace_metadata=evo_metadata, publish_objects=False)
    )

    assert len(result) == 1
    collection = result[0]
    assert isinstance(collection, DownholeCollectionData)
    assert collection.properties["hole_id"].tolist() == ["BH01", "BH02", "BH03", "BH04", "BH05"]
    assert collection.properties["z"].tolist() == [-4.78, 16.48, 0.0, 0.0, 0.0]


def test_should_convert_ags_file_without_publish(evo_metadata, valid_ags_1a_path):
    result = asyncio.run(
        convert_ags(filepaths=[valid_ags_1a_path], evo_workspace_metadata=evo_metadata, publish_objects=False)
    )

    assert len(result) == 1
    data = result[0]
    assert isinstance(data, DownholeCollectionData)
    assert data.tags is not None
    assert data.tags["Source"] == "valid_ags_1a (via Evo Data Converters)"
    assert data.tags["Stage"] == "Experimental"
    assert data.tags["InputType"] == "AGS"


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
@patch("evo.data_converters.ags.importer.ags_to_evo.DownholeCollection")
def test_should_publish_with_hub_url(mock_collection, mock_clients, evo_metadata_with_hub, valid_ags_1a_path):
    metadata = Mock(spec=ObjectMetadata)
    mock_collection.create = AsyncMock(return_value=SimpleNamespace(metadata=metadata))
    data_client = Mock()
    context = Mock()
    data_client.get_static_context.return_value = context
    mock_clients.return_value = (Mock(), data_client)

    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path],
            evo_workspace_metadata=evo_metadata_with_hub,
            publish_objects=True,
            upload_path="prefix",
        )
    )

    assert result == [metadata]
    mock_collection.create.assert_awaited_once()
    call = mock_collection.create.await_args
    assert call.args[0] == context
    assert call.kwargs["path"] == "prefix/valid_ags_1a.json"
    data = call.args[1]
    assert data.tags is not None
    assert data.tags["Source"] == "valid_ags_1a (via Evo Data Converters)"
    assert data.tags["Stage"] == "Experimental"
    assert data.tags["InputType"] == "AGS"


def test_should_add_custom_tags(evo_metadata, valid_ags_1a_path):
    custom_tags = {"CustomTag": "CustomValue", "AnotherTag": "AnotherValue"}
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path],
            evo_workspace_metadata=evo_metadata,
            tags=custom_tags,
            publish_objects=False,
        )
    )

    assert len(result) == 1
    assert result[0].tags is not None
    assert result[0].tags["CustomTag"] == "CustomValue"
    assert result[0].tags["AnotherTag"] == "AnotherValue"
    assert result[0].tags["InputType"] == "AGS"


def test_should_handle_parse_error(evo_metadata, not_ags_path, caplog):
    result = asyncio.run(
        convert_ags(filepaths=[not_ags_path], evo_workspace_metadata=evo_metadata, publish_objects=False)
    )

    assert result == []
    assert "AGS Format Rule 3" in caplog.text


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
@patch("evo.data_converters.ags.importer.ags_to_evo.DownholeCollection")
def test_coordinate_crs_mismatch_is_not_published(
    mock_collection,
    mock_clients,
    evo_metadata_with_hub: EvoWorkspaceMetadata,
    valid_ags_1a_path: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    filepath = tmp_path / "mismatched_crs.ags"
    filepath.write_text(Path(valid_ags_1a_path).read_text().replace('"OSGB"', '"WGS84"'))
    mock_clients.return_value = (Mock(), Mock())

    result = asyncio.run(convert_ags(filepaths=[str(filepath)], evo_workspace_metadata=evo_metadata_with_hub))

    assert result == []
    assert "Failed to convert AGS file 'mismatched_crs'" in caplog.text
    assert "No complete geographic coordinate pair" in caplog.text
    mock_collection.create.assert_not_called()


@pytest.mark.parametrize("merge_files", [True, False])
def test_coordinate_crs_mismatch_file_is_skipped(
    evo_metadata: EvoWorkspaceMetadata,
    test_elevations_ags_path: str,
    valid_ags_1a_path: str,
    tmp_path: Path,
    merge_files: bool,
) -> None:
    filepath = tmp_path / "mismatched_crs.ags"
    filepath.write_text(Path(valid_ags_1a_path).read_text().replace('"OSGB"', '"WGS84"'))

    result = asyncio.run(
        convert_ags(
            filepaths=[str(filepath), test_elevations_ags_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=merge_files,
        )
    )

    assert [collection.name for collection in result] == ["test_elevations"]


@pytest.mark.parametrize("merge_files", [True, False])
def test_conflicting_crs_file_is_skipped(
    evo_metadata: EvoWorkspaceMetadata,
    test_elevations_ags_path: str,
    conflicting_crs_ags_path: str,
    merge_files: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = asyncio.run(
        convert_ags(
            filepaths=[test_elevations_ags_path, conflicting_crs_ags_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=merge_files,
        )
    )

    assert len(result) == 1
    assert result[0].name == "test_elevations"
    assert "LOCA rows declare different coordinate reference systems" in caplog.text


def test_duplicate_loca_id_across_files_raises_warning(evo_metadata, valid_ags_2a_path, invalid_ags_2b_path, caplog):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_2a_path, invalid_ags_2b_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
        )
    )

    assert len(result) == 1
    for message in (
        "Found 1 duplicate LOCA_ID values when merging contexts.",
        "Duplicate IDs: ['EXAMPLE-2-CPT1']",
        "Found 1 duplicate (LOCA_ID, SCPG_TESN) pairs when merging contexts.",
    ):
        assert message in caplog.text


def test_convert_ags_with_multiple_files_from_different_projects(evo_metadata, valid_ags_1a_path, valid_ags_2a_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_2a_path], evo_workspace_metadata=evo_metadata, publish_objects=False
        )
    )

    assert len(result) == 2
    assert all(isinstance(item, DownholeCollectionData) for item in result)


def test_convert_ags_with_multiple_files_same_project(evo_metadata, valid_ags_1a_path, valid_ags_1b_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_1b_path], evo_workspace_metadata=evo_metadata, publish_objects=False
        )
    )

    assert len(result) == 1
    data = result[0]
    assert isinstance(data, DownholeCollectionData)
    assert data.name == "valid_ags_1a"
    assert data.tags is not None
    assert data.tags["InputType"] == "AGS"
    assert data.tags["Source"] == "valid_ags_1a (via Evo Data Converters)"
    assert data.coordinate_reference_system == 27700


def test_convert_ags_with_multiple_files_same_project_no_merge(evo_metadata, valid_ags_1a_path, valid_ags_1b_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_1b_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=False,
        )
    )

    assert len(result) == 2
    assert {item.name for item in result} == {"valid_ags_1a", "valid_ags_1b"}
    assert all(item.tags is not None and item.tags["InputType"] == "AGS" for item in result)


def test_convert_ags_with_mixed_projects(evo_metadata, valid_ags_1a_path, valid_ags_1b_path, valid_ags_2a_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_1b_path, valid_ags_2a_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
        )
    )

    assert len(result) == 2
    assert all(item.tags is not None and item.tags["InputType"] == "AGS" for item in result)


def test_convert_ags_with_empty_file_list(evo_metadata):
    assert asyncio.run(convert_ags(filepaths=[], evo_workspace_metadata=evo_metadata, publish_objects=False)) == []


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
def test_publish_requires_hub_url(mock_clients, evo_metadata, valid_ags_1a_path):
    mock_clients.return_value = (Mock(), Mock())
    with pytest.raises(ConflictingConnectionDetailsError, match="without hub_url"):
        asyncio.run(convert_ags(filepaths=[valid_ags_1a_path], evo_workspace_metadata=evo_metadata))
    mock_clients.assert_called_once()


@pytest.mark.parametrize("overwrite, method", [(False, "create"), (True, "create_or_replace")])
@patch("evo.data_converters.ags.importer.ags_to_evo.DownholeCollection")
def test_publish_downhole_collections(mock_collection, overwrite, method, mock_ags_context):
    mock_ags_context.filename = "test_file"
    data = create_from_parsed_ags(mock_ags_context)
    context = Mock()
    environment = Mock()
    environment.hub_url = "https://test.hub.url"
    environment.org_id = "00000000-0000-0000-0000-000000000001"
    environment.workspace_id = "00000000-0000-0000-0000-000000000002"
    context.get_environment.return_value = environment
    metadata = Mock(spec=ObjectMetadata)
    publish = AsyncMock(return_value=SimpleNamespace(metadata=metadata))
    setattr(mock_collection, method, publish)

    result = asyncio.run(
        publish_downhole_collections([data, data], context, "prefix", overwrite_existing_objects=overwrite)
    )

    assert result == [metadata, metadata]
    assert publish.await_count == 2
    if overwrite:
        assert [call.args[1].object_path for call in publish.await_args_list] == [
            "prefix/test_file_1.json",
            "prefix/test_file_2.json",
        ]
    else:
        assert [call.kwargs["path"] for call in publish.await_args_list] == [
            "prefix/test_file_1.json",
            "prefix/test_file_2.json",
        ]
