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

from os import path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase

import omf2
import pyarrow.parquet as pq
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    ContinuousAttribute_V1_1_0,
    NanContinuous_V1_0_1,
)
from evo_schemas.elements.float_array_1 import FloatArray1_V1_0_1
from evo_schemas.objects import LineSegments_V2_1_0

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    crs_from_epsg_code,
)

from evo.data_converters.omf import OMFReaderContext
from evo.data_converters.omf.importer import convert_omf_lineset


class TestOMFLineSetConverter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = TemporaryDirectory()
        metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(metadata)
        self.data_client = data_client

    def _element_by_name(self, project: omf2.Project, element_name: str) -> omf2.Element:
        for element in project.elements():
            if element.name == element_name:
                return element

        self.fail(f"Could not find element named {element_name}")

    def test_should_convert_omf_v1_lineset_geometry(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/lineset_v1.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        lineset_element = self._element_by_name(project, "data_segments_lines")

        epsg_code = 32650
        line_segments_go = convert_omf_lineset(
            lineset=lineset_element, project=project, reader=reader, data_client=self.data_client, epsg_code=epsg_code
        )

        self.assertIsInstance(line_segments_go, LineSegments_V2_1_0)

        expected_line_segments_go = LineSegments_V2_1_0(
            name=lineset_element.name,
            uuid=None,
            coordinate_reference_system=crs_from_epsg_code(epsg_code),
            bounding_box=line_segments_go.bounding_box,
            segments=line_segments_go.segments,
        )
        self.assertEqual(expected_line_segments_go, line_segments_go)

        expected_bounding_box = BoundingBox_V1_0_1(
            min_x=0.005672391805247257,
            max_x=0.9872553481593824,
            min_y=0.013368379306871403,
            max_y=0.9942228529185596,
            min_z=0.009965527049217271,
            max_z=0.9999608574802016,
        )

        self.assertAlmostEqual(expected_bounding_box.min_x, line_segments_go.bounding_box.min_x)
        self.assertAlmostEqual(expected_bounding_box.max_x, line_segments_go.bounding_box.max_x)
        self.assertAlmostEqual(expected_bounding_box.min_y, line_segments_go.bounding_box.min_y)
        self.assertAlmostEqual(expected_bounding_box.max_y, line_segments_go.bounding_box.max_y)
        self.assertAlmostEqual(expected_bounding_box.min_z, line_segments_go.bounding_box.min_z)
        self.assertAlmostEqual(expected_bounding_box.max_z, line_segments_go.bounding_box.max_z)

        vertices_parquet_file = path.join(str(self.data_client.cache_location), line_segments_go.segments.vertices.data)
        indices_parquet_file = path.join(str(self.data_client.cache_location), line_segments_go.segments.indices.data)

        vertices = pq.read_table(vertices_parquet_file)
        indices = pq.read_table(indices_parquet_file)

        self.assertEqual(100, len(vertices))
        self.assertAlmostEqual(vertices["x"][0].as_py(), 0.7432876095822546)
        self.assertAlmostEqual(vertices["y"][0].as_py(), 0.9942228529185596)
        self.assertAlmostEqual(vertices["z"][0].as_py(), 0.938936637513444)

        self.assertEqual(50, len(indices))
        self.assertEqual(indices["n0"][0].as_py(), 86)
        self.assertEqual(indices["n1"][0].as_py(), 48)

    def test_should_convert_omf_v2_lineset_geometry(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/lineset_v2.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        lineset_element = self._element_by_name(project, "data_segments_lines")

        epsg_code = 32650
        line_segments_go = convert_omf_lineset(
            lineset=lineset_element, project=project, reader=reader, data_client=self.data_client, epsg_code=epsg_code
        )

        self.assertIsInstance(line_segments_go, LineSegments_V2_1_0)

        expected_line_segments_go = LineSegments_V2_1_0(
            name=lineset_element.name,
            uuid=None,
            coordinate_reference_system=crs_from_epsg_code(epsg_code),
            bounding_box=line_segments_go.bounding_box,
            segments=line_segments_go.segments,
        )
        self.assertEqual(expected_line_segments_go, line_segments_go)

        expected_bounding_box = BoundingBox_V1_0_1(
            min_x=0.005672391805247257,
            max_x=0.9872553481593824,
            min_y=0.013368379306871403,
            max_y=0.9942228529185596,
            min_z=0.009965527049217271,
            max_z=0.9999608574802016,
        )

        self.assertAlmostEqual(expected_bounding_box.min_x, line_segments_go.bounding_box.min_x)
        self.assertAlmostEqual(expected_bounding_box.max_x, line_segments_go.bounding_box.max_x)
        self.assertAlmostEqual(expected_bounding_box.min_y, line_segments_go.bounding_box.min_y)
        self.assertAlmostEqual(expected_bounding_box.max_y, line_segments_go.bounding_box.max_y)
        self.assertAlmostEqual(expected_bounding_box.min_z, line_segments_go.bounding_box.min_z)
        self.assertAlmostEqual(expected_bounding_box.max_z, line_segments_go.bounding_box.max_z)

        vertices_parquet_file = path.join(str(self.data_client.cache_location), line_segments_go.segments.vertices.data)
        indices_parquet_file = path.join(str(self.data_client.cache_location), line_segments_go.segments.indices.data)

        vertices = pq.read_table(vertices_parquet_file)
        indices = pq.read_table(indices_parquet_file)

        self.assertEqual(100, len(vertices))
        self.assertAlmostEqual(vertices["x"][0].as_py(), 0.7432876095822546)
        self.assertAlmostEqual(vertices["y"][0].as_py(), 0.9942228529185596)
        self.assertAlmostEqual(vertices["z"][0].as_py(), 0.938936637513444)

        self.assertEqual(50, len(indices))
        self.assertEqual(indices["n0"][0].as_py(), 86)
        self.assertEqual(indices["n1"][0].as_py(), 48)

    def test_should_convert_omf_v1_lineset_vertex_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/lineset_v1.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        lineset_element = self._element_by_name(project, "data_vertices_lines")

        line_segments_go = convert_omf_lineset(
            lineset=lineset_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(line_segments_go, LineSegments_V2_1_0)

        vertex_attributes = line_segments_go.segments.vertices.attributes
        segment_attributes = line_segments_go.segments.indices.attributes

        self.assertEqual(1, len(vertex_attributes))
        self.assertEqual(0, len(segment_attributes))

        expected_vertex_attributes = [
            ContinuousAttribute_V1_1_0(
                name="data assigned to vertices",
                key=vertex_attributes[0].key,
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=FloatArray1_V1_0_1(
                    data=vertex_attributes[0].values.data, length=100, width=1, data_type="float64"
                ),
                attribute_type="scalar",
            )
        ]
        expected_segment_attributes: list[Any] = []

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_segment_attributes, segment_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), vertex_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(100, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.42185369599561073)
        self.assertAlmostEqual(attribute_data[1].as_py(), 0.40827236099074904)

    def test_should_convert_omf_v2_lineset_vertex_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/lineset_v2.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        lineset_element = self._element_by_name(project, "data_vertices_lines")

        line_segments_go = convert_omf_lineset(
            lineset=lineset_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(line_segments_go, LineSegments_V2_1_0)

        vertex_attributes = line_segments_go.segments.vertices.attributes
        segment_attributes = line_segments_go.segments.indices.attributes

        self.assertEqual(1, len(vertex_attributes))
        self.assertEqual(0, len(segment_attributes))

        expected_vertex_attributes = [
            ContinuousAttribute_V1_1_0(
                name="data assigned to vertices",
                key=vertex_attributes[0].key,
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=FloatArray1_V1_0_1(
                    data=vertex_attributes[0].values.data, length=100, width=1, data_type="float64"
                ),
                attribute_type="scalar",
            )
        ]
        expected_segment_attributes: list[Any] = []

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_segment_attributes, segment_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), vertex_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(100, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.42185369599561073)
        self.assertAlmostEqual(attribute_data[1].as_py(), 0.40827236099074904)

    def test_should_convert_omf_v1_lineset_segment_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/lineset_v1.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        lineset_element = self._element_by_name(project, "data_segments_lines")

        line_segments_go = convert_omf_lineset(
            lineset=lineset_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(line_segments_go, LineSegments_V2_1_0)

        vertex_attributes = line_segments_go.segments.vertices.attributes
        segment_attributes = line_segments_go.segments.indices.attributes

        self.assertEqual(0, len(vertex_attributes))
        self.assertEqual(1, len(segment_attributes))

        expected_vertex_attributes: list[Any] = []
        expected_segment_attributes = [
            ContinuousAttribute_V1_1_0(
                name="data assigned to segments",
                key=segment_attributes[0].key,
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=FloatArray1_V1_0_1(
                    data=segment_attributes[0].values.data, length=50, width=1, data_type="float64"
                ),
                attribute_type="scalar",
            )
        ]

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_segment_attributes, segment_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), segment_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(50, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.6697228903296453)

    def test_should_convert_omf_v2_lineset_segment_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/lineset_v2.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        lineset_element = self._element_by_name(project, "data_segments_lines")

        line_segments_go = convert_omf_lineset(
            lineset=lineset_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(line_segments_go, LineSegments_V2_1_0)

        vertex_attributes = line_segments_go.segments.vertices.attributes
        segment_attributes = line_segments_go.segments.indices.attributes

        self.assertEqual(0, len(vertex_attributes))
        self.assertEqual(1, len(segment_attributes))

        expected_vertex_attributes: list[Any] = []
        expected_segment_attributes = [
            ContinuousAttribute_V1_1_0(
                name="data assigned to segments",
                key=segment_attributes[0].key,
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=FloatArray1_V1_0_1(
                    data=segment_attributes[0].values.data, length=50, width=1, data_type="float64"
                ),
                attribute_type="scalar",
            )
        ]

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_segment_attributes, segment_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), segment_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(50, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.6697228903296453)
