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

import logging

import pandas as pd
import pytest
from pyproj import CRS

from evo.data_converters.ags.common import AgsContext, AgsFileInvalidException
from evo.data_converters.ags.common.ags_context import GEOL, HORN, LOCA, SCPG, SCPP, SCPT
from evo.data_converters.ags.diagnostics import AgsDiagnostic
from evo.data_converters.ags.importer.ags_to_downhole_collection import (
    DEFAULT_AZIMUTH,
    DEFAULT_DIP,
    assign_unspecified_coordinates,
    calculate_dip_and_azimuth,
    create_from_parsed_ags,
)
from evo.objects.typed import (
    AttributeDescription,
    DistanceCollection,
    DownholeCollectionData,
    EpsgCode,
    IntervalCollection,
)


def get_collection(result: DownholeCollectionData, name: str) -> DistanceCollection | IntervalCollection:
    matches = [collection for collection in result.collections if collection.name == name]
    assert len(matches) == 1
    return matches[0]


def collar_frame(result: DownholeCollectionData) -> pd.DataFrame:
    if result.attributes is None:
        return result.properties
    return pd.concat([result.properties.reset_index(drop=True), result.attributes.reset_index(drop=True)], axis=1)


def add_test_coordinates(context: AgsContext) -> None:
    loca = context.get_table(LOCA)
    loca["LOCA_NATE"] = 100.0
    loca["LOCA_NATN"] = 200.0
    loca["LOCA_GL"] = 5.0
    context.set_table(LOCA, loca)
    context.set_units(LOCA, {**context.get_units(LOCA), "LOCA_NATE": "m", "LOCA_NATN": "m", "LOCA_GL": "m"})


def chunk_rows(chunks: pd.DataFrame) -> list[tuple[int, int, int]]:
    return [tuple(row) for row in chunks.itertuples(index=False, name=None)]


def row_hole_index(collection: DistanceCollection | IntervalCollection) -> list[int]:
    holes = collection.holes
    return holes["hole_index"].repeat(holes["count"].astype("int64")).tolist()


def assert_measurements_linked_to_collars(result: DownholeCollectionData) -> None:
    collars = collar_frame(result)
    assert collars["hole_id"].tolist() == collars["LOCA_ID"].tolist()
    hole_index_of = dict(zip(collars["LOCA_ID"], collars["hole_index"]))
    for collection in result.collections:
        expected = [hole_index_of[loca_id] for loca_id in collection.table["LOCA_ID"]]
        assert row_hole_index(collection) == expected, collection.name


def push_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.message for record in caplog.records if "Multiple CPT pushes" in record.message]


def to_pyproj(crs: EpsgCode | str | None) -> CRS | None:
    if crs is None:
        return None
    if isinstance(crs, EpsgCode):
        return CRS.from_epsg(int(crs))
    return CRS.from_wkt(crs)


