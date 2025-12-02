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

from unittest.mock import Mock, patch

from evo_schemas.objects import DownholeCollection_V1_3_1

from evo.data_converters.ags.importer.ags_to_evo import convert_ags
from evo.objects.data import ObjectMetadata


def test_should_convert_ags_file_without_publish(evo_metadata, valid_ags_1a_path):
    """Integration: converts an AGS file to a geoscience object without publishing."""
    result = convert_ags(filepaths=[valid_ags_1a_path], evo_workspace_metadata=evo_metadata)
    assert isinstance(result, list)
    assert isinstance(result[0], DownholeCollection_V1_3_1)
    assert len(result) == 1

    obj_metadata = result[0]
    assert obj_metadata.tags is not None
    assert obj_metadata.tags["Source"] == "AGS files (via Evo Data Converters)"
    assert obj_metadata.tags["Stage"] == "Experimental"
    assert obj_metadata.tags["InputType"] == "AGS"


@patch("evo.data_converters.ags.importer.ags_to_evo.publish_geoscience_objects")
def test_should_publish_with_hub_url(mock_publish, evo_metadata_with_hub, valid_ags_1a_path):
    """Integration: publishes when hub_url is provided (network calls mocked)."""
    mock_metadata = [Mock(spec=ObjectMetadata)]
    mock_publish.return_value = mock_metadata

    result = convert_ags(filepaths=[valid_ags_1a_path], evo_workspace_metadata=evo_metadata_with_hub)

    assert result == mock_metadata
    mock_publish.assert_called_once()

    publish_kwargs = mock_publish.call_args.kwargs
    object_models = publish_kwargs["object_models"]
    assert len(object_models) == 1
    published_obj = object_models[0]
    assert published_obj.tags is not None
    assert published_obj.tags["Source"] == "AGS files (via Evo Data Converters)"
    assert published_obj.tags["Stage"] == "Experimental"
    assert published_obj.tags["InputType"] == "AGS"


def test_should_add_custom_tags(evo_metadata, valid_ags_1a_path):
    """Integration: conversion succeeds with custom tags supplied (tags applied internally)."""
    custom_tags = {"CustomTag": "CustomValue", "AnotherTag": "AnotherValue"}
    result = convert_ags(filepaths=[valid_ags_1a_path], evo_workspace_metadata=evo_metadata, tags=custom_tags)
    assert len(result) == 1

    published_obj = result[0]
    assert published_obj.tags is not None

    assert published_obj.tags["CustomTag"] == "CustomValue"
    assert published_obj.tags["AnotherTag"] == "AnotherValue"
    assert published_obj.tags["Source"] == "AGS files (via Evo Data Converters)"
    assert published_obj.tags["Stage"] == "Experimental"
    assert published_obj.tags["InputType"] == "AGS"


def test_should_handle_parse_error(evo_metadata, not_ags_path, caplog):
    """Integration: invalid AGS files return empty list (parse error handled)."""
    result = convert_ags(filepaths=[not_ags_path], evo_workspace_metadata=evo_metadata)
    assert result == []
    # Should log a warning
    assert "AGS Format Rule 3" in caplog.text


def test_duplicate_loca_id_across_files_raises_warning(evo_metadata, valid_ags_2a_path, invalid_ags_2b_path, caplog):
    """Integration: multiple ags files with warnings should be imported"""
    result = convert_ags(filepaths=[valid_ags_2a_path, invalid_ags_2b_path], evo_workspace_metadata=evo_metadata)
    assert len(result) == 1

    expected_warnings = [
        "Table 'PROJ' differs between files. Keeping values from first context.",
        "Found 1 duplicate LOCA_ID values when merging contexts.",
        "Duplicate IDs: ['EXAMPLE-2-CPT1']",
        "Found 1 duplicate (LOCA_ID, SCPG_TESN) pairs when merging contexts.",
    ]

    for warning_message in expected_warnings:
        assert warning_message in caplog.text


def test_convert_ags_with_multiple_files_from_different_projects(
    evo_metadata, valid_ags_1a_path, valid_ags_2a_path, caplog
):
    """Integration: Test multiple AGS files from different PROJ_IDs creates separate DownholeCollections."""
    result = convert_ags(filepaths=[valid_ags_1a_path, valid_ags_2a_path], evo_workspace_metadata=evo_metadata)

    # Should create two separate DownholeCollection objects
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(obj, DownholeCollection_V1_3_1) for obj in result)


def test_convert_ags_with_multiple_files_same_project(evo_metadata, valid_ags_1a_path, valid_ags_1b_path):
    """Integration: Test multiple files from same PROJ_ID merge into single DownholeCollection."""
    result = convert_ags(filepaths=[valid_ags_1a_path, valid_ags_1b_path], evo_workspace_metadata=evo_metadata)

    # Should create one merged DownholeCollection object
    assert isinstance(result, list)
    assert len(result) == 1

    downhole_collection = result[0]
    assert isinstance(downhole_collection, DownholeCollection_V1_3_1)

    # Name comes from the first filename
    assert downhole_collection.name == "valid_ags_1a"

    # Verify tags
    assert downhole_collection.tags is not None
    assert downhole_collection.tags["InputType"] == "AGS"
    assert downhole_collection.tags["Source"] == "AGS files (via Evo Data Converters)"

    # Verify CRS was set
    assert downhole_collection.coordinate_reference_system is not None
    assert downhole_collection.coordinate_reference_system.epsg_code == 27700


def test_convert_ags_with_mixed_projects(evo_metadata, valid_ags_1a_path, valid_ags_1b_path, valid_ags_2a_path):
    """Integration: Test mixed PROJ_IDs merge same projects and separates different ones."""
    result = convert_ags(
        filepaths=[valid_ags_1a_path, valid_ags_1b_path, valid_ags_2a_path], evo_workspace_metadata=evo_metadata
    )

    # Should create two DownholeCollection objects (1a+1b merged, 2a separate)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(obj, DownholeCollection_V1_3_1) for obj in result)

    # Verify both collections have proper metadata
    names = [obj.name for obj in result]
    assert len(names) == 2
    assert all(obj.tags is not None for obj in result)
    assert all(obj.tags["InputType"] == "AGS" for obj in result)


def test_convert_ags_with_empty_file_list(evo_metadata):
    """Integration: Test empty file list handled gracefully."""
    result = convert_ags(filepaths=[], evo_workspace_metadata=evo_metadata)
    assert result == []
