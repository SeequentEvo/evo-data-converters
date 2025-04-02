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

from datetime import date, datetime, timezone
from os import path
from unittest import TestCase

import omf2
import pyarrow as pa

from evo.data_converters.omf import OmfReaderContext
from evo.data_converters.omf.importer.blockmodel.omf_attributes_to_blocksync import convert_blockmodel_attribute
from evo.data_converters.omf.importer.blockmodel.omf_blockmodel_to_blocksync import extract_regular_block_model_columns


class TestConvertBlockModelAttribute(TestCase):
    def test_convert_nullable_boolean_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "../data/null_attribute_values.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        element = project.elements()[0]
        attribute = element.attributes()[6]

        self.assertEqual(attribute.name, "Booleans")
        self.assertIsInstance(attribute.get_data(), omf2.AttributeDataBoolean)

        table = convert_blockmodel_attribute(reader, attribute)

        expected_schema = pa.schema([(attribute.name, pa.bool_())])
        self.assertEqual(expected_schema, table.schema)

        expected_column_names = [attribute.name]
        self.assertEqual(expected_column_names, table.column_names)

        expected_values = [False, True, None, False]
        self.assertEqual(table.columns[0].to_pylist(), expected_values)

    def test_convert_nullable_date_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "../data/null_attribute_values.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        element = project.elements()[0]
        attribute = element.attributes()[3]

        self.assertEqual(attribute.name, "Numbers (Date)")
        self.assertIsInstance(attribute.get_data(), omf2.AttributeDataNumber)

        table = convert_blockmodel_attribute(reader, attribute)

        expected_schema = pa.schema([(attribute.name, pa.date32())])
        self.assertEqual(expected_schema, table.schema)

        expected_column_names = [attribute.name]
        self.assertEqual(expected_column_names, table.column_names)

        expected_values = [date(1995, 5, 1), date(1996, 6, 1), None, date(1998, 8, 1)]
        self.assertEqual(table.columns[0].to_pylist(), expected_values)

    def test_convert_nullable_datetime_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "../data/null_attribute_values.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        element = project.elements()[0]
        attribute = element.attributes()[4]

        self.assertEqual(attribute.name, "Numbers (DateTime)")
        self.assertIsInstance(attribute.get_data(), omf2.AttributeDataNumber)

        table = convert_blockmodel_attribute(reader, attribute)

        expected_schema = pa.schema([(attribute.name, pa.timestamp("us", tz="UTC"))])
        self.assertEqual(expected_schema, table.schema)

        expected_column_names = [attribute.name]
        self.assertEqual(expected_column_names, table.column_names)

        expected_values = [
            datetime(1995, 5, 1, 5, 1, tzinfo=timezone.utc),
            datetime(1996, 6, 1, 6, 1, tzinfo=timezone.utc),
            None,
            datetime(1998, 8, 1, 8, 1, tzinfo=timezone.utc),
        ]
        self.assertEqual(table.columns[0].to_pylist(), expected_values)

    def test_convert_nullable_int64_number_attribute_to_float64(self) -> None:
        omf_file = path.join(path.dirname(__file__), "../data/null_attribute_values.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        element = project.elements()[0]
        attribute = element.attributes()[2]

        self.assertEqual(attribute.name, "Numbers (i64)")
        self.assertIsInstance(attribute.get_data(), omf2.AttributeDataNumber)

        table = convert_blockmodel_attribute(reader, attribute)

        expected_schema = pa.schema([(attribute.name, pa.float64())])
        self.assertEqual(expected_schema, table.schema)

        expected_column_names = [attribute.name]
        self.assertEqual(expected_column_names, table.column_names)

        expected_values = [0.0, 100.0, None, 150.0]
        self.assertEqual(table.columns[0].to_pylist(), expected_values)

    def test_convert_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/rotated_block_model_ijk.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        octree_block_model = project.elements()[0]
        self.assertIsInstance(octree_block_model.geometry(), omf2.BlockModel)

        attribute = octree_block_model.attributes()[0]
        self.assertIsInstance(attribute.get_data(), omf2.AttributeDataNumber)

        table = convert_blockmodel_attribute(reader, attribute)

        unique_column_name = f"data_{attribute.name}"

        expected_schema = pa.schema([(unique_column_name, pa.float64())])
        self.assertEqual(expected_schema, table.schema)

        expected_column_names = [unique_column_name]
        self.assertEqual(expected_column_names, table.column_names)

        expected_values = [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            2.0,
            2.0,
            2.0,
            2.0,
            2.0,
            2.0,
            3.0,
            3.0,
            3.0,
            3.0,
            3.0,
            3.0,
        ]
        self.assertEqual(table.columns[0].to_pylist(), expected_values)

    def test_convert_category_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/bunny_blocks.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        octree_block_model = project.elements()[0]
        self.assertIsInstance(octree_block_model.geometry(), omf2.BlockModel)

        attribute = octree_block_model.attributes()[0]
        self.assertIsInstance(attribute.get_data(), omf2.AttributeDataCategory)

        table = convert_blockmodel_attribute(reader, attribute)

        expected_schema = pa.schema([(attribute.name, pa.utf8())])
        self.assertEqual(expected_schema, table.schema)

        expected_column_names = [attribute.name]
        self.assertEqual(expected_column_names, table.column_names)

        values = table.columns[0].to_pylist()
        self.assertEqual(len(values), 5123)
        self.assertEqual(values[0], "Air")
        self.assertEqual(values[40], "Body")

    def test_should_prevent_duplicate_attribute_column_name(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/bunny_blocks.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        element = project.elements()[0]
        attribute = element.attributes()[0]

        existing_column_names = [attribute.name, f"{attribute.name}_1"]
        table = convert_blockmodel_attribute(reader, attribute, existing_column_names)

        expected_column_names = [f"{attribute.name}_2"]
        self.assertEqual(expected_column_names, table.column_names)

    def test_convert_attributes_with_illegal_column_names(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/rotated_block_model_ijk.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        block_model = project.elements()[0]
        attr = block_model.attributes()[0]
        self.assertIsInstance(attr.get_data(), omf2.AttributeDataNumber)

        table = extract_regular_block_model_columns(block_model, reader)
        self.assertIsInstance(table, pa.Table)

        expected_columns = ["i", "j", "k", "data_i", "data_j", "data_k", "index"]
        self.assertEqual(expected_columns, table.column_names)

        expected_schema = pa.schema(
            [
                ("i", pa.uint32()),
                ("j", pa.uint32()),
                ("k", pa.uint32()),
                ("data_i", pa.float64()),
                ("data_j", pa.float64()),
                ("data_k", pa.float64()),
                ("index", pa.float64()),
            ]
        )
        self.assertEqual(expected_schema, table.schema)