class TestCreateFromParsedAgs:
    def test_properties_and_tags(self, mock_ags_context):
        result = create_from_parsed_ags(mock_ags_context)

        assert isinstance(result, DownholeCollectionData)
        assert result.name == "test_file.ags"
        assert result.coordinate_reference_system == EpsgCode(27700)
        assert result.tags is None
        assert result.distance_unit == "m"
        assert result.desurvey is None
        assert result.properties.columns.tolist() == [
            "hole_index",
            "hole_id",
            "x",
            "y",
            "z",
            "final",
            "target",
            "current",
        ]
        assert result.properties["hole_id"].tolist() == ["BH01", "BH02", "BH03"]
        assert result.attributes is not None
        assert result.attributes.columns[:2].tolist() == ["LOCA_ID", "SCPG_TESN"]

        tagged = create_from_parsed_ags(mock_ags_context, tags={"source": "test"})
        assert tagged.tags == {"source": "test"}

    def test_numeric_attributes_are_described_with_evo_units(self, mock_ags_context):
        result = create_from_parsed_ags(mock_ags_context)

        scpp = get_collection(result, SCPP)
        assert scpp.table.attrs["attribute_descriptions"] == {"SCPP_CIC": AttributeDescription(unit="MPa")}
        assert "attribute_descriptions" not in get_collection(result, GEOL).table.attrs
        assert result.attributes is not None
        assert result.attributes.attrs["attribute_descriptions"] == {
            column: AttributeDescription(unit="m") for column in ("LOCA_NATE", "LOCA_NATN", "LOCA_GL")
        }

    def test_units_unknown_to_evo_are_left_out_with_a_warning(self, mock_ags_context, caplog):
        get_units = mock_ags_context.get_units.side_effect
        mock_ags_context.get_units.side_effect = lambda group: (
            {**get_units(group), "SCPP_CIC": "kN/m3"} if group == SCPP else get_units(group)
        )

        with caplog.at_level(logging.WARNING):
            result = create_from_parsed_ags(mock_ags_context)

        assert "attribute_descriptions" not in get_collection(result, SCPP).table.attrs
        assert "Unit 'kN/m3' of attribute 'SCPP_CIC' of SCPP is not an Evo unit" in caplog.text

    def test_units_from_ags_file(self, valid_ags_path):
        context = AgsContext()
        context.parse_ags(valid_ags_path)

        result = create_from_parsed_ags(context)

        scpt_units = {
            name: description.unit
            for name, description in get_collection(result, SCPT).table.attrs["attribute_descriptions"].items()
        }
        assert scpt_units["SCPT_RES"] == "MPa"
        assert scpt_units["SCPT_FRES"] == "kN/m2"
        assert scpt_units["SCPT_FRR"] == "%"
        assert result.attributes is not None
        collar_units = result.attributes.attrs["attribute_descriptions"]
        assert collar_units["LOCA_LAT"].unit == "dega"
        assert collar_units["SCPG_CSA"].unit == "cm2"
        assert "LOCA_ID" not in collar_units

    def test_unlocated_hole_is_reported_only_after_collection_succeeds(self, test_elevations_ags_path: str) -> None:
        context = AgsContext()
        context.parse_ags(test_elevations_ags_path)
        loca = context.get_table(LOCA)
        unlocated = loca["LOCA_ID"].eq("BH02")
        loca.loc[unlocated, ["LOCA_NATE", "LOCA_NATN"]] = pd.NA

        issues: list[AgsDiagnostic] = []
        result = create_from_parsed_ags(context, diagnostics=issues)

        assert result.properties["hole_id"].tolist() == ["BH01", "BH03", "BH04", "BH05"]
        assert len(issues) == 1
        assert issues[0].code == "hole_dropped"
        assert issues[0].severity == "warning"
        assert issues[0].hole_id == "BH02"

    def test_unlocated_holes_do_not_emit_warnings_when_every_hole_fails(
        self, test_no_coordinates_ags_path: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        context = AgsContext()
        context.parse_ags(test_no_coordinates_ags_path)
        issues: list[AgsDiagnostic] = []

        with caplog.at_level(logging.WARNING), pytest.raises(AgsFileInvalidException) as error:
            create_from_parsed_ags(context, diagnostics=issues)

        assert error.value.code == "invalid_coordinates"
        assert issues == []
        assert "Excluding collars and measurements without complete finite coordinates" in caplog.text

    def test_one_collar_per_loca_id_shared_by_all_groups(self, mock_ags_context):
        result = create_from_parsed_ags(mock_ags_context)

        assert result.properties["hole_id"].tolist() == ["BH01", "BH02", "BH03"]
        assert_measurements_linked_to_collars(result)

    def test_unlocated_hole_is_excluded_with_its_measurements(self, mock_ags_context, caplog):
        get_table = mock_ags_context.get_table.side_effect
        loca = get_table(LOCA)
        loca.loc[loca["LOCA_ID"] == "BH02", "LOCA_NATN"] = pd.NA
        mock_ags_context.get_table.side_effect = lambda name: loca.copy() if name == LOCA else get_table(name)

        result = create_from_parsed_ags(mock_ags_context)

        assert result.properties[["hole_index", "hole_id"]].values.tolist() == [[1, "BH01"], [2, "BH03"]]
        assert all("BH02" not in collection.table["LOCA_ID"].tolist() for collection in result.collections)
        assert_measurements_linked_to_collars(result)
        assert "Excluding collars and measurements without complete finite coordinates for holes: ['BH02']" in (
            caplog.text
        )

    def test_only_first_push_of_a_location_is_imported(self, mock_ags_context, caplog):
        with caplog.at_level(logging.WARNING):
            result = create_from_parsed_ags(mock_ags_context)

        assert collar_frame(result)["SCPG_TESN"].tolist() == ["T01", "T01", "T01"]
        scpt = get_collection(result, "SCPT")
        assert scpt.table["SCPG_TESN"].tolist() == ["T01"] * 5
        assert result.properties["final"].tolist() == [5.2, 10.0, 7.1]
        assert push_warnings(caplog) == [
            "Multiple CPT pushes found for LOCA_ID 'BH03'. Only the first push ('T01') was imported. "
            "Push 'T02' was not imported because multiple pushes per location are not currently supported."
        ]

    def test_first_push_follows_the_order_of_the_ags_data(self, mock_ags_context, caplog):
        original_get_table = mock_ags_context.get_table.side_effect

        def get_table(group):
            table = original_get_table(group)
            # BH03 push T02 comes before T01, so T02 is imported even though it sorts after T01
            return table.iloc[[0, 1, 3, 2]] if group == SCPG else table

        mock_ags_context.get_table.side_effect = get_table
        with caplog.at_level(logging.WARNING):
            result = create_from_parsed_ags(mock_ags_context)

        assert collar_frame(result)["SCPG_TESN"].tolist() == ["T01", "T01", "T02"]
        scpt = get_collection(result, "SCPT")
        assert scpt.table[["distance", "SCPG_TESN"]].values.tolist()[-1] == [7.2, "T02"]
        assert chunk_rows(scpt.holes) == [(1, 0, 2), (2, 2, 2), (3, 4, 1)]
        assert result.properties["final"].tolist() == [5.2, 10.0, 7.2]
        assert push_warnings(caplog) == [
            "Multiple CPT pushes found for LOCA_ID 'BH03'. Only the first push ('T02') was imported. "
            "Push 'T01' was not imported because multiple pushes per location are not currently supported."
        ]

    def test_skipped_pushes_are_excluded_from_all_groups(self, multiple_pushes_ags_path, caplog):
        context = AgsContext()
        context.parse_ags(multiple_pushes_ags_path)

        with caplog.at_level(logging.WARNING):
            result = create_from_parsed_ags(context)

        collars = collar_frame(result)
        assert collars["hole_id"].tolist() == ["CPT-14", "CPT-15"]
        assert collars["SCPG_TESN"].tolist() == ["1", "1"]
        assert not any(":" in hole_id for hole_id in collars["hole_id"])
        # The final depth of CPT-14 comes from its GEOL data and first push, not the deeper pushes 2 and 3
        assert result.properties["final"].tolist() == [3.0, 1.0]

        scpt = get_collection(result, "SCPT")
        assert scpt.table[["LOCA_ID", "SCPG_TESN"]].drop_duplicates().values.tolist() == [
            ["CPT-14", "1"],
            ["CPT-15", "1"],
        ]
        assert scpt.table["distance"].tolist() == [0.0, 1.0, 2.0, 0.0, 1.0]
        assert chunk_rows(scpt.holes) == [(1, 0, 3), (2, 3, 2)]
        scpp = get_collection(result, "SCPP")
        assert scpp.table[["from", "to"]].values.tolist() == [[0.0, 1.0], [1.0, 2.0]]
        assert scpp.table["SCPP_REF"].tolist() == ["P141", "P141"]
        assert chunk_rows(scpp.holes) == [(1, 0, 2)]
        geol = get_collection(result, "GEOL")
        assert chunk_rows(geol.holes) == [(1, 0, 2)]
        assert chunk_rows(result.holes) == [(1, 0, 3), (2, 3, 2)]

        assert push_warnings(caplog) == [
            "Multiple CPT pushes found for LOCA_ID 'CPT-14'. Only the first push ('1') was imported. "
            "Pushes '2' and '3' were not imported because multiple pushes per location are not currently supported."
        ]

    def test_geol_rows_of_all_locations_are_kept(self, valid_ags_with_geol_path, caplog):
        context = AgsContext()
        context.parse_ags(valid_ags_with_geol_path)

        with caplog.at_level(logging.WARNING):
            result = create_from_parsed_ags(context)

        collars = collar_frame(result)
        assert collars["hole_id"].tolist() == ["BH01", "BH02", "BH03"]
        assert collars["SCPG_TESN"].isna().tolist() == [False, False, True]
        geol = get_collection(result, "GEOL")
        assert geol.table["LOCA_ID"].tolist() == ["BH01"] * 4 + ["BH02"] * 3 + ["BH03"]
        # GEOL rows share the collar of their LOCA_ID with the CPT data
        assert chunk_rows(geol.holes) == [(1, 0, 4), (2, 4, 3), (3, 7, 1)]
        # BH03 only has GEOL data, so it gets a vertical station at its final depth
        assert chunk_rows(result.holes) == [(1, 0, 5), (2, 5, 6), (3, 11, 1)]
        assert result.path["distance"].iloc[-1] == 10.0
        assert push_warnings(caplog) == []

    def test_collections_and_hole_chunks(self, mock_ags_context):
        result = create_from_parsed_ags(mock_ags_context)

        assert [collection.name for collection in result.collections] == ["SCPT", "SCPP", "GEOL"]
        scpt = get_collection(result, "SCPT")
        scpp = get_collection(result, "SCPP")
        geol = get_collection(result, "GEOL")
        assert isinstance(scpt, DistanceCollection)
        assert isinstance(scpp, IntervalCollection)
        assert isinstance(geol, IntervalCollection)
        assert all(collection.unit == "m" for collection in result.collections)

        assert scpt.table.columns[:1].tolist() == ["distance"]
        assert scpt.table["distance"].tolist() == [5.1, 5.2, 6.1, 6.2, 7.1]
        assert chunk_rows(scpt.holes) == [(1, 0, 2), (2, 2, 2), (3, 4, 1)]
        assert scpp.table[["from", "to"]].values.tolist() == [[5.0, 10.0], [10.0, 15.0], [15.0, 20.0]]
        assert scpp.table["SCPP_CIC"].tolist() == [1.5, 2.3, 1.8]
        assert chunk_rows(scpp.holes) == [(1, 0, 2), (2, 2, 1)]
        assert geol.table[["from", "to"]].values.tolist() == [[0.0, 5.0], [0.0, 10.0]]
        assert geol.table["GEOL_DESC"].tolist() == ["Clay", "Sand"]
        assert chunk_rows(geol.holes) == [(1, 0, 1), (2, 1, 1)]
        for collection in result.collections:
            assert "hole_index" not in collection.table.columns
            assert collection.holes["hole_index"].dtype == "int32"
            assert collection.holes["offset"].dtype == "uint64"
            assert collection.holes["count"].dtype == "uint64"

    def test_path_follows_measured_depths(self, mock_ags_context):
        result = create_from_parsed_ags(mock_ags_context)

        assert result.path[["distance", "dip", "azimuth"]].values.tolist() == [
            [5.1, 90.0, 0.0],
            [5.2, 90.0, 0.0],
            [6.1, 90.0, 0.0],
            [6.2, 90.0, 0.0],
            [7.1, 90.0, 0.0],
        ]
        assert chunk_rows(result.holes) == [(1, 0, 2), (2, 2, 2), (3, 4, 1)]
        box = result.compute_bounding_box()
        assert box.min_x == pytest.approx(100.0)
        assert box.max_x == pytest.approx(300.0)
        assert box.min_y == pytest.approx(1000.0)
        assert box.max_y == pytest.approx(3000.0)
        assert box.min_z == pytest.approx(-10.98)
        assert box.max_z == pytest.approx(5.0)

    def test_horn_drives_path_orientation(self, mock_ags_context):
        horn = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH02", "BH03"],
                "HORN_TOP": [0.0, 0.0, 0.0],
                "HORN_BASE": [20.0, 20.0, 20.0],
                "HORN_INCL": [85.0, 80.0, 75.0],
                "HORN_ORNT": [45.0, 90.0, 135.0],
            }
        )
        original_get_table = mock_ags_context.get_table.side_effect

        def get_table(group):
            return horn.copy() if group == HORN else original_get_table(group)

        mock_ags_context.get_table.side_effect = get_table
        get_units = mock_ags_context.get_units.side_effect
        mock_ags_context.get_units.side_effect = lambda group: (
            {"HORN_TOP": "m", "HORN_BASE": "m", "HORN_INCL": "deg", "HORN_ORNT": "deg"}
            if group == HORN
            else get_units(group)
        )
        result = create_from_parsed_ags(mock_ags_context)

        assert result.path["dip"].tolist() == [85.0, 85.0, 80.0, 80.0, 75.0]
        assert result.path["azimuth"].tolist() == [45.0, 45.0, 90.0, 90.0, 135.0]

    def test_geol_only_and_empty_distance_group(self, mock_ags_context):
        original_get_table = mock_ags_context.get_table.side_effect
        mock_ags_context.get_table.side_effect = lambda group: (
            pd.DataFrame(columns=["LOCA_ID", "SCPG_TESN", "SCPG_TYPE"])
            if group == SCPG
            else pd.DataFrame(columns=["LOCA_ID", "SCPG_TESN", "SCPT_DPTH"])
            if group == SCPT
            else original_get_table(group)
        )

        result = create_from_parsed_ags(mock_ags_context)

        assert [collection.name for collection in result.collections] == ["GEOL"]
        assert result.properties["hole_id"].tolist() == ["BH01", "BH02"]
        assert result.path["distance"].tolist() == [5.0, 10.0]
        assert chunk_rows(result.holes) == [(1, 0, 1), (2, 1, 1)]

    def test_timedelta_attributes_are_skipped(self, test_timedelta_ags_path, caplog):
        context = AgsContext()
        context.parse_ags(test_timedelta_ags_path)
        add_test_coordinates(context)

        with caplog.at_level(logging.WARNING):
            result = create_from_parsed_ags(context)

        assert result.attributes is not None
        assert not {"SCPG_TSEC", "SCPG_TMIN", "SCPG_THR"} & set(result.attributes.columns)
        assert caplog.text.count("unsupported data type 'timedelta64'") == 3
        assert result.properties["hole_id"].tolist() == ["BH1"]
        assert chunk_rows(result.holes) == [(1, 0, 1)]
        assert push_warnings(caplog) == [
            "Multiple CPT pushes found for LOCA_ID 'BH1'. Only the first push ('CPT01') was imported. "
            "Push 'CPT02' was not imported because multiple pushes per location are not currently supported."
        ]

    def test_datetime_attributes_are_preserved(self, test_datetime_formats_ags_path):
        context = AgsContext()
        context.parse_ags(test_datetime_formats_ags_path)
        add_test_coordinates(context)
        result = create_from_parsed_ags(context)

        assert result.attributes is not None
        assert pd.api.types.is_datetime64_any_dtype(result.attributes["SCPG_DATE"])
        assert pd.api.types.is_datetime64_any_dtype(result.attributes["SCPG_TIME"])

    def test_input_measurement_tables_are_not_mutated(self, valid_ags_path):
        context = AgsContext()
        context.parse_ags(valid_ags_path)
        groups = [LOCA, SCPG, SCPT, SCPP, GEOL, HORN]
        originals = {group: context.get_table(group).copy(deep=True) for group in groups}

        create_from_parsed_ags(context)

        for group in groups:
            pd.testing.assert_frame_equal(context.get_table(group), originals[group])


