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
from evo_schemas.objects import TriangleMesh_V2_1_0

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    crs_from_epsg_code,
)

from evo.data_converters.omf import OMFReaderContext
from evo.data_converters.omf.importer import convert_omf_surface


class TestOMFSurfaceConverter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
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

    def test_should_convert_omf_v2_surface_mesh_geometry(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/surface_v2.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        surface_element = self._element_by_name(project, "surf_diff_origin")

        epsg_code = 32650
        triangle_mesh_go = convert_omf_surface(
            surface=surface_element, project=project, reader=reader, data_client=self.data_client, epsg_code=epsg_code
        )

        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        expected_triangle_mesh_go = TriangleMesh_V2_1_0(
            name=surface_element.name,
            uuid=None,
            coordinate_reference_system=crs_from_epsg_code(epsg_code),
            bounding_box=triangle_mesh_go.bounding_box,
            triangles=triangle_mesh_go.triangles,
        )
        self.assertEqual(expected_triangle_mesh_go, triangle_mesh_go)

        expected_bounding_box = BoundingBox_V1_0_1(
            min_x=50.00547086013213,
            max_x=50.96011655638242,
            min_y=50.014342382938956,
            max_y=50.992925785006996,
            min_z=50.01871760038497,
            max_z=50.99999916415145,
        )
        self.assertAlmostEqual(expected_bounding_box.min_x, triangle_mesh_go.bounding_box.min_x)
        self.assertAlmostEqual(expected_bounding_box.max_x, triangle_mesh_go.bounding_box.max_x)
        self.assertAlmostEqual(expected_bounding_box.min_y, triangle_mesh_go.bounding_box.min_y)
        self.assertAlmostEqual(expected_bounding_box.max_y, triangle_mesh_go.bounding_box.max_y)
        self.assertAlmostEqual(expected_bounding_box.min_z, triangle_mesh_go.bounding_box.min_z)
        self.assertAlmostEqual(expected_bounding_box.max_z, triangle_mesh_go.bounding_box.max_z)

        vertices_parquet_file = path.join(
            str(self.data_client.cache_location), triangle_mesh_go.triangles.vertices.data
        )
        indices_parquet_file = path.join(str(self.data_client.cache_location), triangle_mesh_go.triangles.indices.data)

        vertices = pq.read_table(vertices_parquet_file)
        indices = pq.read_table(indices_parquet_file)

        self.assertEqual(100, len(vertices))
        self.assertAlmostEqual(vertices["x"][0].as_py(), 50.45146572880054)
        self.assertAlmostEqual(vertices["y"][0].as_py(), 50.90627357351534)
        self.assertAlmostEqual(vertices["z"][0].as_py(), 50.97926144947899)

        self.assertEqual(50, len(indices))
        self.assertEqual(indices["x"][0].as_py(), 16)
        self.assertEqual(indices["y"][0].as_py(), 98)
        self.assertEqual(indices["z"][0].as_py(), 44)

    def test_should_convert_omf_v1_surface_mesh_geometry(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/surface_v1.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        surface_element = self._element_by_name(project, "surf_diff_origin")

        epsg_code = 32650
        triangle_mesh_go = convert_omf_surface(
            surface=surface_element, project=project, reader=reader, data_client=self.data_client, epsg_code=epsg_code
        )

        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        expected_triangle_mesh_go = TriangleMesh_V2_1_0(
            name=surface_element.name,
            uuid=None,
            coordinate_reference_system=crs_from_epsg_code(epsg_code),
            bounding_box=triangle_mesh_go.bounding_box,
            triangles=triangle_mesh_go.triangles,
        )
        self.assertEqual(expected_triangle_mesh_go, triangle_mesh_go)

        expected_bounding_box = BoundingBox_V1_0_1(
            min_x=50.00547086013213,
            max_x=50.96011655638242,
            min_y=50.014342382938956,
            max_y=50.992925785006996,
            min_z=50.01871760038497,
            max_z=50.99999916415145,
        )
        self.assertAlmostEqual(expected_bounding_box.min_x, triangle_mesh_go.bounding_box.min_x)
        self.assertAlmostEqual(expected_bounding_box.max_x, triangle_mesh_go.bounding_box.max_x)
        self.assertAlmostEqual(expected_bounding_box.min_y, triangle_mesh_go.bounding_box.min_y)
        self.assertAlmostEqual(expected_bounding_box.max_y, triangle_mesh_go.bounding_box.max_y)
        self.assertAlmostEqual(expected_bounding_box.min_z, triangle_mesh_go.bounding_box.min_z)
        self.assertAlmostEqual(expected_bounding_box.max_z, triangle_mesh_go.bounding_box.max_z)

        vertices_parquet_file = path.join(
            str(self.data_client.cache_location), triangle_mesh_go.triangles.vertices.data
        )
        indices_parquet_file = path.join(str(self.data_client.cache_location), triangle_mesh_go.triangles.indices.data)

        vertices = pq.read_table(vertices_parquet_file)
        indices = pq.read_table(indices_parquet_file)

        self.assertEqual(100, len(vertices))
        self.assertAlmostEqual(vertices["x"][0].as_py(), 50.45146572880054)
        self.assertAlmostEqual(vertices["y"][0].as_py(), 50.90627357351534)
        self.assertAlmostEqual(vertices["z"][0].as_py(), 50.97926144947899)

        self.assertEqual(50, len(indices))
        self.assertEqual(indices["x"][0].as_py(), 16)
        self.assertEqual(indices["y"][0].as_py(), 98)
        self.assertEqual(indices["z"][0].as_py(), 44)

    def test_should_convert_omf_v2_surface_vertex_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/surface_v2.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        surface_element = self._element_by_name(project, "data_vertices_surf")

        triangle_mesh_go = convert_omf_surface(
            surface=surface_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        vertex_attributes = triangle_mesh_go.triangles.vertices.attributes
        triangle_attributes = triangle_mesh_go.triangles.indices.attributes

        self.assertEqual(1, len(vertex_attributes))
        self.assertEqual(0, len(triangle_attributes))

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
        expected_triangle_attributes: list[Any] = []

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_triangle_attributes, triangle_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), vertex_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(100, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.0672726158214969)
        self.assertAlmostEqual(attribute_data[1].as_py(), 0.2599138842960207)
        self.assertAlmostEqual(attribute_data[2].as_py(), 0.09821341379793103)

    def test_should_convert_omf_v2_surface_face_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/surface_v2.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        surface_element = self._element_by_name(project, "data_faces_surf")

        triangle_mesh_go = convert_omf_surface(
            surface=surface_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        vertex_attributes = triangle_mesh_go.triangles.vertices.attributes
        triangle_attributes = triangle_mesh_go.triangles.indices.attributes

        self.assertEqual(0, len(vertex_attributes))
        self.assertEqual(1, len(triangle_attributes))

        expected_vertex_attributes: list[Any] = []
        expected_triangle_attributes = [
            ContinuousAttribute_V1_1_0(
                name="data assigned to faces",
                key=triangle_attributes[0].key,
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=FloatArray1_V1_0_1(
                    data=triangle_attributes[0].values.data, length=50, width=1, data_type="float64"
                ),
                attribute_type="scalar",
            ),
        ]

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_triangle_attributes, triangle_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), triangle_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(50, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.3021922825282952)

    def test_should_convert_omf_v1_surface_vertex_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/surface_v1.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        surface_element = self._element_by_name(project, "data_vertices_surf")

        triangle_mesh_go = convert_omf_surface(
            surface=surface_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        vertex_attributes = triangle_mesh_go.triangles.vertices.attributes
        triangle_attributes = triangle_mesh_go.triangles.indices.attributes

        self.assertEqual(1, len(vertex_attributes))
        self.assertEqual(0, len(triangle_attributes))

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
        expected_triangle_attributes: list[Any] = []

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_triangle_attributes, triangle_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), vertex_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(100, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.0672726158214969)
        self.assertAlmostEqual(attribute_data[1].as_py(), 0.2599138842960207)
        self.assertAlmostEqual(attribute_data[2].as_py(), 0.09821341379793103)

    def test_should_convert_omf_v1_surface_face_attributes(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/surface_v1.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        surface_element = self._element_by_name(project, "data_faces_surf")

        triangle_mesh_go = convert_omf_surface(
            surface=surface_element, project=project, reader=reader, data_client=self.data_client, epsg_code=32650
        )

        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        vertex_attributes = triangle_mesh_go.triangles.vertices.attributes
        triangle_attributes = triangle_mesh_go.triangles.indices.attributes

        self.assertEqual(0, len(vertex_attributes))
        self.assertEqual(1, len(triangle_attributes))

        expected_vertex_attributes: list[Any] = []
        expected_triangle_attributes = [
            ContinuousAttribute_V1_1_0(
                name="data assigned to faces",
                key=triangle_attributes[0].key,
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=FloatArray1_V1_0_1(
                    data=triangle_attributes[0].values.data, length=50, width=1, data_type="float64"
                ),
                attribute_type="scalar",
            ),
        ]

        self.assertListEqual(expected_vertex_attributes, vertex_attributes)
        self.assertListEqual(expected_triangle_attributes, triangle_attributes)

        attribute_parquet_file = path.join(str(self.data_client.cache_location), triangle_attributes[0].values.data)
        attribute_data = pq.read_table(attribute_parquet_file)["data"]

        self.assertEqual(50, len(attribute_data))
        self.assertAlmostEqual(attribute_data[0].as_py(), 0.3021922825282952)
