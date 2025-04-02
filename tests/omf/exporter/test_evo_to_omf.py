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

import omf
from evo_schemas.objects import LineSegments_V2_1_0, Pointset_V1_2_0, TriangleMesh_V2_1_0

from evo.data_converters.common import (
    EvoObjectMetadata,
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.data_converters.omf import OMFMetadata
from evo.data_converters.omf.exporter import UnsupportedObjectError, export_omf
from evo.data_converters.omf.importer import convert_omf


class TestEvoToOmfExporter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid4()), cache_root=self.cache_root_dir.name)

        _, self.data_client = create_evo_object_service_and_data_client(self.workspace_metadata)

        # Convert an OMF file to Evo and use the generate Parquet files to test the exporter
        omf_file = path.join(path.dirname(__file__), "../data/one_of_everything.omf")
        self.evo_objects = convert_omf(
            filepath=omf_file, evo_workspace_metadata=self.workspace_metadata, epsg_code=32650
        )[1:]
        self.evo_object = self.evo_objects[0]
        self.assertIsInstance(self.evo_objects[0], Pointset_V1_2_0)
        self.assertIsInstance(self.evo_objects[1], LineSegments_V2_1_0)
        self.assertIsInstance(self.evo_objects[2], TriangleMesh_V2_1_0)

    @patch("evo.data_converters.omf.exporter.evo_to_omf._download_evo_object_by_id")
    def test_should_create_expected_omf_file(self, mock_download_evo_object_by_id: MagicMock) -> None:
        temp_omf_file = tempfile.NamedTemporaryFile(suffix=".omf", delete=False)

        object_id = uuid4()
        version_id = "any version"
        object = EvoObjectMetadata(object_id=object_id, version_id=version_id)

        mock_download_evo_object_by_id.return_value = self.evo_object.as_dict()

        export_omf(
            temp_omf_file.name,
            objects=[object],
            evo_workspace_metadata=self.workspace_metadata,
        )

        reader = omf.OMFReader(temp_omf_file.name)
        project = reader.get_project()

        self.assertEqual(project.name, self.evo_object.name)
        self.assertEqual(project.description, f"Pointset object with ID {object.object_id}")
        self.assertEqual(project.revision, version_id)

        expected_element_types = [omf.PointSetElement]
        self.assertListEqual(expected_element_types, [type(element) for element in project.elements])

    @patch("evo.data_converters.omf.exporter.evo_to_omf._download_evo_object_by_id")
    def test_should_raise_expected_exception_for_unknown_object_schema(
        self, mock_download_evo_object_by_id: MagicMock
    ) -> None:
        temp_omf_file = tempfile.NamedTemporaryFile(suffix=".omf", delete=False)

        evo_object_dict = self.evo_object.as_dict()
        schema = evo_object_dict["schema"] = "/objects/unknown/1.0.0/unknown.schema.json"

        mock_download_evo_object_by_id.return_value = evo_object_dict

        with self.assertRaises(UnsupportedObjectError) as context:
            export_omf(
                temp_omf_file.name,
                objects=[EvoObjectMetadata(object_id=uuid4())],
                evo_workspace_metadata=self.workspace_metadata,
            )
        self.assertEqual(str(context.exception), f"Unknown Geoscience Object schema '{schema}'")

    @patch("evo.data_converters.omf.exporter.evo_to_omf._download_evo_object_by_id")
    def test_should_raise_expected_exception_for_unsupported_object(
        self, mock_download_evo_object_by_id: MagicMock
    ) -> None:
        temp_omf_file = tempfile.NamedTemporaryFile(suffix=".omf", delete=False)

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
            export_omf(
                temp_omf_file.name,
                objects=[EvoObjectMetadata(object_id=uuid4())],
                evo_workspace_metadata=self.workspace_metadata,
            )
        self.assertEqual(
            str(context.exception), f"Exporting {evo_object_name} Geoscience Objects to OMF is not supported"
        )

    @patch("evo.data_converters.omf.exporter.evo_to_omf._download_evo_object_by_id")
    def test_can_export_multiple_objects(self, mock_download_evo_object_by_id: MagicMock) -> None:
        temp_omf_file = tempfile.NamedTemporaryFile(suffix=".omf", delete=False)

        object_id_dict_map = {uuid4(): evo_object.as_dict() for evo_object in self.evo_objects}
        mock_download_evo_object_by_id.side_effect = lambda svc, oid, vid: object_id_dict_map[oid]

        objects = [EvoObjectMetadata(object_id=object_id) for object_id in object_id_dict_map.keys()]

        export_omf(
            temp_omf_file.name,
            objects=objects,
            evo_workspace_metadata=self.workspace_metadata,
        )

        reader = omf.OMFReader(temp_omf_file.name)
        project = reader.get_project()

        expected_name = "EvoObjects"
        expected_description = (
            f"Objects with IDs {objects[0].object_id}, {objects[1].object_id}, {objects[2].object_id}"
        )
        expected_revision = ""

        self.assertEqual(project.name, expected_name)
        self.assertEqual(project.description, expected_description)
        self.assertEqual(project.revision, expected_revision)

        self.assertIsInstance(project.elements[0], omf.PointSetElement)
        self.assertIsInstance(project.elements[1], omf.LineSetElement)
        self.assertIsInstance(project.elements[2], omf.SurfaceElement)

    @patch("evo.data_converters.omf.exporter.evo_to_omf._download_evo_object_by_id")
    def test_metadata_overrides_defaults(self, mock_download_evo_object_by_id: MagicMock) -> None:
        temp_omf_file = tempfile.NamedTemporaryFile(suffix=".omf", delete=False)

        object_id = uuid4()
        version_id = "any version"
        object = EvoObjectMetadata(object_id=object_id, version_id=version_id)

        name = "MyOMFProject"
        revision = "3"
        description = "A test case for OMF metadata"
        omf_metadata = OMFMetadata(name=name, revision=revision, description=description)

        mock_download_evo_object_by_id.return_value = self.evo_object.as_dict()

        export_omf(
            temp_omf_file.name,
            objects=[object],
            omf_metadata=omf_metadata,
            evo_workspace_metadata=self.workspace_metadata,
        )

        reader = omf.OMFReader(temp_omf_file.name)
        project = reader.get_project()

        self.assertEqual(project.name, name)
        self.assertEqual(project.revision, revision)
        self.assertEqual(project.description, description)
