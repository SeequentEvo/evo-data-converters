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

""" """

from os import path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import uuid4
from zipfile import BadZipFile

from evo_schemas.components import BoundingBox_V1_0_1
from evo_schemas.objects import TriangleMesh_V2_0_0

from evo.data_converters.common import EvoWorkspaceMetadata, crs_from_epsg_code
from evo.data_converters.resqml.importer import convert_resqml


class TestConverter(TestCase):
    def setUp(self) -> None:
        self.temp_cache_dir = TemporaryDirectory()
        self.workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid4()), cache_root=self.temp_cache_dir.name)

    def test_unknown_file(self) -> None:
        # Given a file that does not exist
        file_name = "this file does not exist"
        # Then when convert_resqml is called
        # It should raise a FileNotFound exception
        with self.assertRaises(FileNotFoundError):
            convert_resqml(filepath=file_name, epsg_code=0, evo_workspace_metadata=self.workspace_metadata)

    def test_non_epc_file_thats_not_zipped(self) -> None:
        # Given a file that is not in epc format
        file_name = path.join(path.dirname(__file__), "data/not_zipped.epc")

        # Then when convert_resqml is called
        # It should raise a BadZipFile exception
        # TODO this should eventually be wrapped in what ever exception we're going to throw
        with self.assertRaises(BadZipFile):
            convert_resqml(filepath=file_name, epsg_code=0, evo_workspace_metadata=self.workspace_metadata)

    def test_non_epc_file_thats_zipped(self) -> None:
        # Given a file that is not in epc format
        file_name = path.join(path.dirname(__file__), "data/invalid.epc")

        # Then when convert_resqml is called
        # It should raise a KeyError exception
        # TODO this should eventually be wrapped in what ever exception we're going to throw
        with self.assertRaises(KeyError):
            convert_resqml(filepath=file_name, epsg_code=0, evo_workspace_metadata=self.workspace_metadata)

    def test_should_create_expected_objects(self) -> None:
        file_name = path.join(path.dirname(__file__), "data/surface.epc")

        epsg_code = 32650
        go_objects = convert_resqml(
            filepath=file_name, evo_workspace_metadata=self.workspace_metadata, epsg_code=epsg_code
        )
        self.assertEqual(len(go_objects), 1)

        triangle_mesh_go = go_objects[0]

        expected_triangle_mesh_go = TriangleMesh_V2_0_0(
            name="surface",
            uuid=None,
            coordinate_reference_system=crs_from_epsg_code(epsg_code),
            bounding_box=triangle_mesh_go.bounding_box,
            triangles=triangle_mesh_go.triangles,
            extensions=triangle_mesh_go.extensions,
            tags=triangle_mesh_go.tags,
        )
        self.assertEqual(expected_triangle_mesh_go, triangle_mesh_go)

        expected_bounding_box = BoundingBox_V1_0_1(
            min_x=100.0,
            max_x=100.0,
            min_y=100.0,
            max_y=100.0,
            min_z=-50.0,
            max_z=-50.0,
        )
        self.assertAlmostEqual(expected_bounding_box.min_x, triangle_mesh_go.bounding_box.min_x)
        self.assertAlmostEqual(expected_bounding_box.max_x, triangle_mesh_go.bounding_box.max_x)
        self.assertAlmostEqual(expected_bounding_box.min_y, triangle_mesh_go.bounding_box.min_y)
        self.assertAlmostEqual(expected_bounding_box.max_y, triangle_mesh_go.bounding_box.max_y)
        self.assertAlmostEqual(expected_bounding_box.min_z, triangle_mesh_go.bounding_box.min_z)
        self.assertAlmostEqual(expected_bounding_box.max_z, triangle_mesh_go.bounding_box.max_z)

    def test_should_add_expected_tags(self) -> None:
        file_name = path.join(path.dirname(__file__), "data/surface.epc")

        tags = {"First tag": "first tag value", "Second tag": "second tag value"}

        go_objects = convert_resqml(
            filepath=file_name, evo_workspace_metadata=self.workspace_metadata, epsg_code=32650, tags=tags
        )

        expected_tags = {
            "Source": "surface.epc (via Evo Data Converters)",
            "Stage": "Experimental",
            "InputType": "RESQML",
            **tags,
        }
        self.assertEqual(go_objects[0].tags, expected_tags)
