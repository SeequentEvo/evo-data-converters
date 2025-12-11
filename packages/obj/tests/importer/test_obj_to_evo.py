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
from unittest import TestCase

from evo_schemas.objects import TriangleMesh_V2_2_0

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.data_converters.obj.importer.obj_to_evo import convert_obj


class TestObjToEvoConverter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(self.metadata)
        self.data_client = data_client

    async def test_should_add_expected_tags(self) -> None:
        obj_file = Path(__file__).parent / "data" / "simple_shapes" / "simple_shapes.obj"
        tags = {"First tag": "first tag value", "Second tag": "second tag value"}

        go_objects = await convert_obj(
            filepath=obj_file, evo_workspace_metadata=self.metadata, epsg_code=4326, tags=tags, publish_objects=False
        )

        expected_tags = {
            "Source": "simple_shapes.obj (via Evo Data Converters)",
            "Stage": "Experimental",
            "InputType": "OBJ",
            **tags,
        }
        self.assertEqual(go_objects[0].tags, expected_tags)

    async def test_should_convert_expected_geometry_types(self) -> None:
        obj_file = Path(__file__).parent / "data" / "simple_shapes" / "simple_shapes.obj"
        go_objects = await convert_obj(
            filepath=obj_file, evo_workspace_metadata=self.metadata, epsg_code=4326, publish_objects=False
        )

        expected_go_object_types = [TriangleMesh_V2_2_0]
        self.assertListEqual(expected_go_object_types, [type(obj) for obj in go_objects])
