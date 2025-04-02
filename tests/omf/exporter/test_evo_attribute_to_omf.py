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
from datetime import datetime, timezone
from os import path
from typing import Any
from unittest import TestCase
from uuid import uuid4

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from evo_schemas.components import (
    AttributeDescription_V1_0_1,
    CategoryAttribute_V1_1_0,
    ColorAttribute_V1_1_0,
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_1_0,
    IntegerAttribute_V1_1_0,
    StringAttribute_V1_1_0,
    VectorAttribute_V1_0_0,
)
from evo_schemas.elements import UnitDimensionless_V1_0_1_UnitCategories
from evo_schemas.objects import LineSegments_V2_1_0, Pointset_V1_2_0, TriangleMesh_V2_1_0
from omf.data import (
    ColorData,
    DateTimeArray,
    DateTimeData,
    Legend,
    MappedData,
    ScalarData,
    StringData,
    Vector2Array,
    Vector2Data,
    Vector3Array,
    Vector3Data,
)

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.omf.exporter import export_attribute_to_omf
from evo.data_converters.omf.importer import convert_omf
from evo.data_converters.omf.importer.omf_attributes_to_evo import int_to_rgba


class TestOmfAttributeExporter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.workspace_metadata = EvoWorkspaceMetadata(workspace_id=str(uuid4()), cache_root=self.cache_root_dir.name)

        _, self.data_client = create_evo_object_service_and_data_client(self.workspace_metadata)

        # Convert an OMF file to Evo and use the generated Parquet files to test the exporter
        omf_file = path.join(path.dirname(__file__), "../data/one_of_everything.omf")
        self.evo_objects = convert_omf(
            filepath=omf_file, evo_workspace_metadata=self.workspace_metadata, epsg_code=32650
        )

    def _set_parquet_file_value(self, data: str, row_index: int, value: Any) -> None:
        parquet_file = path.join(str(self.data_client.cache_location), data)

        table = pq.read_table(parquet_file)

        df = table.to_pandas()
        df.loc[row_index] = value

        table = pa.Table.from_pandas(df, table.schema)

        pq.write_table(table, parquet_file)

    def test_should_convert_continuous_attribute_to_scalar_data(self) -> None:
        triangle_mesh_go = self.evo_objects[0]
        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        attribute_go = triangle_mesh_go.triangles.vertices.attributes[0]
        self.assertIsInstance(attribute_go, ContinuousAttribute_V1_1_0)

        # Test handling a null value
        self._set_parquet_file_value(attribute_go.values.data, 0, None)

        # Test handling nan_description
        attribute_go.nan_description.values = [-999.0, -1234.0]
        self._set_parquet_file_value(attribute_go.values.data, 1, -999.0)

        location = "vertices"
        string_description = "NaN values: [-999.0, -1234.0]"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, ScalarData)

        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
        self.assertEqual(string_description, omf_element_data.description)

        numbers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        numbers = pq.read_table(numbers_parquet_file)

        expected_count = 5

        self.assertEqual(len(numbers), expected_count)
        self.assertEqual(len(omf_element_data.array), expected_count)

        numbers_list = numbers[0].to_pylist()

        # Null value converted to NaN
        self.assertEqual(numbers_list[0], None)
        self.assertTrue(np.isnan(omf_element_data.array[0]))

        # Value matching nan_description set to NaN
        self.assertEqual(numbers_list[1], attribute_go.nan_description.values[0])
        self.assertTrue(np.isnan(omf_element_data.array[1]))

        for i in range(2, expected_count - 1):
            self.assertAlmostEqual(numbers_list[i], omf_element_data.array[i])

        # Null value converted to NaN
        self.assertEqual(numbers_list[expected_count - 1], None)
        self.assertTrue(np.isnan(omf_element_data.array[expected_count - 1]))

    def test_should_convert_color_attribute_to_color_data(self) -> None:
        triangle_mesh_go = self.evo_objects[0]
        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        attribute_go = triangle_mesh_go.triangles.indices.attributes[0]
        self.assertIsInstance(attribute_go, ColorAttribute_V1_1_0)

        # Test handling a null value
        self._set_parquet_file_value(attribute_go.values.data, 0, None)

        location = "faces"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, ColorData)

        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
        self.assertEqual("", omf_element_data.description)

        colors_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        colors = pq.read_table(colors_parquet_file)

        expected_count = 6

        self.assertEqual(len(colors), expected_count)
        self.assertEqual(len(omf_element_data.array), expected_count)

        # Null value converted to expected substitute color
        self.assertEqual(colors[0][0].as_py(), None)
        self.assertListEqual(omf_element_data.array[0].tolist(), [0, 0, 0])

        expected_color_components = 3
        self.assertEqual(len(omf_element_data.array[1]), expected_color_components)

        expected_color = [255, 255, 0]
        self.assertListEqual(omf_element_data.array[1].tolist(), expected_color)

        remaining_colors = colors[0][1:]
        remaining_colors_list = [int_to_rgba(color.as_py())[:3] for color in remaining_colors]
        for i in range(1, expected_count):
            self.assertListEqual(remaining_colors_list[i - 1], omf_element_data.array[i].tolist())

    def test_should_convert_category_attribute_to_mapped_data(self) -> None:
        pointset_go = self.evo_objects[1]
        self.assertIsInstance(pointset_go, Pointset_V1_2_0)

        attribute_go = pointset_go.locations.attributes[0]
        self.assertIsInstance(attribute_go, CategoryAttribute_V1_1_0)

        # Test handling nan_description
        attribute_go.nan_description.values = [-999, -1234]
        self._set_parquet_file_value(attribute_go.values.data, 1, -999)

        # Test handling a null value
        self._set_parquet_file_value(attribute_go.values.data, 0, None)

        location = "vertices"
        string_description = "NaN values: [-999, -1234]"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, MappedData)

        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
        self.assertEqual(string_description, omf_element_data.description)

        # Should have the expected indices
        values_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        values = pq.read_table(values_parquet_file)

        expected_count = 5

        self.assertEqual(len(values), expected_count)
        self.assertEqual(len(omf_element_data.array), expected_count)

        values_list = values[0].to_pylist()

        # Null value indices should be converted to -1
        self.assertEqual(values_list[0], None)
        self.assertEqual(omf_element_data.array[0], -1)

        # value indices matching nan_description should be converted to -1
        self.assertEqual(values_list[1], attribute_go.nan_description.values[0])
        self.assertEqual(omf_element_data.array[1], -1)

        for i in range(2, expected_count):
            self.assertEqual(values_list[i], omf_element_data.array[i])

        # Should have the expected legend key/value mapping
        self.assertEqual(len(omf_element_data.legends), 1)

        legend = omf_element_data.legends[0]
        self.assertIsInstance(legend, Legend)

        key_value_table_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.table.data)
        key_value_table = pq.read_table(key_value_table_parquet_file)

        self.assertEqual(len(key_value_table["key"]), 2)
        self.assertEqual(len(key_value_table["value"]), 2)
        self.assertEqual(len(legend.values), 2)

        table_key_list = key_value_table["key"].to_pylist()
        self.assertEqual(table_key_list[0], 0)
        self.assertEqual(table_key_list[1], 1)

        table_value_list = key_value_table["value"].to_pylist()
        self.assertEqual(table_value_list[0], legend.values[0])
        self.assertEqual(table_value_list[1], legend.values[1])

    def test_should_convert_integer_attribute_to_scalar_data(self) -> None:
        omf_file = path.join(path.dirname(__file__), "../data/null_attribute_values.omf")
        evo_objects = convert_omf(filepath=omf_file, evo_workspace_metadata=self.workspace_metadata, epsg_code=32650)

        triangle_mesh_go = evo_objects[0]
        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        attribute_go = triangle_mesh_go.triangles.vertices.attributes[2]
        self.assertIsInstance(attribute_go, IntegerAttribute_V1_1_0)

        # Test handling nan_description
        attribute_go.nan_description.values = [-999.0, -1234.0]
        self._set_parquet_file_value(attribute_go.values.data, 1, -999.0)

        location = "vertices"
        string_description = "NaN values: [-999.0, -1234.0]"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, ScalarData)

        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
        self.assertEqual(string_description, omf_element_data.description)

        integers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        integers = pq.read_table(integers_parquet_file)

        expected_count = 4

        self.assertEqual(len(integers), expected_count)
        self.assertEqual(len(omf_element_data.array), expected_count)
        self.assertIsInstance(omf_element_data.array[0], np.int64)

        integers_list = integers[0].to_pylist()

        expected_null_value = -9223372036854775807
        expected_values = [expected_null_value if i is None else i for i in integers_list]
        self.assertEqual(expected_values, list(omf_element_data.array))

    def test_should_convert_string_attribute_to_string_data(self) -> None:
        line_segments_go = self.evo_objects[2]
        self.assertIsInstance(line_segments_go, LineSegments_V2_1_0)

        attribute_go = line_segments_go.segments.indices.attributes[0]
        self.assertIsInstance(attribute_go, StringAttribute_V1_1_0)

        location = "segments"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, StringData)

        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
        self.assertEqual("", omf_element_data.description)

        strings_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        strings = pq.read_table(strings_parquet_file)

        expected_count = 8

        self.assertEqual(len(strings), expected_count)
        self.assertEqual(len(omf_element_data.array), expected_count)

        strings_list = strings[0].to_pylist()
        for i in range(expected_count):
            # None gets converted to an empty string
            self.assertEqual("" if strings_list[i] is None else strings_list[i], omf_element_data.array[i])

    def test_should_convert_2d_vector_attribute_to_vector2_data(self) -> None:
        pointset_go = self.evo_objects[1]
        self.assertIsInstance(pointset_go, Pointset_V1_2_0)

        attribute_go = pointset_go.locations.attributes[1]
        self.assertIsInstance(attribute_go, VectorAttribute_V1_0_0)

        # Test handling nan_description
        attribute_go.nan_description.values = [-999.0, -1234.0]
        self._set_parquet_file_value(attribute_go.values.data, 3, -999.0)

        location = "vertices"
        string_description = "NaN values: [-999.0, -1234.0]"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, Vector2Data)

        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
        self.assertEqual(string_description, omf_element_data.description)

        vectors_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        vectors = pq.read_table(vectors_parquet_file)

        expected_count = 5

        self.assertEqual(len(vectors), expected_count)
        self.assertEqual(len(omf_element_data.array), expected_count)

        self.assertIsInstance(omf_element_data.array, Vector2Array)

        for i in range(expected_count - 2):
            self.assertAlmostEqual(vectors[0][i].as_py(), omf_element_data.array[i][0])
            self.assertAlmostEqual(vectors[1][i].as_py(), omf_element_data.array[i][1])

        # Value matching nan_description set to NaN
        self.assertEqual(vectors[0][3].as_py(), -999.0)
        self.assertEqual(vectors[1][3].as_py(), -999.0)
        self.assertTrue(np.isnan(omf_element_data.array[3][0]))
        self.assertTrue(np.isnan(omf_element_data.array[3][1]))

        # Null value converted to NaN
        self.assertEqual(vectors[0][4].as_py(), None)
        self.assertEqual(vectors[1][4].as_py(), None)
        self.assertTrue(np.isnan(omf_element_data.array[4][0]))
        self.assertTrue(np.isnan(omf_element_data.array[4][1]))

    def test_should_convert_3d_vector_attribute_to_vector3_data(self) -> None:
        pointset_go = self.evo_objects[1]
        self.assertIsInstance(pointset_go, Pointset_V1_2_0)

        attribute_go = pointset_go.locations.attributes[2]
        self.assertIsInstance(attribute_go, VectorAttribute_V1_0_0)

        # Test handling nan_description
        attribute_go.nan_description.values = [-999.0, -1234.0]
        self._set_parquet_file_value(attribute_go.values.data, 1, -999.0)

        location = "vertices"
        string_description = "NaN values: [-999.0, -1234.0]"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, Vector3Data)

        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
        self.assertEqual(string_description, omf_element_data.description)

        vectors_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        vectors = pq.read_table(vectors_parquet_file)

        expected_count = 5

        self.assertEqual(len(vectors), expected_count)
        self.assertEqual(len(omf_element_data.array), expected_count)

        self.assertIsInstance(omf_element_data.array, Vector3Array)

        # Null value converted to NaN
        self.assertEqual(vectors[0][0].as_py(), None)
        self.assertEqual(vectors[1][0].as_py(), None)
        self.assertEqual(vectors[2][0].as_py(), None)
        self.assertTrue(np.isnan(omf_element_data.array[0][0]))
        self.assertTrue(np.isnan(omf_element_data.array[0][1]))
        self.assertTrue(np.isnan(omf_element_data.array[0][2]))

        # Value matching nan_description set to NaN
        self.assertEqual(vectors[0][1].as_py(), -999.0)
        self.assertEqual(vectors[1][1].as_py(), -999.0)
        self.assertEqual(vectors[2][1].as_py(), -999.0)
        self.assertTrue(np.isnan(omf_element_data.array[1][0]))
        self.assertTrue(np.isnan(omf_element_data.array[1][1]))
        self.assertTrue(np.isnan(omf_element_data.array[1][2]))

        # Converts regular value
        self.assertAlmostEqual(vectors[0][-1].as_py(), omf_element_data.array[-1][0])
        self.assertAlmostEqual(vectors[1][-1].as_py(), omf_element_data.array[-1][1])
        self.assertAlmostEqual(vectors[2][-1].as_py(), omf_element_data.array[-1][2])

    def test_should_convert_datetime_attribute_to_datetime_data(self) -> None:
        triangle_mesh_go = self.evo_objects[0]
        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        attribute_go = triangle_mesh_go.triangles.vertices.attributes[1]
        self.assertIsInstance(attribute_go, DateTimeAttribute_V1_1_0)

        # Test handling a null value
        self._set_parquet_file_value(attribute_go.values.data, 0, None)

        # Test handling nan_description
        attribute_go.nan_description.values = [-999, -1234]
        self._set_parquet_file_value(attribute_go.values.data, 1, -999)

        location = "vertices"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)
        self.assertIsInstance(omf_element_data, DateTimeData)
        self.assertIsInstance(omf_element_data.array, DateTimeArray)

        expected_null_datetime_value = datetime(1, 1, 1, 0, 0, tzinfo=timezone.utc)
        expected_nan_datetime_value = pa.scalar(
            attribute_go.nan_description.values[0], type=pa.timestamp("us", tz="UTC")
        ).as_py()

        expected_datetimes = [
            expected_null_datetime_value,
            expected_nan_datetime_value,
            datetime(2000, 1, 1, 2, 0, tzinfo=timezone.utc),
            datetime(2000, 1, 1, 3, 0, tzinfo=timezone.utc),
            datetime(2000, 1, 1, 4, 0, tzinfo=timezone.utc),
        ]

        string_description = "NaN values: [-999, -1234]"
        self.assertListEqual(expected_datetimes, list(omf_element_data.array))
        self.assertEqual(string_description, omf_element_data.description)

    def test_should_convert_attribute_description_to_string(self) -> None:
        triangle_mesh_go = self.evo_objects[0]
        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        attribute_go = triangle_mesh_go.triangles.vertices.attributes[0]
        self.assertIsInstance(attribute_go, ContinuousAttribute_V1_1_0)

        # Test handling nan_description
        attribute_go.nan_description.values = [-999, -1234]

        # Test handling attribute description
        attribute_go.attribute_description = AttributeDescription_V1_0_1(
            discipline="Geotechnical",
            type="Gold",
            unit=UnitDimensionless_V1_0_1_UnitCategories.Unit_ct_per_t.value,
            scale="log10",
            extensions=None,
            tags={"color": "red-yellow", "alloy": "true"},
        )
        string_description = "discipline: Geotechnical, type: Gold, unit: ct/t, scale: log10, tags: {'color': 'red-yellow', 'alloy': 'true'}, NaN values: [-999, -1234]"
        location = "vertices"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)

        self.assertEqual(omf_element_data.description, string_description)
        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)

    def test_should_convert_only_attribute_description_to_string(self) -> None:
        triangle_mesh_go = self.evo_objects[0]
        self.assertIsInstance(triangle_mesh_go, TriangleMesh_V2_1_0)

        attribute_go = triangle_mesh_go.triangles.vertices.attributes[0]
        self.assertIsInstance(attribute_go, ContinuousAttribute_V1_1_0)

        # Test handling attribute description
        attribute_go.attribute_description = AttributeDescription_V1_0_1(
            discipline="Geotechnical",
            type="Gold",
        )
        string_description = "discipline: Geotechnical, type: Gold"
        location = "vertices"
        omf_element_data = export_attribute_to_omf(uuid4(), None, attribute_go, location, self.data_client)

        self.assertEqual(omf_element_data.description, string_description)
        self.assertEqual(attribute_go.name, omf_element_data.name)
        self.assertEqual(location, omf_element_data.location)
