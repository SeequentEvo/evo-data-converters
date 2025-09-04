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

import os
import re

import pytest
from evo_schemas.objects import LineSegments_V2_1_0, TriangleMesh_V2_1_0

from evo.data_converters.duf.importer import convert_duf


def test_should_log_warnings(evo_metadata, simple_objects_path, caplog: pytest.LogCaptureFixture) -> None:
    convert_duf(filepath=simple_objects_path, evo_workspace_metadata=evo_metadata, epsg_code=32650)

    expected_log_message = r"Unsupported DUF object type: Circle, ignoring 1 object."
    assert any(re.search(expected_log_message, line) for line in caplog.messages)


def test_should_add_expected_tags(evo_metadata, simple_objects_path) -> None:
    tags = {"First tag": "first tag value", "Second tag": "second tag value"}

    go_objects = convert_duf(
        filepath=simple_objects_path, evo_workspace_metadata=evo_metadata, epsg_code=32650, tags=tags
    )

    expected_tags = {
        "Source": f"{os.path.basename(simple_objects_path)} (via Evo Data Converters)",
        "InputType": "DUF",
        "Category": "ModelEntities",
        **tags,
    }
    assert go_objects[0].tags == expected_tags


def test_should_convert_expected_geometry_types(evo_metadata, simple_objects_path) -> None:
    go_objects = convert_duf(filepath=simple_objects_path, evo_workspace_metadata=evo_metadata, epsg_code=32650)

    expected_go_object_types = [LineSegments_V2_1_0, TriangleMesh_V2_1_0]
    assert [type(obj) for obj in go_objects] == expected_go_object_types
