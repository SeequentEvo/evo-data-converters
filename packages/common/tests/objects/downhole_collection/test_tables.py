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

import pytest
import pandas as pd
from evo.data_converters.common.objects.downhole_collection.tables import (
    ColumnMapping,
    DistanceTable,
    IntervalTable,
    MeasurementTableFactory,
)


class TestDistanceTable:
    """Tests for DistanceTable adapter"""

    def test_distance_table_initialization(self):
        """Test basic initialization with valid distance data"""
        df = pd.DataFrame({"hole_index": [1, 1, 2], "penetrationLength": [0.5, 1.0, 1.5], "value": [10, 20, 30]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert table.df is df
        assert isinstance(table.mapping, ColumnMapping)

    def test_distance_table_case_insensitive_columns(self):
        """Test that column matching is case-insensitive"""
        df = pd.DataFrame({"HOLE_INDEX": [1, 1, 2], "PenetrationLength": [0.5, 1.0, 1.5], "value": [10, 20, 30]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert table.get_hole_index_column() == "HOLE_INDEX"
        assert table.get_depth_column() == "PenetrationLength"

    def test_get_depth_column(self):
        """Test getting the depth column name"""
        df = pd.DataFrame({"hole_index": [1], "SCPT_DPTH": [1.0], "value": [10]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["SCPT_DPTH"]))
        assert table.get_depth_column() == "SCPT_DPTH"

    def test_get_primary_column(self):
        """Test that primary column returns the depth column"""
        df = pd.DataFrame({"hole_index": [1], "penetrationLength": [1.0], "value": [10]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert table.get_primary_column() == "penetrationLength"

    def test_get_primary_columns(self):
        """Test that primary columns list contains only the depth column"""
        df = pd.DataFrame({"hole_index": [1], "penetrationLength": [1.0], "value": [10]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert table.get_primary_columns() == ["penetrationLength"]

    def test_get_depth_values(self):
        """Test getting depth values as a Series"""
        df = pd.DataFrame({"hole_index": [1, 1, 2], "penetrationLength": [0.5, 1.0, 1.5], "value": [10, 20, 30]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        depths = table.get_depth_values()

        assert isinstance(depths, pd.Series)
        assert list(depths) == [0.5, 1.0, 1.5]

    def test_get_attribute_columns(self):
        """Test getting non-primary attribute columns"""
        df = pd.DataFrame({"hole_index": [1], "penetrationLength": [1.0], "value": [10], "description": ["test"]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        attrs = table.get_attribute_columns()

        assert "value" in attrs
        assert "description" in attrs
        assert "hole_index" not in attrs
        assert "penetrationLength" not in attrs

    def test_missing_hole_index_raises_error(self):
        """Test that missing hole index column raises ValueError"""
        df = pd.DataFrame({"penetrationLength": [1.0], "value": [10]})

        with pytest.raises(ValueError, match="No hole index column found"):
            DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))

    def test_missing_depth_column_raises_error(self):
        """Test that missing depth column raises ValueError"""
        df = pd.DataFrame({"hole_index": [1], "value": [10]})

        with pytest.raises(ValueError, match="No depth column found"):
            DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))

    def test_alternative_depth_column_names(self):
        """Test that alternative depth column names are recognized"""
        # Test first alternative
        df1 = pd.DataFrame({"hole_index": [1], "penetrationLength": [1.0], "value": [10]})
        table1 = DistanceTable(df1, ColumnMapping(DEPTH_COLUMNS=["penetrationLength", "SCPT_DPTH"]))
        assert table1.get_depth_column() == "penetrationLength"

        # Test second alternative
        df2 = pd.DataFrame({"hole_index": [1], "SCPT_DPTH": [1.0], "value": [10]})
        table2 = DistanceTable(df2, ColumnMapping(DEPTH_COLUMNS=["penetrationLength", "SCPT_DPTH"]))
        assert table2.get_depth_column() == "SCPT_DPTH"

    def test_prepare_dataframe_orders_columns(self) -> None:
        df = pd.DataFrame({"hole_index": [1, 2, 1], "depth": [1.0, 1.0, 0.5], "value": [10, 20, 30]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["depth"]))

        # ensure hole_indexes are contiguous
        assert table.df.iloc[0]["hole_index"] == 1
        assert table.df.iloc[1]["hole_index"] == 1
        assert table.df.iloc[2]["hole_index"] == 2

        # ensure depths are ascending
        assert table.df.iloc[0]["depth"] == 0.5
        assert table.df.iloc[1]["depth"] == 1.0
        assert table.df.iloc[2]["depth"] == 1.0


class TestIntervalTable:
    """Tests for IntervalTable adapter"""

    def test_interval_table_initialization(self):
        """Test basic initialization with valid interval data"""
        df = pd.DataFrame(
            {"hole_index": [1, 1, 2], "SCPP_TOP": [0.0, 1.0, 0.0], "SCPP_BASE": [1.0, 2.0, 1.5], "value": [10, 20, 30]}
        )

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        assert table.df is df
        assert isinstance(table.mapping, ColumnMapping)

    def test_interval_table_case_insensitive(self):
        """Test case-insensitive column matching"""
        df = pd.DataFrame({"HOLE_INDEX": [1], "scpp_top": [0.0], "SCPP_base": [1.0], "value": [10]})

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        assert table.get_from_column() == "scpp_top"
        assert table.get_to_column() == "SCPP_base"

    def test_get_from_column(self):
        """Test getting the 'from' column name"""
        df = pd.DataFrame({"hole_index": [1], "GEOL_TOP": [0.0], "GEOL_BASE": [1.0], "value": [10]})

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["GEOL_TOP"], TO_COLUMNS=["GEOL_BASE"]))
        assert table.get_from_column() == "GEOL_TOP"

    def test_get_to_column(self):
        """Test getting the 'to' column name"""
        df = pd.DataFrame({"hole_index": [1], "SCPP_TOP": [0.0], "SCPP_BASE": [1.0], "value": [10]})

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        assert table.get_to_column() == "SCPP_BASE"

    def test_get_primary_column(self):
        """Test that primary column returns the 'from' column"""
        df = pd.DataFrame({"hole_index": [1], "SCPP_TOP": [0.0], "SCPP_BASE": [1.0], "value": [10]})

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        assert table.get_primary_column() == "SCPP_TOP"

    def test_get_primary_columns(self):
        """Test that primary columns list contains both interval columns"""
        df = pd.DataFrame({"hole_index": [1], "SCPP_TOP": [0.0], "SCPP_BASE": [1.0], "value": [10]})

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        primary = table.get_primary_columns()

        assert len(primary) == 2
        assert "SCPP_TOP" in primary
        assert "SCPP_BASE" in primary

    def test_get_intervals(self):
        """Test getting intervals as a DataFrame"""
        df = pd.DataFrame(
            {"hole_index": [1, 1, 2], "SCPP_TOP": [0.0, 1.0, 0.0], "SCPP_BASE": [1.0, 2.0, 1.5], "value": [10, 20, 30]}
        )

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        intervals = table.get_intervals()

        assert isinstance(intervals, pd.DataFrame)
        assert list(intervals.columns) == ["SCPP_TOP", "SCPP_BASE"]
        assert len(intervals) == 3

    def test_get_attribute_columns(self):
        """Test getting non-primary attribute columns"""
        df = pd.DataFrame(
            {"hole_index": [1], "SCPP_TOP": [0.0], "SCPP_BASE": [1.0], "value": [10], "description": ["test"]}
        )

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        attrs = table.get_attribute_columns()

        assert "value" in attrs
        assert "description" in attrs
        assert "hole_index" not in attrs
        assert "SCPP_TOP" not in attrs
        assert "SCPP_BASE" not in attrs

    def test_missing_hole_index_raises_error(self):
        """Test that missing hole index raises ValueError"""
        df = pd.DataFrame({"SCPP_TOP": [0.0], "SCPP_BASE": [1.0], "value": [10]})

        with pytest.raises(ValueError, match="No hole index column found"):
            IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))

    def test_missing_from_column_raises_error(self):
        """Test that missing 'from' column raises ValueError"""
        df = pd.DataFrame({"hole_index": [1], "SCPP_BASE": [1.0], "value": [10]})

        with pytest.raises(ValueError, match="Missing interval columns"):
            IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))

    def test_missing_to_column_raises_error(self):
        """Test that missing 'to' column raises ValueError"""
        df = pd.DataFrame({"hole_index": [1], "SCPP_TOP": [0.0], "value": [10]})

        with pytest.raises(ValueError, match="Missing interval columns"):
            IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))

    def test_alternative_interval_column_names(self):
        """Test that alternative interval column names are recognized"""
        # Test GEOL_ alternatives
        df = pd.DataFrame({"hole_index": [1], "GEOL_TOP": [0.0], "GEOL_BASE": [1.0], "value": [10]})

        table = IntervalTable(
            df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP", "GEOL_TOP"], TO_COLUMNS=["SCPP_BASE", "GEOL_BASE"])
        )
        assert table.get_from_column() == "GEOL_TOP"
        assert table.get_to_column() == "GEOL_BASE"

    def test_prepare_dataframe_orders_columns(self) -> None:
        df = pd.DataFrame({"hole_index": [1, 2, 1], "SCPP_TOP": [1.0, 1.0, 0.5], "SCPP_BASE": [1.5, 1.5, 1.0]})

        table = IntervalTable(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))

        # ensure hole_indexes are contiguous
        assert table.df.iloc[0]["hole_index"] == 1
        assert table.df.iloc[1]["hole_index"] == 1
        assert table.df.iloc[2]["hole_index"] == 2

        # ensure depths are ascending
        assert table.df.iloc[0]["SCPP_TOP"] == 0.5
        assert table.df.iloc[1]["SCPP_TOP"] == 1.0
        assert table.df.iloc[2]["SCPP_TOP"] == 1.0


