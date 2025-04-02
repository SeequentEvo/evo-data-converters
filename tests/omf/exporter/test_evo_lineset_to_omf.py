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
from uuid import uuid4

import omf
import pyarrow as pa
from evo_schemas.components import (
    ContinuousAttribute_V1_0_1,
    ContinuousAttribute_V1_1_0,
    Segments_V1_1_0,
    Segments_V1_1_0_Indices,
    Segments_V1_1_0_Vertices,
)
from evo_schemas.elements import IndexArray2_V1_0_1
from evo_schemas.objects import LineSegments_V2_0_0, LineSegments_V2_0_0_Parts, LineSegments_V2_1_0

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.omf.exporter import export_omf_lineset
from evo.data_converters.omf.importer import convert_omf


class TestExportOmfLineSet(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid4()), cache_root=self.cache_root_dir.name)

        _, self.data_client = create_evo_object_service_and_data_client(self.workspace_metadata)

        # Convert an OMF file to Evo and use the generated Parquet files to test the exporter
        omf_file = path.join(path.dirname(__file__), "..", "data", "lineset_v1.omf")
        self.evo_objects = convert_omf(
            filepath=omf_file, evo_workspace_metadata=self.workspace_metadata, epsg_code=32650
        )

    def test_should_create_expected_omf_lineset_element(self) -> None:
        evo_object = self.evo_objects[0]
        self.assertIsInstance(evo_object, LineSegments_V2_1_0)

        evo_object.description = "any description"
        element = export_omf_lineset(uuid4(), None, evo_object, self.data_client)

        self.assertEqual(element.name, evo_object.name)
        self.assertEqual(element.description, evo_object.description)

        self.assertIsInstance(element.geometry, omf.LineSetGeometry)

        self.assertEqual(len(element.geometry.vertices), 100)

        vertex = element.geometry.vertices[0]
        self.assertAlmostEqual(vertex[0], 0.08736983268319776)
        self.assertAlmostEqual(vertex[1], 0.5130448433857124)
        self.assertAlmostEqual(vertex[2], 0.4256484661327785)

        self.assertEqual(len(element.geometry.segments), 50)

        segment = element.geometry.segments[0]
        self.assertEqual(segment[0], 79)
        self.assertEqual(segment[1], 75)

    def test_should_create_expected_omf_vertex_attributes(self) -> None:
        evo_object = self.evo_objects[6]
        self.assertIsInstance(evo_object, LineSegments_V2_1_0)
        self.assertEqual(evo_object.name, "data_vertices_lines")

        element = export_omf_lineset(uuid4(), None, evo_object, self.data_client)

        self.assertEqual(len(element.data), 1)

        scalar_data = element.data[0]
        self.assertIsInstance(scalar_data, omf.ScalarData)
        self.assertEqual(scalar_data.location, "vertices")
        self.assertEqual(scalar_data.name, "data assigned to vertices")

        self.assertEqual(len(scalar_data.array), 100)
        self.assertAlmostEqual(scalar_data.array[0], 0.42185369599561073)
        self.assertAlmostEqual(scalar_data.array[1], 0.40827236099074904)

    def test_should_create_expected_omf_segment_attributes(self) -> None:
        evo_object = self.evo_objects[5]
        self.assertIsInstance(evo_object, LineSegments_V2_1_0)
        self.assertEqual(evo_object.name, "data_segments_lines")

        element = export_omf_lineset(uuid4(), None, evo_object, self.data_client)

        self.assertEqual(len(element.data), 1)

        scalar_data = element.data[0]

        self.assertIsInstance(scalar_data, omf.ScalarData)
        self.assertEqual(scalar_data.location, "segments")

        self.assertEqual(scalar_data.name, "data assigned to segments")

        self.assertEqual(len(scalar_data.array), 50)
        self.assertAlmostEqual(scalar_data.array[0], 0.6697228903296453)

    def test_should_create_expected_omf_lineset_element_from_old_object_schema(self) -> None:
        line_segments_object = self.evo_objects[6]
        self.assertIsInstance(line_segments_object, LineSegments_V2_1_0)

        continuous_attribute = line_segments_object.segments.vertices.attributes[0]
        self.assertIsInstance(continuous_attribute, ContinuousAttribute_V1_1_0)

        old_continuous_attribute = ContinuousAttribute_V1_0_1(
            name=continuous_attribute.name,
            values=continuous_attribute.values,
            nan_description=continuous_attribute.nan_description,
        )

        evo_object = LineSegments_V2_0_0(
            name=line_segments_object.name,
            description="any description",
            uuid=None,
            bounding_box=line_segments_object.bounding_box,
            coordinate_reference_system=line_segments_object.coordinate_reference_system,
            segments=Segments_V1_1_0(
                vertices=Segments_V1_1_0_Vertices(
                    **{**line_segments_object.segments.vertices.as_dict(), "attributes": [old_continuous_attribute]}
                ),
                indices=Segments_V1_1_0_Indices(
                    **{**line_segments_object.segments.indices.as_dict(), "attributes": []}
                ),
            ),
        )

        element = export_omf_lineset(uuid4(), None, evo_object, self.data_client)

        self.assertEqual(element.name, evo_object.name)
        self.assertEqual(element.description, evo_object.description)

        self.assertIsInstance(element.geometry, omf.LineSetGeometry)

        self.assertEqual(len(element.geometry.vertices), 100)
        self.assertEqual(len(element.geometry.segments), 50)

        self.assertEqual(len(element.data), 1)

        scalar_data = element.data[0]
        self.assertIsInstance(scalar_data, omf.ScalarData)
        self.assertEqual(scalar_data.location, "vertices")
        self.assertEqual(scalar_data.name, "data assigned to vertices")

        self.assertEqual(len(scalar_data.array), 100)

    def test_should_unpack_chunked_segments(self) -> None:
        evo_object = self.evo_objects[6]

        start_segment_index = 25
        number_of_segments = 10

        chunks_schema = pa.schema(
            [
                pa.field("start_segment_index", pa.uint64()),
                pa.field("number_of_segments", pa.uint64()),
            ]
        )
        chunks_table = pa.Table.from_pydict(
            {
                "start_segment_index": [start_segment_index],
                "number_of_segments": [number_of_segments],
            },
            schema=chunks_schema,
        )
        chunks_data = self.data_client.save_table(chunks_table)
        chunks = IndexArray2_V1_0_1(**chunks_data)

        evo_object.parts = LineSegments_V2_0_0_Parts(chunks=chunks)

        element = export_omf_lineset(uuid4(), None, evo_object, self.data_client)

        self.assertEqual(len(element.geometry.vertices), 100)
        self.assertEqual(len(element.geometry.segments), number_of_segments)
