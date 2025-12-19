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

import math
import os
import tempfile
import zipfile
from importlib.util import find_spec
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

import pytest

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.data_converters.obj.importer.obj_to_evo import convert_obj


class TestObjZipLoading(IsolatedAsyncioTestCase):
    implementation: str = "trimesh"

    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(self.metadata)
        self.data_client = data_client

    async def test_open_zip_file(self) -> None:
        obj_file = Path(__file__).parent.parent / "data" / "simple_shapes" / "simple_shapes.obj"
        with tempfile.TemporaryDirectory() as tempdirname:
            zip_tempfile = Path(tempdirname) / "simple_shapes.obj.zip"
            with zipfile.ZipFile(zip_tempfile, mode="w", compression=zipfile.ZIP_STORED) as zip_file:
                zip_file.write(obj_file, arcname=obj_file.name)

            # There are sporadic issues on Windows with Trimesh where the zipfile is not ready
            # to be read immediately. Double check here.
            assert os.access(zip_tempfile, os.R_OK), f"Check {zip_tempfile} is readable"

            (triangle_mesh,) = await convert_obj(
                filepath=zip_tempfile,
                evo_workspace_metadata=self.metadata,
                epsg_code=4326,
                publish_objects=False,
                implementation=self.implementation,
            )

            # Rough test of whether it parsed at all
            assert math.isclose(triangle_mesh.bounding_box.min_x, 174.54, rel_tol=0.01)


@pytest.mark.skipif(find_spec("tinyobjloader") is None, reason="tinyobj not installed")
class TestObjZipLoadingTinyObj(TestObjZipLoading):
    implementation = "tinyobj"
