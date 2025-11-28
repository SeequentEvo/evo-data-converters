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

import pandas as pd
import pyarrow as pa
from datetime import datetime, date

from evo_schemas.components import (
    BoolAttribute_V1_1_0 as BoolAttribute,
    CategoryAttribute_V1_1_0 as CategoryAttribute,
    ContinuousAttribute_V1_1_0 as ContinuousAttribute,
    DateTimeAttribute_V1_1_0 as DateTimeAttribute,
    IntegerAttribute_V1_1_0 as IntegerAttribute,
    StringAttribute_V1_1_0 as StringAttribute,
)

from evo.data_converters.common.objects.attributes import AttributeFactory, PyArrowTableFactory, DataType


class TestPyArrowTableFactory:
    """Test PyArrow table creation."""

    def test_create_continuous_table(self) -> None:
        series = pd.Series([1.5, 2.5, pd.NA, 3.5])
        table = PyArrowTableFactory.create_table(series, DataType.CONTINUOUS)

        assert table.num_columns == 1
        assert table.column_names == ["data"]
        assert table.num_rows == 4
        assert table["data"][0].as_py() == 1.5
        assert table["data"][2].as_py() is None
        assert table.field("data").type == pa.float64()

    def test_create_string_table(self) -> None:
        series = pd.Series(["alice", "bob", pd.NA, "edith"])
        table = PyArrowTableFactory.create_table(series, DataType.STRING)

        assert table.num_columns == 1
        assert table.column_names == ["data"]
        assert table.num_rows == 4
        assert table["data"][0].as_py() == "alice"
        assert table["data"][2].as_py() is None
        assert table.field("data").type == pa.string()