class TestCalculateDipAndAzimuth:
    def test_matches_measurement_to_horn_interval(self):
        horn_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH01"],
                "HORN_TOP": [0.0, 10.0],
                "HORN_BASE": [10.0, 20.0],
                "HORN_INCL": [85.0, 80.0],
                "HORN_ORNT": [45.0, 90.0],
            }
        )
        measurements_df = pd.DataFrame({"LOCA_ID": ["BH01", "BH01", "BH01"], "SCPT_DPTH": [0.0, 15.0, 18.0]})

        calculate_dip_and_azimuth(horn_df, measurements_df, "SCPT_DPTH")

        assert measurements_df["dip"].tolist() == [85.0, 80.0, 80.0]
        assert measurements_df["azimuth"].tolist() == [45.0, 90.0, 90.0]

    def test_matches_each_hole_to_its_own_horn_intervals(self):
        horn_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH02"],
                "HORN_TOP": [0.0, 0.0],
                "HORN_BASE": [20.0, 20.0],
                "HORN_INCL": [85.0, 75.0],
                "HORN_ORNT": [45.0, 180.0],
            }
        )
        measurements_df = pd.DataFrame({"LOCA_ID": ["BH01", "BH02", "BH01"], "SCPT_DPTH": [5.0, 10.0, 15.0]})

        calculate_dip_and_azimuth(horn_df, measurements_df, "SCPT_DPTH")

        assert measurements_df["dip"].tolist() == [85.0, 75.0, 85.0]
        assert measurements_df["azimuth"].tolist() == [45.0, 180.0, 45.0]

    def test_defaults_when_no_matching_interval(self):
        horn_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01"],
                "HORN_TOP": [1.0],
                "HORN_BASE": [2.0],
                "HORN_INCL": [85.0],
                "HORN_ORNT": [45.0],
            }
        )
        measurements_df = pd.DataFrame({"LOCA_ID": ["BH01", "BH02"], "SCPT_DPTH": [0.0, 5.0]})

        calculate_dip_and_azimuth(horn_df, measurements_df, "SCPT_DPTH")

        assert measurements_df["dip"].tolist() == [DEFAULT_DIP, DEFAULT_DIP]
        assert measurements_df["azimuth"].tolist() == [DEFAULT_AZIMUTH, DEFAULT_AZIMUTH]

    def test_preserves_non_default_measurement_index(self):
        horn_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01"],
                "HORN_TOP": [0.0],
                "HORN_BASE": [10.0],
                "HORN_INCL": [85.0],
                "HORN_ORNT": [45.0],
            }
        )
        measurements_df = pd.DataFrame({"LOCA_ID": ["BH01", "BH01"], "SCPT_DPTH": [5.0, 1.0]}, index=[10, 4])

        calculate_dip_and_azimuth(horn_df, measurements_df, "SCPT_DPTH")

        assert measurements_df["dip"].tolist() == [85.0, 85.0]
        assert measurements_df["azimuth"].tolist() == [45.0, 45.0]


