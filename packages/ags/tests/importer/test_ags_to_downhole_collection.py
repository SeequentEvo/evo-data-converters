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
from evo.data_converters.ags.common import AgsContext
from evo.data_converters.ags.importer.ags_to_downhole_collection import (
    calculate_dip_and_azimuth,
    create_from_parsed_ags,
)
from evo.data_converters.common.objects.downhole_collection import DownholeCollection
from evo.data_converters.common.objects.downhole_collection.tables import DEFAULT_AZIMUTH, DEFAULT_DIP


class TestCreateFromParsedAgsProps:
    """Tests for basic DownholeCollection creation properties."""

    def test_basic_properties(self, mock_ags_context):
        """Test basic properties of created DownholeCollection."""
        result = create_from_parsed_ags(mock_ags_context)

        assert isinstance(result, DownholeCollection)
        assert result.name == "test_file.ags"
        assert result.coordinate_reference_system == "EPSG:4326"
        assert result.tags is None

    def test_with_tags(self, mock_ags_context):
        """Test DownholeCollection creation with custom tags."""
        tags = {"project": "test_project", "site": "test_site"}
        result = create_from_parsed_ags(mock_ags_context, tags=tags)

        assert result.tags == tags


class TestCreateFromParsedAgsCollars:
    """Tests for collars table creation from AGS context."""

    def test_collars_structure(self, mock_ags_context):
        """Test that collars have correct structure and data."""
        result = create_from_parsed_ags(mock_ags_context)
        collars_df = result.collars.df

        # Check required columns exist
        assert "hole_index" in collars_df.columns
        assert "hole_id" in collars_df.columns
        assert "x" in collars_df.columns
        assert "y" in collars_df.columns
        assert "z" in collars_df.columns
        assert "final_depth" in collars_df.columns

        # Check number of holes and hole indexes
        assert list(collars_df["hole_index"]) == [1, 2, 3, 4]

        # Check z is set to 0.0
        assert all(collars_df["z"] == 0.0)

    def test_collars_final_depths(self, mock_ags_context):
        """Test that final depths are calculated correctly from measurement data."""
        result = create_from_parsed_ags(mock_ags_context)

        collars_df = result.collars.df

        # Check final depths match max depth across all measurement groups for each hole
        bh01_depth = collars_df[collars_df["hole_id"] == "BH01:T01"]["final_depth"].values[0]
        bh02_depth = collars_df[collars_df["hole_id"] == "BH02:T01"]["final_depth"].values[0]
        bh03_depth_1 = collars_df[collars_df["hole_id"] == "BH03:T01"]["final_depth"].values[0]
        bh03_depth_2 = collars_df[collars_df["hole_id"] == "BH03:T02"]["final_depth"].values[0]

        assert bh01_depth == 5.2
        assert bh02_depth == 6.2
        assert bh03_depth_1 == 7.1
        assert bh03_depth_2 == 7.2

    def test_collars_coordinates(self, mock_ags_context):
        """Test that coordinates are correctly mapped and typed."""
        result = create_from_parsed_ags(mock_ags_context)

        collars_df = result.collars.df

        # Check data types
        assert collars_df["x"].dtype == float
        assert collars_df["y"].dtype == float
        assert collars_df["hole_id"].dtype == object  # string

        assert collars_df[collars_df["hole_id"] == "BH01:T01"]["x"].values[0] == 100.0
        assert collars_df[collars_df["hole_id"] == "BH01:T01"]["y"].values[0] == 1000.0

    def test_collars_scpg_merge(self, mock_ags_context):
        """Test that SCPG data is merged correctly into collars."""
        result = create_from_parsed_ags(mock_ags_context)

        collars_df = result.collars.df

        # Check SCPG columns are present
        assert "SCPG_TYPE" in collars_df.columns
        assert "SCPG_TESN" in collars_df.columns

        # Check LOCA_ID is retained as a key column
        assert "LOCA_ID" in collars_df.columns

        # check number of rows matches expected holes (3 LOCA but 4 unique holes due to SCPG_TESN)
        assert len(collars_df) == 4

    def test_collars_column_ordering(self, mock_ags_context):
        """Test that standard columns appear first in collars."""
        result = create_from_parsed_ags(mock_ags_context)

        collars_df = result.collars.df
        standard_cols = ["hole_index", "hole_id", "x", "y", "z", "final_depth"]

        # Check first columns match standard order
        actual_first_cols = list(collars_df.columns[:6])
        assert actual_first_cols == standard_cols