class TestAttributeFactory:
    """Test evo attribute creation from pandas Series."""

    def test_create_continuous_attribute(self, mock_data_client) -> None:
        """Test creating a ContinuousAttribute from floating point data."""
        series = pd.Series([1.5, 2.5, pd.NA, 3.5, 4.5])

        attribute = AttributeFactory.create("resistance", series, mock_data_client)

        assert isinstance(attribute, ContinuousAttribute)
        assert attribute.key == "resistance"
        assert attribute.name == "resistance"
        assert attribute.values is not None
        assert attribute.nan_description is not None
        assert attribute.nan_description.values == []

    def test_create_continuous_attribute_with_nan_values(self, mock_data_client) -> None:
        """Test ContinuousAttribute with custom NaN values."""
        series = pd.Series([1.5, 2.5, -999.0, 3.5, 4.5])
        series.attrs["nan_values"] = [-999.0, -9999.0]

        attribute = AttributeFactory.create("pressure", series, mock_data_client)

        assert isinstance(attribute, ContinuousAttribute)
        assert attribute.nan_description.values == [-999.0, -9999.0]

    def test_create_continuous_from_mixed_integer_float(self, mock_data_client) -> None:
        """Test that mixed integer-float data creates ContinuousAttribute."""
        series = pd.Series([1, 2.5, 3, pd.NA, 4.7])

        attribute = AttributeFactory.create("values", series, mock_data_client)

        assert isinstance(attribute, ContinuousAttribute)

    def test_create_string_attribute(self, mock_data_client) -> None:
        """Test creating a StringAttribute."""
        series = pd.Series(["alice", "bob", pd.NA, "charlie", "diana"])

        attribute = AttributeFactory.create("engineer", series, mock_data_client)

        assert isinstance(attribute, StringAttribute)
        assert attribute.key == "engineer"
        assert attribute.name == "engineer"
        assert attribute.values is not None
        assert not hasattr(attribute, "nan_description")

    def test_create_string_attribute_unicode(self, mock_data_client) -> None:
        """Test StringAttribute with unicode strings."""
        series = pd.Series(["hello world!", "世界", pd.NA, "🌍"])

        attribute = AttributeFactory.create("notes", series, mock_data_client)

        assert isinstance(attribute, StringAttribute)

    def test_create_integer_attribute(self, mock_data_client) -> None:
        """Test creating an IntegerAttribute."""
        series = pd.Series([1, 2, pd.NA, 3, 4, 5])

        attribute = AttributeFactory.create("count", series, mock_data_client)

        assert isinstance(attribute, IntegerAttribute)
        assert attribute.key == "count"
        assert attribute.name == "count"
        assert attribute.values is not None
        assert attribute.nan_description is not None
        assert attribute.nan_description.values == []

    def test_create_integer_attribute_with_nan_values(self, mock_data_client) -> None:
        """Test IntegerAttribute with nan_values on the series attributes."""
        series = pd.Series([1, 2, -999, 3, 4])
        series.attrs["nan_values"] = [-999, -9999]

        attribute = AttributeFactory.create("count", series, mock_data_client)

        assert isinstance(attribute, IntegerAttribute)
        assert attribute.nan_description.values == [-999, -9999]

    def test_create_datetime_attribute_from_date(self, mock_data_client) -> None:
        """Test DateTimeAttribute from date objects."""
        series = pd.Series([date(2023, 1, 1), date(2023, 6, 15), pd.NaT, date(2023, 12, 31)])

        attribute = AttributeFactory.create("date", series, mock_data_client)

        assert isinstance(attribute, DateTimeAttribute)

    def test_create_datetime_attribute_from_datetime(self, mock_data_client) -> None:
        """Test DateTimeAttribute from datetime objects."""
        series = pd.Series(
            [datetime(2023, 1, 1, 10, 30), datetime(2023, 6, 15, 14, 45), pd.NaT, datetime(2023, 12, 31, 23, 59)]
        )

        attribute = AttributeFactory.create("datetime", series, mock_data_client)

        assert isinstance(attribute, DateTimeAttribute)

    def test_create_bool_attribute(self, mock_data_client) -> None:
        """Test creating a BoolAttribute."""
        series = pd.Series([True, False, pd.NA, True, False])

        attribute = AttributeFactory.create("signed_off", series, mock_data_client)

        assert isinstance(attribute, BoolAttribute)
        assert attribute.key == "signed_off"
        assert attribute.name == "signed_off"
        assert attribute.values is not None

    def test_create_categorical_attribute(self, mock_data_client) -> None:
        """Test creating a CategoryAttribute from categorical data."""
        series = pd.Series(["rock", "sand", "clay", "rock", "limestone"], dtype="category")

        attribute = AttributeFactory.create("lithology", series, mock_data_client)

        assert isinstance(attribute, CategoryAttribute)
        assert attribute.key == "lithology"
        assert attribute.name == "lithology"
        assert attribute.table is not None
        assert attribute.values is not None
        assert attribute.nan_description is not None
        assert attribute.nan_description.values == [-1]

    def test_create_unsupported_type_returns_none(self, mock_data_client) -> None:
        """Test that unsupported types return None."""
        # Complex numbers will not be supported so use those
        series = pd.Series([1 + 2j, 3 + 4j, 5 + 6j])

        attribute = AttributeFactory.create("unsupported", series, mock_data_client)

        assert attribute is None

    def test_create_mixed_type_returns_none(self, mock_data_client) -> None:
        """Test that mixed types return None."""
        series = pd.Series(["text", 123, True, None, 1.5])

        attribute = AttributeFactory.create("mixed", series, mock_data_client)

        assert attribute is None

    def test_data_client_save_table_called_with_correct_args(self, mock_data_client) -> None:
        series = pd.Series([1.5, 2.5, 3.5])
        table = PyArrowTableFactory.create_table(series, DataType.CONTINUOUS)

        AttributeFactory.create("floats", series, mock_data_client)

        assert mock_data_client.save_table.called

        # Check that the expected pyarrow table was passed
        call_args = mock_data_client.save_table.call_args
        assert call_args.args[0] == table


class TestCategoricalAttributeFactory:
    """Test AttributeFactory.create_categorical_attribute()."""

    def test_create_categorical_attribute_basic(self, mock_data_client) -> None:
        series = pd.Series(["sand", "clay", "sand", "rock", "clay"], dtype="category")

        attribute = AttributeFactory.create_categorical_attribute("lithology", series, mock_data_client)

        assert isinstance(attribute, CategoryAttribute)
        assert attribute.key == "lithology"
        assert attribute.name == "lithology"
        assert attribute.table is not None
        assert attribute.values is not None

    def test_create_categorical_attribute_with_nulls(self, mock_data_client) -> None:
        series = pd.Series(["sand", "clay", pd.NA, "rock", pd.NA], dtype="category")

        attribute = AttributeFactory.create_categorical_attribute("lithology", series, mock_data_client)

        assert isinstance(attribute, CategoryAttribute)
        assert attribute.nan_description is not None
        assert attribute.nan_description.values == [-1]

    def test_create_categorical_saves_lookup_table(self, mock_data_client) -> None:
        series = pd.Series(["A", "B", "C", "A", "B"], dtype="category")

        _ = AttributeFactory.create_categorical_attribute("code", series, mock_data_client)

        # Should be called twice: once for lookup table, once for integer array
        assert mock_data_client.save_table.call_count == 2

        lookup_table = mock_data_client.save_table.call_args_list[0].args[0]
        assert set(lookup_table.column_names) == {"key", "value"}
        assert lookup_table.num_rows == 3  # A, B, and C

        # Second call should be integer array with data column
        second_call_table = mock_data_client.save_table.call_args_list[1].args[0]
        assert set(second_call_table.column_names) == {"data"}
        assert second_call_table.num_rows == 5  # 5 measurements

    def test_create_categorical_attribute_codes_mapping(self, mock_data_client) -> None:
        series = pd.Series(["sand", "clay", "sand", "rock", "clay"], dtype="category")

        _ = AttributeFactory.create_categorical_attribute("lithology", series, mock_data_client)

        integer_table = mock_data_client.save_table.call_args_list[1].args[0]
        codes = integer_table["data"].to_pylist()

        assert codes[0] == codes[2]  # Both "sand"
        assert codes[1] == codes[4]  # Both "clay"
        assert codes[0] != codes[1]  # "sand" != "clay"

    def test_create_categorical_empty_series(self, mock_data_client) -> None:
        series = pd.Series([], dtype="category")

        # Use create() which checks for empty series and returns None
        attribute = AttributeFactory.create("empty_cat", series, mock_data_client)

        assert attribute is None

    def test_create_defers_to_categorical_attribute(self, mock_data_client) -> None:
        series = pd.Series(["A", "B", "A", "C"], dtype="category")

        attribute = AttributeFactory.create("category_test", series, mock_data_client)

        assert isinstance(attribute, CategoryAttribute)


