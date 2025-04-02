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

import re
import tempfile
from os import path
from unittest import TestCase

import pytest
from evo_schemas.objects import LineSegments_V2_1_0, Pointset_V1_2_0, TriangleMesh_V2_1_0

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.omf.importer import convert_omf


@pytest.mark.usefixtures("caplog")
class TestOmfToEvoProblems:
    def test_should_log_warnings(self, caplog: pytest.LogCaptureFixture) -> None:
        cache_root_dir = tempfile.TemporaryDirectory()
        metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=cache_root_dir.name
        )
        omf_file = path.join(path.dirname(__file__), "data/duplicate_element_name.omf")

        convert_omf(filepath=omf_file, evo_workspace_metadata=metadata, epsg_code=32650)

        expected_log_message = r"WARNING  evo.data_converters:omf_to_evo.py:\d+ Problems returned reading OMF project:"
        assert any(re.search(expected_log_message, line) for line in caplog.text.splitlines())

        expected_log_message = r"WARNING  evo.data_converters:omf_to_evo.py:\d+ Warning: 'Project::elements\[\.\.\]::name' contains duplicate of \"Duplicate\", inside 'Duplicate Element Name Test'"
        assert any(re.search(expected_log_message, line) for line in caplog.text.splitlines())


class TestOmfToEvoConverter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(self.metadata)
        self.data_client = data_client

    def test_should_add_expected_tags(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/pointset_v2.omf")

        tags = {"First tag": "first tag value", "Second tag": "second tag value"}

        go_objects = convert_omf(filepath=omf_file, evo_workspace_metadata=self.metadata, epsg_code=32650, tags=tags)

        expected_tags = {
            "Source": "pointset_v2.omf (via Evo Data Converters)",
            "Stage": "Experimental",
            "InputType": "OMF",
            **tags,
        }
        self.assertEqual(go_objects[0].tags, expected_tags)

    def test_should_convert_expected_geometry_types(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        go_objects = convert_omf(filepath=omf_file, evo_workspace_metadata=self.metadata, epsg_code=32650)

        expected_go_object_types = [TriangleMesh_V2_1_0, Pointset_V1_2_0, LineSegments_V2_1_0, TriangleMesh_V2_1_0]
        self.assertListEqual(expected_go_object_types, [type(obj) for obj in go_objects])