class TestCreateFromParsedAgsMeasurements:
    """Tests for measurement tables creation from AGS context."""

    def test_measurements_hole_index(self, mock_ags_context):
        """Test that all measurements have hole_index added."""
        result = create_from_parsed_ags(mock_ags_context)

        # Check all measurement adapters have hole_index in underlying dataframe
        for adapter in result.measurements:
            assert "hole_index" in adapter.df.columns
            assert adapter.df["hole_index"].isin([1, 2, 3, 4]).all()

    def test_measurements_hole_index_is_integer(self, valid_ags_with_geol_path):
        """Test that hole_index column has integer dtype, not float.

        Uses real AGS file with unmatched LOCA_ID to ensure the fix for NaN handling
        is working - without the fix, NaN values would convert the column to float.
        """
        ags_context = AgsContext()
        ags_context.parse_ags(valid_ags_with_geol_path)

        result = create_from_parsed_ags(ags_context)

        # Check all measurement adapters have integer hole_index
        for adapter in result.measurements:
            assert pd.api.types.is_integer_dtype(adapter.df["hole_index"]), (
                f"hole_index should be integer dtype, got {adapter.df['hole_index'].dtype}"
            )

    def test_measurements_depth_columns(self, mock_ags_context):
        """Test that measurement tables contain appropriate depth columns."""
        result = create_from_parsed_ags(mock_ags_context)

        all_columns = set()
        for adapter in result.measurements:
            all_columns.update(col.upper() for col in adapter.df.columns)

        depth_columns = {"SCPT_DPTH", "SCPP_DPTH", "SCDG_DPTH"}
        found_depth_columns = depth_columns & all_columns

        assert len(found_depth_columns) > 0, (
            f"Expected depth columns from measurement groups, found: {found_depth_columns}"
        )

    def test_measurements_count(self, mock_ags_context):
        """Test that the correct number of measurement tables are created."""
        result = create_from_parsed_ags(mock_ags_context)

        assert len(result.measurements) == 4

    def test_measurements_scpt_data(self, mock_ags_context):
        """Test that SCPT measurement data is correctly converted."""
        result = create_from_parsed_ags(mock_ags_context)

        scpt_adapter = next((a for a in result.measurements if "SCPT_DPTH" in a.df.columns), None)
        assert scpt_adapter is not None, "SCPT measurement table not found"

        scpt_df = scpt_adapter.df

        assert "SCPT_DPTH" in scpt_df.columns
        assert "hole_index" in scpt_df.columns
        assert len(scpt_df) == 6
        assert set(scpt_df["SCPT_DPTH"].values) == {5.1, 5.2, 6.1, 6.2, 7.1, 7.2}

    def test_measurements_scpp_data(self, mock_ags_context):
        """Test that SCPP measurement data is correctly converted."""
        result = create_from_parsed_ags(mock_ags_context)

        scpp_adapter = next((a for a in result.measurements if "SCPP_TOP" in a.df.columns), None)
        assert scpp_adapter is not None, "SCPP measurement table not found"

        scpp_df = scpp_adapter.df

        assert "SCPP_TOP" in scpp_df.columns
        assert "SCPP_BASE" in scpp_df.columns
        assert "SCPP_CIC" in scpp_df.columns
        assert "hole_index" in scpp_df.columns
        assert len(scpp_df) == 3
        assert list(scpp_df["SCPP_TOP"].values) == [5.0, 10.0, 15.0]
        assert list(scpp_df["SCPP_BASE"].values) == [10.0, 15.0, 20.0]

    def test_measurements_geol_data(self, mock_ags_context):
        """Test that GEOL measurement data is correctly converted."""
        result = create_from_parsed_ags(mock_ags_context)

        geol_adapter = next((a for a in result.measurements if "GEOL_TOP" in a.df.columns), None)
        assert geol_adapter is not None, "GEOL measurement table not found"

        geol_df = geol_adapter.df

        assert "GEOL_TOP" in geol_df.columns
        assert "GEOL_BASE" in geol_df.columns
        assert "GEOL_DESC" in geol_df.columns
        assert "hole_index" in geol_df.columns
        assert len(geol_df) == 2
        assert set(geol_df["GEOL_DESC"].values) == {"Clay", "Sand"}

    def test_measurements_scdg_data(self, mock_ags_context):
        """Test that SCDG measurement data is correctly converted."""
        result = create_from_parsed_ags(mock_ags_context)

        scdg_adapter = next((a for a in result.measurements if "SCDG_DPTH" in a.df.columns), None)
        assert scdg_adapter is not None, "SCDG measurement table not found"

        scdg_df = scdg_adapter.df

        assert "SCDG_DPTH" in scdg_df.columns
        assert "SCDG_T" in scdg_df.columns
        assert "hole_index" in scdg_df.columns
        assert len(scdg_df) == 2
        assert set(scdg_df["SCDG_DPTH"].values) == {7.5, 11.0}
        assert set(scdg_df["SCDG_T"].values) == {100, 150}

    def test_measurements_scpt_empty_table(self, mock_ags_context):
        """Test handling when SCPT table is empty."""
        # Override get_table to return empty SCPT with required columns
        original_get_table = mock_ags_context.get_table.side_effect

        def empty_scpt_get_table(table_name):
            if table_name == "SCPT":
                return pd.DataFrame(columns=["LOCA_ID", "SCPG_TESN", "SCPT_DPTH"])
            return original_get_table(table_name)

        mock_ags_context.get_table.side_effect = empty_scpt_get_table
        mock_ags_context.get_tables.return_value = [pd.DataFrame(columns=["LOCA_ID", "SCPG_TESN", "SCPT_DPTH"])]

        result = create_from_parsed_ags(mock_ags_context)

        # Should still create collars, but final_depth should be NaN
        assert len(result.collars.df) == 4
        assert result.collars.df["final_depth"].isna().all()

    def test_geol_with_unmatched_loca_drops_rows(self, valid_ags_with_geol_path):
        """Test that GEOL rows with unmatched LOCA_ID are dropped.

        The test file valid_ags_with_geol.ags contains:
        - BH01, BH02, BH03 in LOCA (three physical locations)
        - BH01, BH02 in SCPG (only two have CPT tests - these become collars)
        - GEOL entries for BH01 (4 intervals), BH02 (3 intervals), and BH03 (1 interval)
        - BH03's GEOL row should be dropped because BH03 has no collar (not in SCPG)
        """
        ags_context = AgsContext()
        ags_context.parse_ags(valid_ags_with_geol_path)

        result = create_from_parsed_ags(ags_context)

        geol_adapter = next((a for a in result.measurements if "GEOL_TOP" in a.df.columns), None)
        assert geol_adapter is not None

        # Should have 7 rows (4 for BH01 + 3 for BH02), BH03's 1 row dropped
        assert len(geol_adapter.df) == 7
        assert "BH03" not in geol_adapter.df["LOCA_ID"].values
        assert set(geol_adapter.df["LOCA_ID"].unique()) == {"BH01", "BH02"}
        # hole_index should be integer
        assert pd.api.types.is_integer_dtype(geol_adapter.df["hole_index"])


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
        measurements_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH01", "BH01"],
                "SCPT_DPTH": [5.0, 15.0, 18.0],
            }
        )

        calculate_dip_and_azimuth(horn_df, measurements_df, "SCPT_DPTH")

        assert measurements_df["dip"].tolist() == [85.0, 80.0, 80.0]
        assert measurements_df["azimuth"].tolist() == [45.0, 90.0, 90.0]

    def test_defaults_when_no_matching_interval(self):
        horn_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01"],
                "HORN_TOP": [5.0],
                "HORN_BASE": [10.0],
                "HORN_INCL": [85.0],
                "HORN_ORNT": [45.0],
            }
        )
        measurements_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH01"],
                "SCPT_DPTH": [2.0, 15.0],
            }
        )

        calculate_dip_and_azimuth(horn_df, measurements_df, "SCPT_DPTH")

        assert measurements_df["dip"].tolist() == [DEFAULT_DIP, DEFAULT_DIP]
        assert measurements_df["azimuth"].tolist() == [DEFAULT_AZIMUTH, DEFAULT_AZIMUTH]

    def test_multiple_locas(self):
        horn_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH02"],
                "HORN_TOP": [0.0, 0.0],
                "HORN_BASE": [20.0, 20.0],
                "HORN_INCL": [85.0, 75.0],
                "HORN_ORNT": [45.0, 180.0],
            }
        )
        measurements_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH02", "BH01"],
                "SCPT_DPTH": [5.0, 10.0, 15.0],
            }
        )

        calculate_dip_and_azimuth(horn_df, measurements_df, "SCPT_DPTH")

        assert measurements_df["dip"].tolist() == [85.0, 75.0, 85.0]
        assert measurements_df["azimuth"].tolist() == [45.0, 180.0, 45.0]


