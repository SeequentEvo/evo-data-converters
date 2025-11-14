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


def test_should_convert_ags_file_without_publish(evo_metadata, valid_ags_path):
    """Integration: converts an AGS file to a geoscience object without publishing."""
    result = convert_ags(filepath=valid_ags_path, evo_workspace_metadata=evo_metadata)
    assert isinstance(result, DownholeCollection_V1_3_1)

    assert result.tags is not None
    assert result.tags["Source"] == "AGS files (via Evo Data Converters)"
    assert result.tags["Stage"] == "Experimental"
    assert result.tags["InputType"] == "AGS"


@patch("evo.data_converters.ags.importer.ags_to_evo.publish_geoscience_objects")
def test_should_publish_with_hub_url(mock_publish, evo_metadata_with_hub, valid_ags_path):
    """Integration: publishes when hub_url is provided (network calls mocked)."""
    mock_metadata = Mock(spec=ObjectMetadata)
    mock_publish.return_value = [mock_metadata]

    result = convert_ags(filepath=valid_ags_path, evo_workspace_metadata=evo_metadata_with_hub)

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


def test_should_add_custom_tags(evo_metadata, valid_ags_path):
    """Integration: conversion succeeds with custom tags supplied (tags applied internally)."""
    custom_tags = {"CustomTag": "CustomValue", "AnotherTag": "AnotherValue"}
    result = convert_ags(filepath=valid_ags_path, evo_workspace_metadata=evo_metadata, tags=custom_tags)

    assert result.tags["CustomTag"] == "CustomValue"
    assert result.tags["AnotherTag"] == "AnotherValue"
    assert result.tags["Source"] == "AGS files (via Evo Data Converters)"
    assert result.tags["Stage"] == "Experimental"
    assert result.tags["InputType"] == "AGS"


def test_should_handle_parse_error(evo_metadata, not_ags_path):
    """Integration: invalid AGS files return None (parse error handled)."""
    result = convert_ags(filepath=not_ags_path, evo_workspace_metadata=evo_metadata)
    assert result is None