class TestMeasurementTableFactory:
    """Tests for MeasurementTableFactory"""

    def test_create_distance_table(self):
        """Test factory creates DistanceTable for depth data"""
        df = pd.DataFrame({"hole_index": [1], "penetrationLength": [1.0], "value": [10]})

        table = MeasurementTableFactory.create(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert isinstance(table, DistanceTable)

    def test_create_interval_table(self):
        """Test factory creates IntervalTable for interval data"""
        df = pd.DataFrame({"hole_index": [1], "SCPP_TOP": [0.0], "SCPP_BASE": [1.0], "value": [10]})

        table = MeasurementTableFactory.create(df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        assert isinstance(table, IntervalTable)

    def test_interval_takes_precedence(self):
        """Test that interval table is chosen when both depth and interval columns present"""
        df = pd.DataFrame(
            {"hole_index": [1], "penetrationLength": [1.0], "SCPP_TOP": [0.0], "SCPP_BASE": [1.0], "value": [10]}
        )

        table = MeasurementTableFactory.create(
            df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"], FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"])
        )
        assert isinstance(table, IntervalTable)

    def test_case_insensitive_detection(self):
        """Test factory detection is case-insensitive"""
        df = pd.DataFrame({"HOLE_INDEX": [1], "PenetrationLength": [1.0], "value": [10]})

        table = MeasurementTableFactory.create(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert isinstance(table, DistanceTable)

    def test_custom_column_mapping(self):
        """Test factory with custom column mapping"""
        custom_mapping = ColumnMapping(HOLE_INDEX_COLUMNS=["custom_hole"], DEPTH_COLUMNS=["custom_depth"])

        df = pd.DataFrame({"custom_hole": [1], "custom_depth": [1.0], "value": [10]})

        table = MeasurementTableFactory.create(df, custom_mapping)
        assert isinstance(table, DistanceTable)
        assert table.get_depth_column() == "custom_depth"

    def test_no_matching_columns_raises_error(self):
        """Test that missing required columns raises ValueError"""
        df = pd.DataFrame({"hole_index": [1], "value": [10]})

        with pytest.raises(ValueError, match="Cannot determine measurement type"):
            MeasurementTableFactory.create(df, ColumnMapping())

    def test_missing_hole_index_raises_error(self):
        """Test that missing hole index column raises ValueError"""
        df = pd.DataFrame({"penetrationLength": [1.0], "value": [10]})

        with pytest.raises(ValueError, match="No hole index column found"):
            MeasurementTableFactory.create(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))

    def test_recognizes_all_depth_alternatives(self):
        """Test that all alternative depth column names are recognized"""
        for depth_col in ["penetrationLength", "SCPT_DPTH"]:
            df = pd.DataFrame({"hole_index": [1], depth_col: [1.0], "value": [10]})

            table = MeasurementTableFactory.create(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength", "SCPT_DPTH"]))
            assert isinstance(table, DistanceTable)

    def test_recognizes_all_interval_alternatives(self):
        """Test that all alternative interval column names are recognized"""
        interval_pairs = [("SCPP_TOP", "SCPP_BASE"), ("GEOL_TOP", "GEOL_BASE")]

        for from_col, to_col in interval_pairs:
            df = pd.DataFrame({"hole_index": [1], from_col: [0.0], to_col: [1.0], "value": [10]})

            table = MeasurementTableFactory.create(
                df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP", "GEOL_TOP"], TO_COLUMNS=["SCPP_BASE", "GEOL_BASE"])
            )
            assert isinstance(table, IntervalTable)


class TestMeasurementTableAdapter:
    """Tests for base MeasurementTableAdapter class"""

    def test_get_hole_index_column(self):
        """Test getting hole index column through concrete implementation"""
        df = pd.DataFrame({"hole_index": [1], "penetrationLength": [1.0], "value": [10]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert table.get_hole_index_column() == "hole_index"

    def test_find_column_returns_first_match(self):
        """Test that _find_column returns first matching column"""
        df = pd.DataFrame({"hole_index": [1], "penetrationLength": [1.0], "SCPT_DPTH": [1.5], "value": [10]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength", "SCPT_DPTH"]))
        # Should return penetrationLength as it's first in the mapping list
        assert table.get_depth_column() == "penetrationLength"

    def test_empty_dataframe_validation(self):
        """Test that empty dataframe with correct columns is valid"""
        df = pd.DataFrame({"hole_index": [], "penetrationLength": [], "value": []})

        # Should not raise an error
        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        assert len(table.df) == 0


class TestNanValuesHandling:
    def test_distance_table_with_nan_values(self) -> None:
        df = pd.DataFrame({"hole_index": [1, 1, 2], "depth": [0.5, 1.0, 1.5], "value": [10, 9999.0, 30]})
        nan_values = {"value": [9999.0, -999.0]}

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["depth"]), nan_values_by_column=nan_values)

        assert table.nan_values_by_column == nan_values

    def test_get_nan_values_returns_all_when_no_column_specified(self) -> None:
        df = pd.DataFrame({"hole_index": [1], "depth": [1.0], "qc": [10], "fs": [20]})
        nan_values = {"qc": [9999.0, -999.0], "fs": [-999.0]}

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["depth"]), nan_values_by_column=nan_values)

        result = table.get_nan_values()

        assert isinstance(result, dict)
        assert result == nan_values
        assert result["qc"] == [9999.0, -999.0]
        assert result["fs"] == [-999.0]

    def test_get_nan_values_returns_list_for_specific_column(self) -> None:
        df = pd.DataFrame({"hole_index": [1], "depth": [1.0], "qc": [10], "fs": [20]})
        nan_values = {"qc": [9999.0, -999.0], "fs": [-999.0]}

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["depth"]), nan_values_by_column=nan_values)

        qc_nans = table.get_nan_values("qc")
        fs_nans = table.get_nan_values("fs")

        assert isinstance(qc_nans, list)
        assert qc_nans == [9999.0, -999.0]
        assert isinstance(fs_nans, list)
        assert fs_nans == [-999.0]

    def test_get_nan_values_returns_empty_list_for_missing_column(self) -> None:
        df = pd.DataFrame({"hole_index": [1], "depth": [1.0], "qc": [10]})
        nan_values = {"qc": [9999.0]}

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["depth"]), nan_values_by_column=nan_values)

        result = table.get_nan_values("nonexistent_column")

        assert isinstance(result, list)
        assert result == []

    def test_get_nan_values_with_no_nan_values_initialized(self) -> None:
        df = pd.DataFrame({"hole_index": [1], "depth": [1.0], "qc": [10]})

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["depth"]))

        result_all = table.get_nan_values()
        assert result_all == {}

        result_column = table.get_nan_values("qc")
        assert result_column == []

    def test_factory_creates_table_with_nan_values(self) -> None:
        df = pd.DataFrame({"hole_index": [1], "depth": [1.0], "qc": [10]})
        nan_values = {"qc": [9999.0, -999.0]}

        table = MeasurementTableFactory.create(
            df, ColumnMapping(DEPTH_COLUMNS=["depth"]), nan_values_by_column=nan_values
        )

        assert isinstance(table, DistanceTable)
        assert table.get_nan_values() == nan_values
        assert table.get_nan_values("qc") == [9999.0, -999.0]

    def test_nan_values_with_multiple_types(self) -> None:
        df = pd.DataFrame({"hole_index": [1], "depth": [1.0], "qc": [10], "code": ["A"]})
        nan_values = {
            "qc": [9999.0, -999, 0],  # float, int, int
            "code": ["UNKNOWN", "N/A", ""],  # strings
        }

        table = DistanceTable(df, ColumnMapping(DEPTH_COLUMNS=["depth"]), nan_values_by_column=nan_values)

        assert table.get_nan_values("qc") == [9999.0, -999, 0]
        assert table.get_nan_values("code") == ["UNKNOWN", "N/A", ""]