class TestCreateDownholeCollectionWithHornTable:
    def test_no_horn_table_no_dip_azimuth_columns(self, mock_ags_context):
        result = create_from_parsed_ags(mock_ags_context)

        scpt_adapter = next((a for a in result.measurements if "SCPT_DPTH" in a.df.columns), None)
        assert scpt_adapter is not None

        assert "dip" not in scpt_adapter.df.columns
        assert "azimuth" not in scpt_adapter.df.columns

    def test_horn_table_adds_dip_azimuth_columns(self, mock_ags_context):
        horn_df = pd.DataFrame(
            {
                "LOCA_ID": ["BH01", "BH02", "BH03"],
                "HORN_TOP": [0.0, 0.0, 0.0],
                "HORN_BASE": [20.0, 20.0, 20.0],
                "HORN_INCL": [85.0, 80.0, 75.0],
                "HORN_ORNT": [45.0, 90.0, 135.0],
            }
        )

        original_get_table = mock_ags_context.get_table.side_effect

        def with_horn_get_table(table_name):
            if table_name == "HORN":
                return horn_df
            return original_get_table(table_name)

        mock_ags_context.get_table.side_effect = with_horn_get_table

        result = create_from_parsed_ags(mock_ags_context)

        scpt_adapter = next((a for a in result.measurements if "SCPT_DPTH" in a.df.columns), None)
        assert scpt_adapter is not None

        assert "dip" in scpt_adapter.df.columns
        assert "dip" in scpt_adapter.mapping.DIP_COLUMNS
        assert "azimuth" in scpt_adapter.df.columns
        assert "azimuth" in scpt_adapter.mapping.AZIMUTH_COLUMNS
