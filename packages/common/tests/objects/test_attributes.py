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

from evo.data_converters.common.objects.attributes import PyArrowTableFactory, AttributeFactory
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0 as ContinuousAttribute,
    StringAttribute_V1_1_0 as StringAttribute,
)


class TestPyArrowTableFactory:
    def test_create_continuous_table_basic(self) -> None:
        """Test creating a table from a simple float series."""
        series = pd.Series([1.0, 2.0, 3.0, 4.0])
        table = PyArrowTableFactory.create_continuous_table(series)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 4
        assert table.column_names == ["data"]
        assert table.schema[0].type == pa.float64()

    def test_create_continuous_table_with_nans(self) -> None:
        """Test creating a table from a series with NaN values."""
        series = pd.Series([1.0, float("nan"), 3.0, 4.0])
        table = PyArrowTableFactory.create_continuous_table(series)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 4
        assert table.column_names == ["data"]

    def test_create_string_table_basic(self) -> None:
        """Test creating a table from a simple string series."""
        series = pd.Series(["bob", "sally", "edith"])
        table = PyArrowTableFactory.create_string_table(series)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 3
        assert table.column_names == ["data"]
        assert table.schema[0].type == pa.string()

    def test_create_string_table_with_nans(self) -> None:
        """Test creating a table from a series with NaN values."""
        series = pd.Series(["bob", pd.NA, "sally", "edith"])
        table = PyArrowTableFactory.create_string_table(series)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 4
        assert table.column_names == ["data"]


class TestAttributeFactory:
    def test_create_with_float_series(self, mock_data_client) -> None:
        """Test creating attribute from float series."""
        series = pd.Series([1.0, 2.0, 3.0])

        result = AttributeFactory.create("test_attr", series, mock_data_client)

        assert result is not None
        assert isinstance(result, ContinuousAttribute)
        assert result.key == "test_attr"
        assert result.name == "test_attr"
        mock_data_client.save_table.assert_called_once()

    def test_create_with_float_series_and_nan_values(self, mock_data_client) -> None:
        """Test creating attribute with nan_values in series attributes."""
        series = pd.Series([1.0, 2.0, 3.0])
        series.attrs["nan_values"] = [-999.0, -9999.0]

        result = AttributeFactory.create("test_attr", series, mock_data_client)

        assert result is not None
        assert result.nan_description.values == [-999.0, -9999.0]

    def test_create_with_string_series(self, mock_data_client) -> None:
        """Test creating attribute from string series."""
        series = pd.Series(["bob", pd.NA, "sally", "edith"])

        result = AttributeFactory.create("test_attr", series, mock_data_client)

        assert result is not None
        assert isinstance(result, StringAttribute)
        assert result.key == "test_attr"
        assert result.name == "test_attr"
        mock_data_client.save_table.assert_called_once()

    def test_create_with_non_supported_series_returns_none(self, mock_data_client) -> None:
        """Test that non-supported series returns None."""
        series = pd.Series([1, 2, 3], dtype=int)

        result = AttributeFactory.create("test_attr", series, mock_data_client)

        assert result is None
        mock_data_client.save_table.assert_not_called()
