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

import pyarrow as pa
import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_data_client():
    """Create a mock ObjectDataClient that returns valid schemas for different table types."""
    client = Mock()

    def save_table_side_effect(table):
        """Return appropriate schema based on table structure."""
        num_rows = table.num_rows
        column_names = set(table.column_names)

        # LookupTable: has 'key' and 'value' columns
        if column_names == {"key", "value"}:
            return {
                "data": None,
                "length": num_rows,
                "keys_data_type": "int32",
                "values_data_type": "string",
            }

        # FloatArray2: has 'from' and 'to' columns (for intervals)
        if column_names == {"from", "to"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # FloatArray3: has 'x', 'y', 'z' columns OR 'final', 'target', 'current'
        if column_names == {"x", "y", "z"} or column_names == {"final", "target", "current"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # DownholeDirectionVector: has 'distance', 'azimuth', 'dip' columns
        if column_names == {"distance", "azimuth", "dip"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # HoleChunks: has 'hole_index', 'offset', 'count' columns
        if column_names == {"hole_index", "offset", "count"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # Single 'data' column - determine type from schema
        if column_names == {"data"}:
            data_field = table.schema.field("data")
            data_type = data_field.type

            # IntegerArray1: int types
            if data_type in (pa.int32(), pa.int64()):
                dtype_str = "int32" if data_type == pa.int32() else "int64"
                return {
                    "data": None,
                    "length": num_rows,
                    "data_type": dtype_str,
                }

            # FloatArray1: float64
            if data_type == pa.float64():
                return {
                    "data": None,
                    "length": num_rows,
                }

            # StringArray: string type
            if pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
                return {
                    "data": None,
                    "length": num_rows,
                }

            # DateTimeArray: timestamp types
            if pa.types.is_timestamp(data_type):
                return {
                    "data": None,
                    "length": num_rows,
                }

            # BoolArray1: boolean type
            if pa.types.is_boolean(data_type):
                return {
                    "data": None,
                    "length": num_rows,
                }

        # FloatArray1: single 'values' column
        if column_names == {"values"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # Default for any other array types
        return {
            "data": None,
            "length": num_rows,
        }

    client.save_table = MagicMock(side_effect=save_table_side_effect)
    return client
