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
from os import path
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from evo_schemas.objects import TriangleMesh_V2_1_0, TriangleMesh_V2_2_0

from evo.data_converters.common import (
    EvoObjectMetadata,
    EvoWorkspaceMetadata,
)
from evo.data_converters.obj.exporter import UnsupportedObjectError, export_obj
from evo.data_converters.omf.importer import convert_omf
from evo.data_converters.obj.importer import convert_obj
import trimesh


class TestEvoToObjExporter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid4()), cache_root=self.cache_root_dir.name)

        # Convert an OMF file to Evo and use the generate Parquet files to test the exporter
        omf_file = path.join(path.dirname(__file__), "../data/pyramid.omf")
        self.evo_objects = convert_omf(
            filepath=omf_file,
            evo_workspace_metadata=self.workspace_metadata,
            epsg_code=32650,
        )
        self.evo_object = self.evo_objects[0]
        self.assertIsInstance(self.evo_object, TriangleMesh_V2_1_0)

    @patch("evo.data_converters.obj.exporter.evo_to_obj._download_evo_object_by_id")
    def test_should_create_expected_obj_file(self, mock_download_evo_object_by_id: MagicMock) -> None:
        temp_obj_file = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)

        object_id = uuid4()
        version_id = "any version"
        object = EvoObjectMetadata(object_id=object_id, version_id=version_id)

        mock_download_evo_object_by_id.return_value = self.evo_object.as_dict()

        export_obj(
            temp_obj_file.name,
            objects=[object],
            evo_workspace_metadata=self.workspace_metadata,
        )

        scene = trimesh.load_scene(temp_obj_file.name)

        self.assertEqual(len(scene.geometry.keys()), 1)

        geometry_name = "geometry_0"
        self.assertIn(geometry_name, scene.geometry)
        geometry = scene.geometry[geometry_name]

        self.assertEqual(len(geometry.vertices), 5)
        self.assertEqual(len(geometry.faces), 6)

        vertex = geometry.vertices[0]
        self.assertAlmostEqual(vertex[0], -1)
        self.assertAlmostEqual(vertex[1], -1)
        self.assertAlmostEqual(vertex[2], 0)

        face = geometry.faces[0]
        self.assertEqual(face[0], 0)
        self.assertEqual(face[1], 1)
        self.assertEqual(face[2], 4)

    @patch("evo.data_converters.obj.exporter.evo_to_obj._download_evo_object_by_id")
    def test_should_raise_expected_exception_for_unknown_object_schema(
        self, mock_download_evo_object_by_id: MagicMock
    ) -> None:
        temp_obj_file = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)

        evo_object_dict = self.evo_object.as_dict()
        schema = evo_object_dict["schema"] = "/objects/unknown/1.0.0/unknown.schema.json"

        mock_download_evo_object_by_id.return_value = evo_object_dict

        with self.assertRaises(UnsupportedObjectError) as context:
            export_obj(
                temp_obj_file.name,
                objects=[EvoObjectMetadata(object_id=uuid4())],
                evo_workspace_metadata=self.workspace_metadata,
            )
        self.assertEqual(str(context.exception), f"Unknown Geoscience Object schema '{schema}'")

    @patch("evo.data_converters.obj.exporter.evo_to_obj._download_evo_object_by_id")
    def test_should_raise_expected_exception_for_unsupported_object(
        self, mock_download_evo_object_by_id: MagicMock
    ) -> None:
        temp_obj_file = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)

        # Given a schema we haven't implemented support for
        evo_object_name = "Regular3DGrid_V1_1_0"
        evo_object_dict = {
            "name": "3d grid",
            "uuid": "00000000-0000-0000-0000-000000000000",
            "schema": "/objects/regular-3d-grid/1.1.0/regular-3d-grid.schema.json",
            "bounding_box": {"min_y": 0, "max_y": 10, "min_x": 0, "max_x": 10, "min_z": 0, "max_z": 10.0},
            "coordinate_reference_system": {"epsg_code": 1024},
            "origin": [0.0, 0.0, 0.0],
            "size": [10, 10, 10],
            "cell_size": [1.0, 1.0, 1.0],
        }

        mock_download_evo_object_by_id.return_value = evo_object_dict

        with self.assertRaises(UnsupportedObjectError) as context:
            export_obj(
                temp_obj_file.name,
                objects=[EvoObjectMetadata(object_id=uuid4())],
                evo_workspace_metadata=self.workspace_metadata,
            )
        self.assertEqual(
            str(context.exception), f"Exporting {evo_object_name} Geoscience Objects to OBJ is not supported"
        )

    @patch("evo.data_converters.obj.exporter.evo_to_obj._download_evo_object_by_id")
    def test_can_handle_multiple_parts(self, mock_download_evo_object_by_id: MagicMock) -> None:
        obj_file = path.join(path.dirname(__file__), "../data/simple_shapes/simple_shapes.obj")
        self.evo_objects = convert_obj(
            filepath=obj_file,
            evo_workspace_metadata=self.workspace_metadata,
            epsg_code=32650,
            publish_objects=False,
        )
        self.assertEqual(len(self.evo_objects), 1)

        self.evo_object = self.evo_objects[0]
        self.assertIsInstance(self.evo_object, TriangleMesh_V2_2_0)

        object_id = uuid4()
        version_id = "any version"

        object = EvoObjectMetadata(object_id=object_id, version_id=version_id)
        mock_download_evo_object_by_id.return_value = self.evo_object.as_dict()

        temp_obj_file = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)

        export_obj(
            temp_obj_file.name,
            objects=[object],
            evo_workspace_metadata=self.workspace_metadata,
        )

        scene = trimesh.load_scene(temp_obj_file.name)

        self.assertEqual(len(scene.geometry.keys()), 1)

        geometry_name = "geometry_0"
        self.assertIn(geometry_name, scene.geometry)
        geometry = scene.geometry[geometry_name]

        self.assertEqual(len(geometry.vertices), 13)
        self.assertEqual(len(geometry.faces), 18)

        vertex = geometry.vertices[0]
        self.assertAlmostEqual(vertex[0], 174.79)
        self.assertAlmostEqual(vertex[1], -41.29)
        self.assertAlmostEqual(vertex[2], 1)

        face = geometry.faces[0]
        self.assertEqual(face[0], 0)
        self.assertEqual(face[1], 1)
        self.assertEqual(face[2], 2)
