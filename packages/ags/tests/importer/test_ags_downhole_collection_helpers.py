#  Copyright © 2025 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import logging

import numpy as np
import pandas as pd
import pytest
from pyproj import CRS

from evo.data_converters.ags.importer.ags_to_downhole_collection import (
    attribute_frame,
    attribute_series,
    build_path,
    describe_units,
    hole_chunks,
    path_stations,
    prepare_measurements,
    to_evo_crs,
    to_evo_unit,
)
from evo.objects.typed import AttributeDescription, EpsgCode


class TestToEvoCrs:
    @pytest.mark.parametrize("crs", [None, "unspecified"])
    def test_unspecified_crs(self, crs):
        assert to_evo_crs(crs) is None

    def test_integer_and_epsg_crs(self):
        assert to_evo_crs(27700) == EpsgCode(27700)
        assert to_evo_crs("EPSG:27700") == EpsgCode(27700)

    def test_custom_crs_is_returned_as_wkt(self):
        crs = "+proj=tmerc +lat_0=1.234 +lon_0=5.678 +k=0.9999 +x_0=111 +y_0=222 +ellps=GRS80 +units=m +no_defs"

        result = to_evo_crs(crs)

        assert isinstance(result, str)
        assert CRS.from_wkt(result).is_projected


class TestAttributeConversion:
    @pytest.mark.parametrize(
        "values, expected_dtype",
        [
            (pd.Series([1, 2, None], dtype="object"), "Int64"),
            ([1.5, 2, None], "float64"),
            ([True, False, None], "boolean"),
            (["a", None, "c"], "string"),
            ([pd.Timestamp("2023-01-01"), None], "datetime64[ns]"),
        ],
    )
    def test_supported_attribute_types(self, values, expected_dtype):
        series = values.rename("value") if isinstance(values, pd.Series) else pd.Series(values, name="value")
        result = attribute_series(series, "test")

        assert result is not None
        assert str(result.dtype) == expected_dtype

    def test_empty_and_timedelta_attributes_are_skipped(self, caplog):
        empty = pd.Series([None, None], name="empty", dtype="object")
        duration = pd.Series(pd.to_timedelta(["1 day", None]), name="duration")

        with caplog.at_level(logging.WARNING):
            assert attribute_series(empty, "test") is None
            assert attribute_series(duration, "test") is None

        assert "duration" in caplog.text
        assert "timedelta64" in caplog.text

    def test_frame_preserves_index_and_omits_empty_columns(self):
        frame = pd.DataFrame(
            {"number": [1, None], "empty": [None, None], "text": ["a", "b"]},
            index=[10, 11],
        )

        result = attribute_frame(frame, "test")

        assert result.index.tolist() == [10, 11]
        assert result.columns.tolist() == ["number", "text"]
        assert result["number"].isna().tolist() == [False, True]


class TestUnits:
    @pytest.mark.parametrize(
        ("ags_unit", "expected"),
        [
            ("m", "m"),
            (" kN/m2 ", "kN/m2"),
            ("%", "%"),
            ("deg", "dega"),
            ("DegC", "degC"),
            ("MN/m2", "MPa"),
            ("mg/l", "mg/L"),
            ("", None),
            ("  ", None),
            (None, None),
            ("blows", None),
        ],
    )
    def test_to_evo_unit(self, ags_unit, expected):
        assert to_evo_unit(ags_unit) == expected

    def test_numeric_attributes_are_described_with_their_units(self, caplog):
        frame = pd.DataFrame(
            {
                "depth": [1.0, 2.0],
                "count": pd.array([1, 2], dtype="Int64"),
                "flag": pd.array([True, False], dtype="boolean"),
                "text": pd.array(["a", "b"], dtype="string"),
                "blows": [3.0, 4.0],
                "unitless": [5.0, 6.0],
            }
        )
        units = {"depth": "m", "count": "%", "flag": "m", "text": "m", "blows": "blows", "unknown": "m"}

        with caplog.at_level(logging.WARNING):
            describe_units(frame, units, "test")

        assert frame.attrs["attribute_descriptions"] == {
            "depth": AttributeDescription(unit="m"),
            "count": AttributeDescription(unit="%"),
        }
        assert "Unit 'blows' of attribute 'blows' of test is not an Evo unit" in caplog.text
        assert "'flag'" not in caplog.text
        assert "'text'" not in caplog.text

    def test_attributes_without_units_are_not_described(self):
        frame = pd.DataFrame({"depth": [1.0, 2.0]})

        describe_units(frame, {}, "test")

        assert "attribute_descriptions" not in frame.attrs


class TestHoleChunks:
    def test_offsets_and_counts_for_non_contiguous_indices(self):
        result = hole_chunks(pd.Series([1, 1, 3, 3, 3, 4]))

        assert result["hole_index"].tolist() == [1, 3, 4]
        assert result["offset"].tolist() == [0, 2, 5]
        assert result["count"].tolist() == [2, 3, 1]

    def test_includes_zero_count_chunks_for_requested_holes(self):
        result = hole_chunks(pd.Series([2, 2, 4]), pd.Series([1, 2, 3, 4]))

        assert result[["hole_index", "offset", "count"]].values.tolist() == [
            [1, 0, 0],
            [2, 0, 2],
            [3, 2, 0],
            [4, 2, 1],
        ]

    def test_empty_rows_can_still_produce_requested_chunks(self):
        result = hole_chunks(pd.Series(dtype="int64"), pd.Series([1, 2]))

        assert result["offset"].tolist() == [0, 0]
        assert result["count"].tolist() == [0, 0]


