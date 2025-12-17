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
from importlib.util import find_spec
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

import pytest

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.data_converters.obj.importer.implementation.base import InvalidOBJError
from evo.data_converters.obj.importer.obj_to_evo import convert_obj


class TestObjFileErrors(IsolatedAsyncioTestCase):
    implementation: str = "trimesh"

    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(self.metadata)
        self.data_client = data_client

    async def test_missing_vertices_file(self) -> None:
        """
        Attempts to load a file that's missing referenced vertices.
        """
        obj_file = Path(__file__).parent.parent / "data" / "simple_shapes" / "simple_shapes_corrupt.obj"

        with self.assertRaises(InvalidOBJError):
            (triangle_mesh,) = await convert_obj(
                filepath=obj_file,
                evo_workspace_metadata=self.metadata,
                epsg_code=4326,
                publish_objects=False,
                implementation=self.implementation,
            )

    async def test_wrong_format_file(self) -> None:
        """
        Attempts to load an STL version of simple_shapes that should refuse to load, even
        though several of the implementations would otherwise support STL.
        """
        stl_file = Path(__file__).parent.parent / "data" / "simple_shapes" / "simple_shapes.stl"

        with self.assertRaises(InvalidOBJError):
            (triangle_mesh,) = await convert_obj(
                filepath=stl_file,
                evo_workspace_metadata=self.metadata,
                epsg_code=4326,
                publish_objects=False,
                implementation=self.implementation,
            )


@pytest.mark.skipif(find_spec("tinyobjloader") is None, reason="tinyobj not installed")
class TestObjFileErrorsTinyObj(TestObjFileErrors):
    implementation = "tinyobj"