class TestCoordinateColumnHandling:
    @pytest.fixture
    def coordinate_context(self, valid_ags_path: str) -> AgsContext:
        context = AgsContext()
        context.parse_ags(valid_ags_path)
        loca = context.get_table(LOCA)
        loca["LOCA_NATE"] = 575784.0
        loca["LOCA_NATN"] = 5807006.0
        loca["LOCA_LOCX"] = 100.0
        loca["LOCA_LOCY"] = 200.0
        loca["LOCA_LON"] = 174.8
        loca["LOCA_LAT"] = -41.3
        loca["LOCA_GREF"] = "OSGB"
        context.set_units(LOCA, {**context.get_units(LOCA), "LOCA_LOCX": "m", "LOCA_LOCY": "m", "LOCA_LOCZ": "m"})
        return context

    @staticmethod
    def _add_hole(context: AgsContext, loca_id: str) -> pd.DataFrame:
        """Copy the first LOCA and SCPG rows to a new hole and return the updated LOCA table."""
        loca = context.get_table(LOCA)
        new_hole = loca.copy()
        new_hole["LOCA_ID"] = loca_id
        context.set_table(LOCA, pd.concat([loca, new_hole], ignore_index=True))
        scpg = context.get_table(SCPG)
        new_test = scpg.copy()
        new_test["LOCA_ID"] = loca_id
        context.set_table(SCPG, pd.concat([scpg, new_test], ignore_index=True))
        return context.get_table(LOCA)

    @pytest.mark.parametrize("crs_name", ["WGS84", "NZGD2000"])
    @pytest.mark.parametrize("crs_column", ["LOCA_LLZ", "LOCA_GREF"])
    def test_geographic_crs_uses_unscaled_lon_lat(
        self, coordinate_context: AgsContext, crs_name: str, crs_column: str
    ) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = ""
        loca[crs_column] = crs_name

        result = create_from_parsed_ags(coordinate_context)

        crs = to_pyproj(result.coordinate_reference_system)
        assert crs is not None and crs.is_geographic
        assert result.properties[["x", "y"]].values.tolist() == [[174.8, -41.3]]
        assert result.distance_unit == coordinate_context.get_units("SCPT")["SCPT_DPTH"]

    def test_projected_crs_with_survey_foot_axes(self, coordinate_context: AgsContext) -> None:
        coordinate_context.get_table(LOCA)["LOCA_GREF"] = "EPSG:2263"

        dhc = create_from_parsed_ags(coordinate_context)

        assert dhc.distance_unit == "ft[US]"
        assert dhc.properties["x"].iloc[0] == pytest.approx(575784 * 3937 / 1200, rel=1e-12)
        assert dhc.collections[0].unit == "m"

    @pytest.mark.parametrize(
        ("crs_name", "epsg"), [("OSGB", 27700), ("OSI", 29902), ("ITM", 2157), ("EPSG:2193", 2193)]
    )
    def test_nate_natn_have_projected_crs(self, coordinate_context: AgsContext, crs_name: str, epsg: int) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = crs_name
        loca["LOCA_LLZ"] = "WGS84"

        result = create_from_parsed_ags(coordinate_context)

        assert result.coordinate_reference_system == EpsgCode(epsg)
        assert result.properties[["x", "y"]].values.tolist() == [[575784.0, 5807006.0]]

    @pytest.mark.parametrize(
        ("crs_name", "columns", "expected"),
        [
            ("WGS84", ["LOCA_LON", "LOCA_LAT"], "LOCA_LON/LOCA_LAT"),
            ("OSGB", ["LOCA_NATE", "LOCA_NATN", "LOCA_LOCX", "LOCA_LOCY"], "LOCA_NATE/LOCA_NATN"),
        ],
    )
    @pytest.mark.parametrize("empty_columns", [False, True])
    def test_crs_coordinate_mismatch_raises(
        self, coordinate_context: AgsContext, crs_name: str, columns: list[str], expected: str, empty_columns: bool
    ) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = crs_name
        if empty_columns:
            loca[columns] = pd.NA
        else:
            coordinate_context.set_table(LOCA, loca.drop(columns=columns))

        with pytest.raises(
            AgsFileInvalidException, match=f"No holes have a complete finite coordinate pair.*{expected}"
        ):
            create_from_parsed_ags(coordinate_context)

    def test_projected_crs_does_not_fall_back_to_local_coordinates(self, coordinate_context: AgsContext) -> None:
        coordinate_context.get_table(LOCA)["LOCA_NATN"] = pd.NA

        with pytest.raises(AgsFileInvalidException, match="No holes have a complete finite coordinate pair"):
            create_from_parsed_ags(coordinate_context)

    def test_incomplete_projected_pairs_are_not_mixed(self, coordinate_context: AgsContext) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_NATN"] = pd.NA
        loca["LOCA_LOCX"] = pd.NA

        with pytest.raises(AgsFileInvalidException, match="No holes have a complete finite coordinate pair"):
            create_from_parsed_ags(coordinate_context)

    def test_unlocated_local_reference_hole_without_crs_is_excluded(
        self, coordinate_context: AgsContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        coordinate_context.get_table(LOCA)["LOCA_GREF"] = ""
        loca = self._add_hole(coordinate_context, "SITE")
        site = loca["LOCA_ID"] == "SITE"
        loca.loc[site, "LOCA_LREF"] = "SITE GRID"
        loca.loc[site, ["LOCA_LOCX", "LOCA_LOCY"]] = pd.NA

        result = create_from_parsed_ags(coordinate_context)

        assert result.properties[["hole_id", "x", "y"]].values.tolist() == [["EXAMPLE-1-CPT1", 575784.0, 5807006.0]]
        assert "Excluding collars and measurements without complete finite coordinates for holes: ['SITE']" in (
            caplog.text
        )

    def test_holes_with_different_crs_raise(self, coordinate_context: AgsContext) -> None:
        loca = self._add_hole(coordinate_context, "GEOGRAPHIC")
        loca.loc[loca["LOCA_ID"] == "GEOGRAPHIC", "LOCA_GREF"] = ""
        loca.loc[loca["LOCA_ID"] == "GEOGRAPHIC", "LOCA_LLZ"] = "WGS84"

        with pytest.raises(AgsFileInvalidException, match="different coordinate reference systems"):
            create_from_parsed_ags(coordinate_context)

    def test_hole_without_crs_uses_crs_of_other_holes(self, coordinate_context: AgsContext) -> None:
        loca = self._add_hole(coordinate_context, "UNDECLARED")
        loca.loc[loca["LOCA_ID"] == "UNDECLARED", "LOCA_GREF"] = ""

        result = create_from_parsed_ags(coordinate_context)

        assert result.coordinate_reference_system == EpsgCode(27700)
        assert result.properties[["x", "y"]].values.tolist() == [[575784.0, 5807006.0]] * 2

    def test_zero_coordinates_are_valid(self, coordinate_context: AgsContext) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = "WGS84"
        loca[["LOCA_LON", "LOCA_LAT"]] = 0.0

        result = create_from_parsed_ags(coordinate_context)

        assert result.properties[["x", "y"]].values.tolist() == [[0.0, 0.0]]

    @pytest.mark.parametrize("invalid_coordinate", ["invalid", "inf"])
    def test_invalid_coordinates_do_not_fall_back_to_other_family(
        self, coordinate_context: AgsContext, invalid_coordinate: str
    ) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = "WGS84"
        loca["LOCA_LON"] = invalid_coordinate

        with pytest.raises(AgsFileInvalidException, match="No holes have a complete finite coordinate pair"):
            create_from_parsed_ags(coordinate_context)

    def test_projected_crs_in_llz_uses_projected_columns(self, coordinate_context: AgsContext) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = ""
        loca["LOCA_LLZ"] = "EPSG:2193"

        result = create_from_parsed_ags(coordinate_context)

        assert result.coordinate_reference_system == EpsgCode(2193)
        assert result.properties[["x", "y"]].values.tolist() == [[575784.0, 5807006.0]]

    def test_unsupported_crs_type_raises(self, coordinate_context: AgsContext) -> None:
        coordinate_context.get_table(LOCA)["LOCA_GREF"] = "EPSG:4978"

        with pytest.raises(AgsFileInvalidException, match="neither projected nor geographic"):
            create_from_parsed_ags(coordinate_context)

    @pytest.mark.parametrize("crs_name", ["", "LOCAL"])
    def test_unspecified_crs_warns_and_uses_declared_local_family(
        self, coordinate_context: AgsContext, crs_name: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = crs_name
        if crs_name == "":
            loca = loca.drop(columns=["LOCA_LOCX", "LOCA_LOCY", "LOCA_LON", "LOCA_LAT"])
            coordinate_context.set_table(LOCA, loca)

        result = create_from_parsed_ags(coordinate_context)

        assert result.coordinate_reference_system is None
        if crs_name == "LOCAL":
            assert result.properties[["x", "y", "z"]].values.tolist() == [[100.0, 200.0, 0.0]]
            assert "using local grid coordinates" in caplog.text
        else:
            assert result.properties[["x", "y"]].values.tolist() == [[575784.0, 5807006.0]]
            assert "coordinate columns cannot be verified" in caplog.text

    def test_undeclared_crs_uses_geographic_family_when_only_lon_lat_present(
        self, coordinate_context: AgsContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        loca = coordinate_context.get_table(LOCA).drop(columns=["LOCA_NATE", "LOCA_NATN", "LOCA_LOCX", "LOCA_LOCY"])
        loca["LOCA_GREF"] = ""
        loca["LOCA_GL"] = 12.5
        loca["LOCA_LOCZ"] = -3.25
        coordinate_context.set_table(LOCA, loca)

        result = create_from_parsed_ags(coordinate_context)

        assert result.coordinate_reference_system is None
        assert result.properties[["x", "y", "z"]].values.tolist() == [[174.8, -41.3, 12.5]]
        assert "coordinate columns cannot be verified" in caplog.text

    def test_heterogeneous_coordinate_families_are_resolved_per_hole_but_not_combined(
        self, test_coordinate_columns_ags_path: str
    ) -> None:
        context = AgsContext()
        context.parse_ags(test_coordinate_columns_ags_path)
        loca = context.get_table(LOCA)
        families = assign_unspecified_coordinates(loca)

        assert loca.loc[:3, ["LOCA_ID", "x", "y"]].values.tolist() == [
            ["BH01", 100.0, 200.0],
            ["BH02", 300.0, 400.0],
            ["BH03", -0.1278, 51.5074],
            ["BH04", 500.0, 600.0],
        ]
        assert loca.loc[4, ["x", "y"]].isna().all()
        assert families.fillna("missing").tolist() == ["national", "local", "geographic", "national", "missing"]

        with pytest.raises(AgsFileInvalidException, match="different coordinate types"):
            create_from_parsed_ags(context)

    def test_unspecified_coordinates_fall_back_to_next_complete_pair(
        self, test_coordinate_columns_ags_path: str
    ) -> None:
        context = AgsContext()
        context.parse_ags(test_coordinate_columns_ags_path)
        loca = context.get_table(LOCA)
        loca.loc[loca["LOCA_ID"] == "BH02", "LOCA_NATE"] = 999.0
        loca.loc[loca["LOCA_ID"] == "BH02", "LOCA_NATN"] = pd.NA
        context.set_table(LOCA, loca)

        families = assign_unspecified_coordinates(loca)

        assert loca.loc[loca["LOCA_ID"] == "BH02", ["x", "y"]].values.tolist() == [[300.0, 400.0]]
        assert families.loc[loca["LOCA_ID"] == "BH02"].tolist() == ["local"]

    @pytest.mark.parametrize(
        ("crs_name", "ground_level", "local_z", "expected"),
        [
            ("OSGB", 12.5, 99.0, 12.5),
            ("OSGB", -4.78, 99.0, -4.78),
            ("OSGB", 0.0, 99.0, 0.0),
            ("OSGB", "16.48", 99.0, 16.48),
            ("OSGB", None, -3.25, 0.0),
            ("OSGB", "", 10.0, 0.0),
            ("LOCAL", 12.5, -3.25, -3.25),
        ],
    )
    def test_elevation_uses_selected_coordinate_family(
        self,
        coordinate_context: AgsContext,
        crs_name: str,
        ground_level: float | str | None,
        local_z: float,
        expected: float,
    ) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = crs_name
        loca["LOCA_GL"] = ground_level
        loca["LOCA_LOCZ"] = local_z

        result = create_from_parsed_ags(coordinate_context)

        assert result.properties["z"].tolist() == [expected]

    @pytest.mark.parametrize(
        ("source_column", "crs_name", "expected"),
        [("LOCA_GL", "OSGB", -4.78), ("LOCA_LOCZ", "LOCAL", -4.78), ("LOCA_LOCZ", "OSGB", 0.0)],
    )
    def test_elevation_with_one_source_column(
        self, coordinate_context: AgsContext, source_column: str, crs_name: str, expected: float
    ) -> None:
        loca = coordinate_context.get_table(LOCA).drop(columns=["LOCA_GL", "LOCA_LOCZ"], errors="ignore")
        loca[source_column] = -4.78
        loca["LOCA_GREF"] = crs_name
        coordinate_context.set_table(LOCA, loca)

        result = create_from_parsed_ags(coordinate_context)

        assert result.properties["z"].tolist() == [expected]

    @pytest.mark.parametrize("invalid_level", [pd.NA, "abc", "inf", "-inf", "nan"])
    def test_invalid_elevation_warns_per_hole(
        self, coordinate_context: AgsContext, caplog: pytest.LogCaptureFixture, invalid_level: object
    ) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GL"] = invalid_level
        loca["LOCA_LOCZ"] = invalid_level

        result = create_from_parsed_ags(coordinate_context)

        assert result.properties["z"].tolist() == [0.0]
        assert "No valid z coordinate data found" in caplog.text
        assert result.properties["hole_id"].iloc[0] in caplog.text

    def test_missing_vertical_datum_warns_and_is_preserved_as_undeclared(
        self, coordinate_context: AgsContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        coordinate_context.get_table(LOCA)["LOCA_DATM"] = ""

        result = create_from_parsed_ags(coordinate_context)

        assert "LOCA_GL used without a declared vertical datum (LOCA_DATM)" in caplog.text
        assert collar_frame(result)["LOCA_DATM"].tolist() == ["undeclared"]

    def test_declared_vertical_datum_is_preserved_for_ground_level(
        self, coordinate_context: AgsContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        coordinate_context.get_table(LOCA)["LOCA_DATM"] = "SITE VERTICAL DATUM"

        result = create_from_parsed_ags(coordinate_context)

        assert collar_frame(result)["LOCA_DATM"].tolist() == ["SITE VERTICAL DATUM"]
        assert "LOCA_GL used without a declared vertical datum" not in caplog.text

    def test_local_reference_selects_local_xyz_family(self, coordinate_context: AgsContext) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = ""
        loca["LOCA_LREF"] = "SITE GRID"
        loca["LOCA_DATM"] = "LOCAL DATUM"
        loca["LOCA_LOCZ"] = -3.25

        result = create_from_parsed_ags(coordinate_context)

        collars = collar_frame(result)
        assert collars[["x", "y", "z"]].values.tolist() == [[100.0, 200.0, -3.25]]
        assert collars["LOCA_LREF"].tolist() == ["SITE GRID"]
        assert collars["LOCA_DATM"].tolist() == ["LOCAL DATUM"]

    def test_local_reference_without_local_coordinates_raises(self, coordinate_context: AgsContext) -> None:
        loca = coordinate_context.get_table(LOCA)
        loca["LOCA_GREF"] = ""
        loca["LOCA_LREF"] = "SITE GRID"
        loca[["LOCA_LOCX", "LOCA_LOCY"]] = pd.NA

        with pytest.raises(AgsFileInvalidException, match="No holes have a complete finite coordinate pair"):
            create_from_parsed_ags(coordinate_context)

    def test_coordinate_dtypes_are_float(self, coordinate_context: AgsContext) -> None:
        result = create_from_parsed_ags(coordinate_context)

        assert result.properties[["x", "y", "z"]].dtypes.tolist() == ["float64"] * 3

    def test_no_coordinates_are_not_defaulted_to_zero(
        self, test_no_coordinates_ags_path: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        context = AgsContext()
        context.parse_ags(test_no_coordinates_ags_path)

        with pytest.raises(AgsFileInvalidException, match="No holes have a complete finite coordinate pair"):
            create_from_parsed_ags(context)

        assert "defaulting to 0.0" not in caplog.text