class TestMeasurements:
    @pytest.fixture
    def collars(self):
        return pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH01", "BH02"],
                "SCPG_TESN": ["T01", "T02", "T01"],
                "hole_index": [1, 2, 3],
            }
        )

    def test_matches_sorts_coerces_and_does_not_mutate_input(self, collars):
        table = pd.DataFrame(
            {
                "LOCA_ID": ["BH02", "BH01", "BH01", "BH01"],
                "SCPG_TESN": ["T01", "T02", "T01", "T01"],
                "SCPT_DPTH": ["1", "2", "5", "3"],
            }
        )
        original = table.copy(deep=True)

        result = prepare_measurements(table, "SCPT", {"distance": "SCPT_DPTH"}, collars)

        assert result["hole_index"].tolist() == [1, 1, 2, 3]
        assert result["SCPT_DPTH"].tolist() == [3.0, 5.0, 2.0, 1.0]
        assert result["hole_index"].dtype == "int64"
        assert result["SCPT_DPTH"].dtype == "float64"
        pd.testing.assert_frame_equal(table, original)

    def test_unmatched_rows_are_dropped_with_warning(self, collars, caplog):
        table = pd.DataFrame({"LOCA_ID": ["BH01", "MISSING"], "SCPT_DPTH": [1.0, 2.0]})

        with caplog.at_level(logging.WARNING):
            result = prepare_measurements(table, "SCPT", {"distance": "SCPT_DPTH"}, collars)

        assert result is not None
        assert result["LOCA_ID"].tolist() == ["BH01"]
        assert "Dropping 1 rows with unmatched LOCA_ID in measurement table SCPT" in caplog.text

    def test_all_unmatched_rows_return_none(self, collars):
        table = pd.DataFrame({"LOCA_ID": ["MISSING"], "SCPT_DPTH": [1.0]})

        assert prepare_measurements(table, "SCPT", {"distance": "SCPT_DPTH"}, collars) is None

    def test_empty_or_missing_depth_table_returns_none(self, collars, caplog):
        with caplog.at_level(logging.WARNING):
            assert prepare_measurements(pd.DataFrame(), "SCPT", {"distance": "SCPT_DPTH"}, collars) is None
            assert (
                prepare_measurements(pd.DataFrame({"LOCA_ID": ["BH01"]}), "SCPT", {"distance": "SCPT_DPTH"}, collars)
                is None
            )

        assert "it has no SCPT_DPTH column" in caplog.text

    def test_location_level_group_uses_first_collar(self, collars):
        table = pd.DataFrame({"LOCA_ID": ["BH01"], "GEOL_TOP": [0.0], "GEOL_BASE": [1.0]})

        result = prepare_measurements(table, "GEOL", {"from": "GEOL_TOP", "to": "GEOL_BASE"}, collars)

        assert result is not None
        assert result["hole_index"].tolist() == [1]

    def test_rows_without_push_are_not_linked_to_collar_without_push(self, caplog):
        collars = pd.DataFrame({"LOCA_ID": ["BH01", "BH02"], "SCPG_TESN": ["T01", pd.NA], "hole_index": [1, 2]})
        table = pd.DataFrame({"LOCA_ID": ["BH01", "BH02"], "SCPG_TESN": ["T01", pd.NA], "SCPT_DPTH": [1.0, 2.0]})

        with caplog.at_level(logging.WARNING):
            result = prepare_measurements(table, "SCPT", {"distance": "SCPT_DPTH"}, collars)

        assert result is not None
        assert result["LOCA_ID"].tolist() == ["BH01"]
        assert "Dropping 1 rows with unmatched LOCA_ID in measurement table SCPT" in caplog.text


class TestPathHelpers:
    def test_path_stations_drops_missing_depths_and_uses_vertical_defaults(self):
        measurements = pd.DataFrame(
            {"hole_index": [1, 1, 2], "LOCA_ID": ["BH01", "BH01", "BH02"], "SCPT_DPTH": [1.0, np.nan, 2.0]}
        )

        result = path_stations(measurements, "SCPT_DPTH", pd.DataFrame())

        assert result[["hole_index", "distance", "dip", "azimuth"]].values.tolist() == [
            [1, 1.0, 90.0, 0.0],
            [2, 2.0, 90.0, 0.0],
        ]

    def test_build_path_keeps_station_order_and_adds_vertical_stations_at_final_depth(self):
        collars = pd.DataFrame({"hole_index": [1, 2, 3, 4], "final_depth": [2.0, 8.0, np.nan, 0.0]})
        stations = pd.DataFrame(
            {
                "hole_index": [1, 1],
                "distance": [2.0, 1.0],
                "dip": [80.0, 80.0],
                "azimuth": [10.0, 10.0],
            }
        )

        path, holes = build_path(collars, stations)

        assert path[["distance", "dip", "azimuth"]].values.tolist() == [
            [2.0, 80.0, 10.0],
            [1.0, 80.0, 10.0],
            [8.0, 90.0, 0.0],
        ]
        assert holes[["hole_index", "offset", "count"]].values.tolist() == [
            [1, 0, 2],
            [2, 2, 1],
            [3, 3, 0],
            [4, 3, 0],
        ]
        assert path.dtypes.astype(str).tolist() == ["float64", "float64", "float64"]

    def test_build_path_without_stations_returns_empty_path_and_zero_chunks(self):
        collars = pd.DataFrame({"hole_index": [1, 2], "final_depth": [np.nan, 0.0]})

        path, holes = build_path(collars, None)

        assert path.columns.tolist() == ["distance", "dip", "azimuth"]
        assert path.empty
        assert holes["count"].tolist() == [0, 0]
