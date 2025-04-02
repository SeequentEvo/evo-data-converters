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
from unittest import TestCase

import omf2
import pyarrow.parquet as pq
from evo_schemas.components import (
    BoolAttribute_V1_1_0,
    CategoryAttribute_V1_1_0,
    ColorAttribute_V1_1_0,
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_1_0,
    IntegerAttribute_V1_1_0,
    NanCategorical_V1_0_1,
    NanContinuous_V1_0_1,
    StringAttribute_V1_1_0,
    VectorAttribute_V1_0_0,
)
from evo_schemas.elements import (
    BoolArray1_V1_0_1,
    ColorArray_V1_0_1,
    DateTimeArray_V1_0_1,
    FloatArray1_V1_0_1,
    FloatArrayMd_V1_0_1,
    IntegerArray1_V1_0_1,
    LookupTable_V1_0_1,
    StringArray_V1_0_1,
)

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.omf import OmfReaderContext
from evo.data_converters.omf.importer.omf_attributes_to_evo import (
    convert_omf_attribute,
    int_to_rgba,
    int_to_rgba_optional,
    rgba_to_int,
)


class TestOmfAttributeConverter(TestCase):
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

    def test_should_convert_omf_v2_datetime_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Pyramid surface")

        datetime_attribute = element.attributes()[2]
        self.assertIsInstance(datetime_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(datetime_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, DateTimeAttribute_V1_1_0)

        expected_attribute = DateTimeAttribute_V1_1_0(
            name=datetime_attribute.name,
            key=attribute_go.key,
            values=DateTimeArray_V1_0_1(data=attribute_go.values.data, length=5),
            nan_description=NanCategorical_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        datetimes_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        datetimes = pq.read_table(datetimes_parquet_file)

        expected_datetimes = [
            datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2000, 1, 1, 1, 0, tzinfo=timezone.utc),
            datetime(2000, 1, 1, 2, 0, tzinfo=timezone.utc),
            datetime(2000, 1, 1, 3, 0, tzinfo=timezone.utc),
            datetime(2000, 1, 1, 4, 0, tzinfo=timezone.utc),
        ]
        self.assertEqual(expected_datetimes, datetimes.column("data").to_pylist())

    def test_should_convert_omf_v2_f64_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/continuous_colormap.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Test Surface")

        number_attribute = element.attributes()[0]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, ContinuousAttribute_V1_1_0)

        expected_attribute = ContinuousAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=FloatArray1_V1_0_1(data=attribute_go.values.data, length=4, data_type="float64"),
            nan_description=NanContinuous_V1_0_1(values=[]),
            attribute_type="scalar",
        )
        self.assertEqual(expected_attribute, attribute_go)

        numbers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        numbers = pq.read_table(numbers_parquet_file)

        expected_numbers = [0.0, 1.0, 2.0, 1.5]
        self.assertEqual(expected_numbers, numbers.column("data").to_pylist())

    def test_should_convert_omf_v2_date_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/continuous_colormap.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Test Surface")

        date_attribute = element.attributes()[1]
        self.assertIsInstance(date_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(date_attribute, reader, self.data_client)

        # Evo lacks a type to represent Dates, so they get converted to strings
        # of the form “YYYY-MM-DD”.
        self.assertIsInstance(attribute_go, StringAttribute_V1_1_0)

        expected_attribute = StringAttribute_V1_1_0(
            name=date_attribute.name,
            key=attribute_go.key,
            values=StringArray_V1_0_1(data=attribute_go.values.data, length=4),
        )
        self.assertEqual(expected_attribute, attribute_go)

        dates_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        dates = pq.read_table(dates_parquet_file)

        expected_dates = [
            "1995-05-01",
            "1996-06-01",
            "1997-07-01",
            "1998-08-01",
        ]
        self.assertEqual(expected_dates, dates.column("data").to_pylist())

    def test_should_convert_omf_v2_f32_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/continuous_colormap.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Test Surface")

        number_attribute = element.attributes()[3]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, ContinuousAttribute_V1_1_0)

        expected_attribute = ContinuousAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=FloatArray1_V1_0_1(data=attribute_go.values.data, length=4, data_type="float64"),
            nan_description=NanContinuous_V1_0_1(values=[]),
            attribute_type="scalar",
        )
        self.assertEqual(expected_attribute, attribute_go)

        numbers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        numbers = pq.read_table(numbers_parquet_file)

        expected_numbers = [0.0, 1.0, 2.0, 1.5]
        self.assertEqual(expected_numbers, numbers.column("data").to_pylist())

    def test_should_convert_omf_v2_i64_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/continuous_colormap.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Test Surface")

        number_attribute = element.attributes()[4]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, IntegerAttribute_V1_1_0)

        expected_attribute = IntegerAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=IntegerArray1_V1_0_1(data=attribute_go.values.data, length=4, data_type="int64"),
            nan_description=NanCategorical_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        numbers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        numbers = pq.read_table(numbers_parquet_file)

        expected_numbers = [0, 100, 200, 150]
        self.assertEqual(expected_numbers, numbers.column("data").to_pylist())

    def test_should_convert_omf_v2_category_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Pyramid points")

        category_attribute = element.attributes()[0]
        self.assertIsInstance(category_attribute.get_data(), omf2.AttributeDataCategory)

        attribute_go = convert_omf_attribute(category_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, CategoryAttribute_V1_1_0)
        expected_attribute = CategoryAttribute_V1_1_0(
            name=category_attribute.name,
            key=attribute_go.key,
            table=LookupTable_V1_0_1(data=attribute_go.table.data, keys_data_type="int64", length=2),
            values=IntegerArray1_V1_0_1(data=attribute_go.values.data, data_type="int64", length=5),
            nan_description=NanCategorical_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        lookup_table_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.table.data)
        lookup_table = pq.read_table(lookup_table_parquet_file).to_pydict()

        expected_lookup_table = {"key": [0, 1], "value": ["Base", "Top"]}
        self.assertDictEqual(expected_lookup_table, lookup_table)

        values_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        values = pq.read_table(values_parquet_file)

        expected_values = [0, 0, 0, 0, 1]
        self.assertEqual(expected_values, values.column("data").to_pylist())

    def test_should_convert_omf_v2_text_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Pyramid lines")

        text_attribute = element.attributes()[0]
        self.assertIsInstance(text_attribute.get_data(), omf2.AttributeDataText)

        attribute_go = convert_omf_attribute(text_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, StringAttribute_V1_1_0)

        expected_attribute = StringAttribute_V1_1_0(
            name=text_attribute.name,
            key=attribute_go.key,
            values=StringArray_V1_0_1(data=attribute_go.values.data, length=8),
        )
        self.assertEqual(expected_attribute, attribute_go)

        strings_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        strings = pq.read_table(strings_parquet_file)

        expected_strings = [None, None, None, None, "sw", "se", "ne", "nw"]
        self.assertEqual(expected_strings, strings.column("data").to_pylist())

    def test_should_convert_omf_v2_boolean_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Regular block model")

        boolean_attribute = element.attributes()[0]
        self.assertIsInstance(boolean_attribute.get_data(), omf2.AttributeDataBoolean)

        attribute_go = convert_omf_attribute(boolean_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, BoolAttribute_V1_1_0)

        expected_attribute = BoolAttribute_V1_1_0(
            name=boolean_attribute.name,
            key=attribute_go.key,
            values=BoolArray1_V1_0_1(data=attribute_go.values.data, length=8),
        )
        self.assertEqual(expected_attribute, attribute_go)

        booleans_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        booleans = pq.read_table(booleans_parquet_file)

        expected_booleans = [False, False, False, False, False, False, False, True]
        self.assertEqual(expected_booleans, booleans.column("data").to_pylist())

    def test_int_to_rgba(self) -> None:
        color_int = int("0x04030201", 16)
        expected_rgba = [1, 2, 3, 4]
        self.assertEqual(expected_rgba, int_to_rgba(color_int))

    def test_rgba_to_int(self) -> None:
        rgba = [1, 2, 3, 4]
        expected_int = int("0x04030201", 16)
        self.assertEqual(expected_int, rgba_to_int(rgba))

    def test_should_convert_omf_v2_color_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Pyramid surface")

        color_attribute = element.attributes()[1]
        self.assertIsInstance(color_attribute.get_data(), omf2.AttributeDataColor)

        attribute_go = convert_omf_attribute(color_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, ColorAttribute_V1_1_0)

        expected_attribute = ColorAttribute_V1_1_0(
            name=color_attribute.name,
            key=attribute_go.key,
            values=ColorArray_V1_0_1(data=attribute_go.values.data, length=6),
        )
        self.assertEqual(expected_attribute, attribute_go)

        colors_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        uint32_colors = pq.read_table(colors_parquet_file)

        rgba_colors = [int_to_rgba_optional(color) for color in uint32_colors.column("data").to_pylist()]

        expected_rgba_colors = [
            [255, 0, 0, 255],
            [255, 255, 0, 255],
            [0, 255, 0, 255],
            [0, 0, 255, 255],
            [255, 255, 255, 255],
            [255, 255, 255, 255],
        ]

        self.assertEqual(expected_rgba_colors, rgba_colors)

    def test_should_convert_omf_v2_null_f32_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        number_attribute = (self._element_by_name(project, "Test Surface")).attributes()[0]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)
        self.assertIsInstance(attribute_go, ContinuousAttribute_V1_1_0)

        expected_attribute = ContinuousAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=FloatArray1_V1_0_1(data=attribute_go.values.data, length=4, data_type="float64"),
            nan_description=NanContinuous_V1_0_1(values=[]),
            attribute_type="scalar",
        )
        self.assertEqual(expected_attribute, attribute_go)

        numbers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        numbers = pq.read_table(numbers_parquet_file)

        expected_numbers = [0.0, 1.0, None, 1.5]
        self.assertEqual(expected_numbers, numbers.column("data").to_pylist())

    def test_should_convert_omf_v2_null_f64_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        number_attribute = (self._element_by_name(project, "Test Surface")).attributes()[1]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)
        self.assertIsInstance(attribute_go, ContinuousAttribute_V1_1_0)

        expected_attribute = ContinuousAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=FloatArray1_V1_0_1(data=attribute_go.values.data, length=4, data_type="float64"),
            nan_description=NanContinuous_V1_0_1(values=[]),
            attribute_type="scalar",
        )
        self.assertEqual(expected_attribute, attribute_go)

        numbers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        numbers = pq.read_table(numbers_parquet_file)

        expected_numbers = [0.0, 1.0, None, 1.5]
        self.assertEqual(expected_numbers, numbers.column("data").to_pylist())

    def test_should_convert_omf_v2_null_i64_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        number_attribute = (self._element_by_name(project, "Test Surface")).attributes()[2]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)
        self.assertIsInstance(attribute_go, IntegerAttribute_V1_1_0)

        expected_attribute = IntegerAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=IntegerArray1_V1_0_1(data=attribute_go.values.data, length=4, data_type="int64"),
            nan_description=NanCategorical_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        numbers_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        numbers = pq.read_table(numbers_parquet_file)

        expected_numbers = [0, 100, None, 150]
        self.assertEqual(expected_numbers, numbers.column("data").to_pylist())

    def test_should_convert_omf_v2_null_date_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        number_attribute = (self._element_by_name(project, "Test Surface")).attributes()[3]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)

        # Evo lacks a type to represent Dates, so they get converted to strings
        # of the form “YYYY-MM-DD”.
        self.assertIsInstance(attribute_go, StringAttribute_V1_1_0)

        expected_attribute = StringAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=StringArray_V1_0_1(data=attribute_go.values.data, length=4),
        )
        self.assertEqual(expected_attribute, attribute_go)

        dates_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        dates = pq.read_table(dates_parquet_file)

        expected_dates = [
            "1995-05-01",
            "1996-06-01",
            None,
            "1998-08-01",
        ]
        self.assertEqual(expected_dates, dates.column("data").to_pylist())

    def test_should_convert_omf_v2_null_datetime_number_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        number_attribute = (self._element_by_name(project, "Test Surface")).attributes()[4]
        self.assertIsInstance(number_attribute.get_data(), omf2.AttributeDataNumber)

        attribute_go = convert_omf_attribute(number_attribute, reader, self.data_client)
        self.assertIsInstance(attribute_go, DateTimeAttribute_V1_1_0)

        expected_attribute = DateTimeAttribute_V1_1_0(
            name=number_attribute.name,
            key=attribute_go.key,
            values=DateTimeArray_V1_0_1(data=attribute_go.values.data, length=4),
            nan_description=NanCategorical_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        dates_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        dates = pq.read_table(dates_parquet_file)

        expected_dates = [
            datetime(1995, 5, 1, 5, 1, tzinfo=timezone.utc),
            datetime(1996, 6, 1, 6, 1, tzinfo=timezone.utc),
            None,
            datetime(1998, 8, 1, 8, 1, tzinfo=timezone.utc),
        ]
        self.assertEqual(expected_dates, dates.column("data").to_pylist())

    def test_should_convert_omf_v2_null_category_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        category_attribute = (self._element_by_name(project, "Test Surface")).attributes()[5]
        self.assertIsInstance(category_attribute.get_data(), omf2.AttributeDataCategory)

        attribute_go = convert_omf_attribute(category_attribute, reader, self.data_client)
        self.assertIsInstance(attribute_go, CategoryAttribute_V1_1_0)

        expected_attribute = CategoryAttribute_V1_1_0(
            name=category_attribute.name,
            key=attribute_go.key,
            table=LookupTable_V1_0_1(data=attribute_go.table.data, keys_data_type="int64", length=3),
            values=IntegerArray1_V1_0_1(data=attribute_go.values.data, data_type="int64", length=4),
            nan_description=NanCategorical_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        lookup_table_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.table.data)
        lookup_table = pq.read_table(lookup_table_parquet_file).to_pydict()

        expected_lookup_table = {"key": list(range(3)), "value": ["Zero", "One", "Two"]}
        self.assertEqual(expected_lookup_table, lookup_table)

        values_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        values = pq.read_table(values_parquet_file)

        expected_values = [0, 1, None, 2]
        self.assertEqual(expected_values, values.column("data").to_pylist())

    def test_should_convert_omf_v2_null_boolean_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        boolean_attribute = (self._element_by_name(project, "Test Surface")).attributes()[6]
        self.assertIsInstance(boolean_attribute.get_data(), omf2.AttributeDataBoolean)

        attribute_go = convert_omf_attribute(boolean_attribute, reader, self.data_client)
        self.assertIsInstance(attribute_go, BoolAttribute_V1_1_0)

        expected_attribute = BoolAttribute_V1_1_0(
            name=boolean_attribute.name,
            key=attribute_go.key,
            values=BoolArray1_V1_0_1(data=attribute_go.values.data, length=4),
        )
        self.assertEqual(expected_attribute, attribute_go)

        booleans_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        booleans = pq.read_table(booleans_parquet_file)

        expected_booleans = [False, True, None, False]
        self.assertEqual(expected_booleans, booleans.column("data").to_pylist())

    def test_should_convert_omf_v2_null_color_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/null_attribute_values.omf")
        reader = OmfReaderContext(omf_file).reader()

        project, _ = reader.project()

        boolean_attribute = (self._element_by_name(project, "Test Surface")).attributes()[7]
        self.assertIsInstance(boolean_attribute.get_data(), omf2.AttributeDataColor)

        attribute_go = convert_omf_attribute(boolean_attribute, reader, self.data_client)
        self.assertIsInstance(attribute_go, ColorAttribute_V1_1_0)

        expected_attribute = ColorAttribute_V1_1_0(
            name=boolean_attribute.name,
            key=attribute_go.key,
            values=ColorArray_V1_0_1(data=attribute_go.values.data, length=4),
        )
        self.assertEqual(expected_attribute, attribute_go)

        colors_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        uint32_colors = pq.read_table(colors_parquet_file)

        rgba_colors = list(map(int_to_rgba_optional, uint32_colors.column("data").to_pylist()))

        expected_rgba_colors = [
            [0, 0, 255, 255],
            [0, 255, 0, 255],
            None,
            [255, 0, 0, 255],
        ]
        self.assertEqual(expected_rgba_colors, rgba_colors)

    def test_should_convert_omf_v2_2d_vector_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Pyramid points")

        vector_attribute = element.attributes()[1]
        self.assertIsInstance(vector_attribute.get_data(), omf2.AttributeDataVector)

        attribute_go = convert_omf_attribute(vector_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, VectorAttribute_V1_0_0)

        expected_count = 5

        expected_attribute = VectorAttribute_V1_0_0(
            name=vector_attribute.name,
            key=attribute_go.key,
            values=FloatArrayMd_V1_0_1(data=attribute_go.values.data, width=2, length=expected_count),
            nan_description=NanContinuous_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        vectors_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        vectors_table = pq.read_table(vectors_parquet_file)

        expected_vectors = [
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
            {"x": 0.0, "y": 1.0},
            {"x": 0.0, "y": 0.0},
            {"x": None, "y": None},
        ]

        self.assertListEqual(expected_vectors, vectors_table.to_pylist())

    def test_should_convert_omf_v2_3d_vector_attribute(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        element = self._element_by_name(project, "Pyramid points")

        vector_attribute = element.attributes()[2]
        self.assertIsInstance(vector_attribute.get_data(), omf2.AttributeDataVector)

        attribute_go = convert_omf_attribute(vector_attribute, reader, self.data_client)

        self.assertIsInstance(attribute_go, VectorAttribute_V1_0_0)

        expected_count = 5

        expected_attribute = VectorAttribute_V1_0_0(
            name=vector_attribute.name,
            key=attribute_go.key,
            values=FloatArrayMd_V1_0_1(data=attribute_go.values.data, width=3, length=expected_count),
            nan_description=NanContinuous_V1_0_1(values=[]),
        )
        self.assertEqual(expected_attribute, attribute_go)

        vectors_parquet_file = path.join(str(self.data_client.cache_location), attribute_go.values.data)
        vectors_table = pq.read_table(vectors_parquet_file)

        expected_vectors = [
            {"x": None, "y": None, "z": None},
            {"x": None, "y": None, "z": None},
            {"x": None, "y": None, "z": None},
            {"x": None, "y": None, "z": None},
            {"x": 0.0, "y": 0.0, "z": 1.0},
        ]

        self.assertListEqual(expected_vectors, vectors_table.to_pylist())