class TestInferredTypeMapping:
    """Test single and multiple inferred types map to a single attribute type."""

    def test_boolean_type_is_mapped(self) -> None:
        config = AttributeFactory.INFERRED_TYPE_MAP.get("boolean")

        assert config is AttributeFactory.BOOL_CONFIG

    def test_continuous_types_are_mapped(self) -> None:
        configs = [
            AttributeFactory.INFERRED_TYPE_MAP.get("floating"),
            AttributeFactory.INFERRED_TYPE_MAP.get("mixed-integer-float"),
            AttributeFactory.INFERRED_TYPE_MAP.get("decimal"),
        ]

        assert all(c is AttributeFactory.CONTINUOUS_CONFIG for c in configs)

    def test_integer_type_is_mapped(self) -> None:
        config = AttributeFactory.INFERRED_TYPE_MAP.get("integer")

        assert config is AttributeFactory.INTEGER_CONFIG

    def test_string_types_are_mapped(self) -> None:
        configs = [
            AttributeFactory.INFERRED_TYPE_MAP.get("string"),
            AttributeFactory.INFERRED_TYPE_MAP.get("unicode"),
            AttributeFactory.INFERRED_TYPE_MAP.get("bytes"),
        ]

        assert all(c is AttributeFactory.STRING_CONFIG for c in configs)

    def test_datetime_types_are_mapped(self) -> None:
        configs = [
            AttributeFactory.INFERRED_TYPE_MAP.get("datetime64"),
            AttributeFactory.INFERRED_TYPE_MAP.get("datetime"),
            AttributeFactory.INFERRED_TYPE_MAP.get("date"),
        ]

        assert all(c is AttributeFactory.DATETIME_CONFIG for c in configs)


class TestEdgeCases:
    """Test the weird stuff."""

    def test_empty_series(self, mock_data_client) -> None:
        series = pd.Series([])

        attribute = AttributeFactory.create("empty", series, mock_data_client)

        assert attribute is None

    def test_all_null_values(self, mock_data_client) -> None:
        series = pd.Series([pd.NA, pd.NA, pd.NA])

        attribute = AttributeFactory.create("all_nulls", series, mock_data_client)

        assert attribute is None

    def test_nan_values_attr_non_list(self, mock_data_client) -> None:
        series = pd.Series([1, 2, 3])
        series.attrs["nan_values"] = {-999}  # set instead of list

        attribute = AttributeFactory.create("test", series, mock_data_client)

        # Should get converted to a list
        assert isinstance(attribute, IntegerAttribute)
        assert isinstance(attribute.nan_description.values, list)

    def test_categorical_all_nulls(self, mock_data_client) -> None:
        series = pd.Series([pd.NA, pd.NA, pd.NA], dtype="category")

        attribute = AttributeFactory.create("all_nulls", series, mock_data_client)

        assert isinstance(attribute, CategoryAttribute)

    def test_categorical_single_category(self, mock_data_client) -> None:
        series = pd.Series(["sand", "sand", "sand"], dtype="category")

        attribute = AttributeFactory.create("single_category", series, mock_data_client)

        assert isinstance(attribute, CategoryAttribute)
        lookup_table = mock_data_client.save_table.call_args_list[0].args[0]
        assert lookup_table.num_rows == 1
