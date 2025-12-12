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
from pathlib import Path
from evo.data_converters.ags.common import AgsContext, AgsFileInvalidException


def test_not_ags_file(not_ags_path):
    """An AGS file not conforming to spec cannot be imported"""
    context = AgsContext()
    with pytest.raises(AgsFileInvalidException, match="AGS Format Rule 3"):
        context.parse_ags(not_ags_path)


def test_ags_file_missing_cpt_groups(valid_ags_no_cpt_path):
    """An AGS file without cpt data cannot be imported"""
    context = AgsContext()
    with pytest.raises(
        AgsFileInvalidException,
        match="Missing importable groups: one or more of SCPT, SCPP, GEOL, SCDG required.",
    ):
        context.parse_ags(valid_ags_no_cpt_path)


def test_file_not_found():
    """An AGS file not found cannot be imported"""
    context = AgsContext()
    non_existent_path = Path(__file__).parent / "data" / "does_not_exist.ags"
    with pytest.raises(FileNotFoundError):
        context.parse_ags(non_existent_path)


def test_valid_ags(valid_ags_path):
    """An AGS with correct structure and required tables present can be imported"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)
    expected_tables = [
        "LOCA",
        "SCPG",
        "SCPT",
    ]
    for table_name in expected_tables:
        assert table_name in context.tables
        assert not context.tables[table_name].empty
        assert table_name in context.headings
        assert len(context.headings[table_name]) > 0


def test_timedelta_type_conversion(test_timedelta_ags_path):
    """Test that T type with different time units is converted to pandas Timedelta"""
    import pandas as pd

    context = AgsContext()
    context.parse_ags(test_timedelta_ags_path)

    scpg_table = context.get_table("SCPG")

    assert "SCPG_TSEC" in scpg_table.columns
    assert "SCPG_TMIN" in scpg_table.columns
    assert "SCPG_THR" in scpg_table.columns

    assert pd.api.types.is_timedelta64_dtype(scpg_table["SCPG_TSEC"])
    assert pd.api.types.is_timedelta64_dtype(scpg_table["SCPG_TMIN"])
    assert pd.api.types.is_timedelta64_dtype(scpg_table["SCPG_THR"])

    assert scpg_table.iloc[0]["SCPG_TSEC"] == pd.Timedelta(seconds=10)
    assert scpg_table.iloc[0]["SCPG_TMIN"] == pd.Timedelta(minutes=5.5)
    assert scpg_table.iloc[0]["SCPG_THR"] == pd.Timedelta(hours=2.25)

    assert scpg_table.iloc[1]["SCPG_TSEC"] == pd.Timedelta(seconds=120)
    assert scpg_table.iloc[1]["SCPG_TMIN"] == pd.Timedelta(minutes=15)
    assert scpg_table.iloc[1]["SCPG_THR"] == pd.Timedelta(hours=1)


def test_datetime_formats(test_datetime_formats_ags_path):
    """Test that datetime formats are correctly parsed"""
    import pandas as pd

    context = AgsContext()
    context.parse_ags(test_datetime_formats_ags_path)

    scpg_table = context.get_table("SCPG")

    assert pd.api.types.is_datetime64_any_dtype(scpg_table["SCPG_DATE"])
    assert pd.api.types.is_datetime64_any_dtype(scpg_table["SCPG_TIME"])

    row = scpg_table.iloc[0]
    assert row["SCPG_DATE"] == pd.Timestamp("2023-11-15")
    assert row["SCPG_TIME"].hour == 14
    assert row["SCPG_TIME"].minute == 30


def test_crs_from_loca_gref_osgb(valid_ags_path):
    """Test LOCA_GREF returns correct EPSG code for OSGB"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    # Modify LOCA table to add LOCA_GREF column with OSGB value
    loca_table = context.get_table("LOCA")
    loca_table["LOCA_GREF"] = "OSGB"

    assert context.crs_from_loca_gref() == 27700


def test_crs_from_loca_gref_local(valid_ags_path):
    """Test LOCA_GREF returns 'unspecified' for LOCAL"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_GREF"] = "LOCAL"

    assert context.crs_from_loca_gref() == "unspecified"


def test_crs_from_loca_gref_unknown(valid_ags_path, caplog):
    """Test LOCA_GREF returns None and logs warning for unknown value"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_GREF"] = "UNKNOWN_CRS"

    assert context.crs_from_loca_gref() is None
    assert "Could not determine CRS from LOCA_GREF: UNKNOWN_CRS" in caplog.text


def test_crs_from_loca_llz_epsg_code(valid_ags_path):
    """Test LOCA_LLZ returns correct EPSG code for EPSG:4326"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_LLZ"] = "EPSG:4326"

    assert context.crs_from_loca_llz() == 4326


def test_crs_from_loca_llz_wgs84(valid_ags_path):
    """Test LOCA_LLZ returns correct EPSG code for WGS84"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_LLZ"] = "WGS84"

    assert context.crs_from_loca_llz() == 4326


def test_crs_from_loca_llz_invalid(valid_ags_path, caplog):
    """Test LOCA_LLZ returns None and logs warning for invalid CRS"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_LLZ"] = "INVALID_CRS"

    assert context.crs_from_loca_llz() is None
    assert "Could not determine CRS from LOCA_LLZ: INVALID_CRS" in caplog.text


def test_coordinate_reference_system_gref_only(valid_ags_path):
    """Test coordinate_reference_system returns GREF value when only GREF is available"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_GREF"] = "OSGB"

    assert context.coordinate_reference_system == 27700


def test_coordinate_reference_system_llz_only(valid_ags_path):
    """Test coordinate_reference_system returns LLZ value when only LLZ is available"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_LLZ"] = "EPSG:4326"

    assert context.coordinate_reference_system == 4326


def test_coordinate_reference_system_both_prefers_gref(valid_ags_path, caplog):
    """Test coordinate_reference_system prefers GREF when both are available"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_GREF"] = "OSGB"
    loca_table["LOCA_LLZ"] = "EPSG:4326"

    assert context.coordinate_reference_system == 27700
    assert "Found CRS for both LOCA_GREF and LOCA_LLZ, preferring LOCA_GREF: 27700" in caplog.text


def test_coordinate_reference_system_neither_available(valid_ags_path):
    """Test coordinate_reference_system returns None when neither GREF nor LLZ are available"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    # Neither column exists by default
    assert context.coordinate_reference_system is None


def test_coordinate_reference_system_local_gref(valid_ags_path):
    """Test coordinate_reference_system returns 'unspecified' for LOCAL GREF"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table("LOCA")
    loca_table["LOCA_GREF"] = "LOCAL"

    assert context.coordinate_reference_system == "unspecified"


def test_coordinate_reference_system_mismatch_in_merge(valid_ags_2a_path, invalid_ags_2d_path, caplog):
    """Test that a mismatch in CRS during merging fails with validation, warns without"""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_2a_path)

    context2 = AgsContext()
    context2.parse_ags(invalid_ags_2d_path)

    # Should raise when validation is enabled (default)
    with pytest.raises(
        ValueError,
        match="Cannot merge AgsContext instances: Incompatible CRS: first has '27700', second has '29902'.",
    ):
        context1.merge(other=context2)

    # Should not raise when validation is disabled, but should log a warning
    context1.merge(other=context2, validate_compatibility=False)
    assert "Incompatible CRS: first has '27700', second has '29902'" in caplog.text


def test_proj_id_mismatch_in_merge(valid_ags_1a_path, valid_ags_2c_path, caplog):
    """Test that a mismatch in PROJ_ID during merging fails with validation, warns without"""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_2c_path)

    # Should raise when validation is enabled (default)
    with pytest.raises(
        ValueError,
        match="Cannot merge AgsContext instances: Incompatible PROJ_ID: first has 'EXAMPLE-1', second has 'EXAMPLE-2'.",
    ):
        context1.merge(other=context2)

    # Should not raise when validation is disabled, but should log a warning
    context1.merge(other=context2, validate_compatibility=False)
    assert "Incompatible PROJ_ID: first has 'EXAMPLE-1', second has 'EXAMPLE-2'" in caplog.text


def test_duplicate_loca_ids_during_merge(valid_ags_2a_path, invalid_ags_2b_path, caplog):
    """Test that duplicate LOCA_IDs are handled during merge, keeping first occurrence"""
    context_2a = AgsContext()
    context_2a.parse_ags(valid_ags_2a_path)

    context_2b = AgsContext()
    context_2b.parse_ags(invalid_ags_2b_path)

    context_2a.merge(other=context_2b)

    # Should have logged a warning about duplicates
    assert "Found 1 duplicate LOCA_ID values when merging contexts" in caplog.text
    assert "EXAMPLE-2-CPT1" in caplog.text

    # LOCA table should have only 1 row (from 2a, as 2b has the same ID)
    loca_table = context_2a.get_table("LOCA")
    assert len(loca_table) == 1
    assert loca_table.iloc[0]["LOCA_ID"] == "EXAMPLE-2-CPT1"
    # Verify we kept the coordinates from first file
    assert loca_table.iloc[0]["LOCA_NATE"] == 575800.00


def test_non_identical_proj_table_warning(valid_ags_2a_path, valid_ags_2c_path, caplog):
    """Test that non-identical PROJ table entries trigger a warning but still allow merge"""
    context_2a = AgsContext()
    context_2a.parse_ags(valid_ags_2a_path)

    context_2c = AgsContext()
    context_2c.parse_ags(valid_ags_2c_path)

    # Merge should succeed despite different PROJ table (same PROJ_ID)
    context_2a.merge(other=context_2c)

    assert "Table 'PROJ' differs between files" in caplog.text
    assert "Keeping values from first context" in caplog.text

    # LOCA table should have both locations
    loca_table = context_2a.get_table("LOCA")
    assert len(loca_table) == 2
    assert set(loca_table["LOCA_ID"]) == {"EXAMPLE-2-CPT1", "EXAMPLE-2-CPT2"}


def test_merge_idempotent(valid_ags_1a_path):
    """Test that merging the same AgsContext multiple times is idempotent"""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_1a_path)

    context1.merge(other=context2)
    context1.merge(other=context2)

    assert context1.headings == context2.headings

    for group_name, table in context1.tables.items():
        assert len(table) == len(context2.tables[group_name]), group_name
        assert table.equals(context2.tables[group_name])


def test_merge_two_files_same_proj_id(valid_ags_1a_path, valid_ags_1b_path):
    """Test merging two files with same PROJ_ID and verify all data is correctly merged."""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_1b_path)

    # Verify both contexts have the same PROJ_ID
    assert context1.proj_id == context2.proj_id == "EXAMPLE-1"

    # Verify initial state before merge
    assert len(context1.get_table("LOCA")) == 1
    assert len(context2.get_table("LOCA")) == 1
    assert context1.get_table("LOCA")["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT1"
    assert context2.get_table("LOCA")["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT2"

    # Get initial counts
    context1_scpt_count = len(context1.get_table("SCPT"))
    context2_scpt_count = len(context2.get_table("SCPT"))

    # Merge context2 into context1. context2 is not modified by this operation
    context1.merge(other=context2)

    # Verify LOCA table has both locations
    loca_table = context1.get_table("LOCA")
    assert len(loca_table) == 2
    loca_ids = set(loca_table["LOCA_ID"])
    assert loca_ids == {"EXAMPLE-1-CPT1", "EXAMPLE-1-CPT2"}

    # Verify LOCA coordinates are preserved
    cpt1_row = loca_table[loca_table["LOCA_ID"] == "EXAMPLE-1-CPT1"].iloc[0]
    cpt2_row = loca_table[loca_table["LOCA_ID"] == "EXAMPLE-1-CPT2"].iloc[0]
    assert cpt1_row["LOCA_NATE"] == 575784.00
    assert cpt1_row["LOCA_NATN"] == 5807006.00
    assert cpt2_row["LOCA_NATE"] == 575784.00
    assert cpt2_row["LOCA_NATN"] == 5807006.00

    # Verify SCPG table has both test entries
    scpg_table = context1.get_table("SCPG")
    assert len(scpg_table) == 2
    scpg_pairs = set(zip(scpg_table["LOCA_ID"], scpg_table["SCPG_TESN"]))
    assert scpg_pairs == {("EXAMPLE-1-CPT1", "1"), ("EXAMPLE-1-CPT2", "1")}

    # Verify SCPT measurement data from both files is present
    scpt_table = context1.get_table("SCPT")
    assert len(scpt_table) == context1_scpt_count + context2_scpt_count
    scpt_loca_ids = set(scpt_table["LOCA_ID"])
    assert scpt_loca_ids == {"EXAMPLE-1-CPT1", "EXAMPLE-1-CPT2"}

    # Verify SCPT data integrity for both locations
    cpt1_scpt = scpt_table[scpt_table["LOCA_ID"] == "EXAMPLE-1-CPT1"]
    cpt2_scpt = scpt_table[scpt_table["LOCA_ID"] == "EXAMPLE-1-CPT2"]
    assert len(cpt1_scpt) == context1_scpt_count
    assert len(cpt2_scpt) == context2_scpt_count

    # Verify original context2 is unchanged
    assert len(context2.get_table("LOCA")) == 1
    assert len(context2.get_table("SCPT")) == context2_scpt_count


def test_merge_multiple_files_different_proj_ids(valid_ags_1a_path, valid_ags_2a_path):
    """Test that files with different PROJ_IDs should not be merged into a single context."""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_2a_path)

    # Verify different PROJ_IDs
    assert context1.proj_id == "EXAMPLE-1"
    assert context2.proj_id == "EXAMPLE-2"

    with pytest.raises(ValueError, match="Cannot merge AgsContext instances: Incompatible PROJ_ID"):
        context1.merge(other=context2)

    # Verify contexts are unchanged after failed merge
    assert len(context1.get_table("LOCA")) == 1
    assert context1.get_table("LOCA")["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT1"
    assert len(context2.get_table("LOCA")) == 1
    assert context2.get_table("LOCA")["LOCA_ID"].iloc[0] == "EXAMPLE-2-CPT1"


def test_merge_with_invalid_file_skipped(valid_ags_1a_path, not_ags_path):
    """Test that invalid files are handled gracefully when parsing multiple files."""
    from evo.data_converters.ags.importer.parse_ags_files import parse_ags_files

    # Parse multiple files including an invalid one
    filepaths = [valid_ags_1a_path, not_ags_path]
    contexts = parse_ags_files(filepaths)

    # Should only return one context (invalid file skipped)
    assert len(contexts) == 1
    assert "EXAMPLE-1" in contexts

    # Verify the valid context has correct data
    context = contexts["EXAMPLE-1"]
    assert len(context.get_table("LOCA")) == 1
    assert context.get_table("LOCA")["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT1"


def test_merge_handles_duplicate_loca_ids_correctly(valid_ags_2a_path, invalid_ags_2b_path, caplog):
    """Test that duplicate LOCA_IDs during merge keeps first occurrence with correct data."""
    context_2a = AgsContext()
    context_2a.parse_ags(valid_ags_2a_path)

    context_2b = AgsContext()
    context_2b.parse_ags(invalid_ags_2b_path)

    # Get the data from 2a before merge
    loca_2a = context_2a.get_table("LOCA")
    cpt1_2a_nate = loca_2a[loca_2a["LOCA_ID"] == "EXAMPLE-2-CPT1"]["LOCA_NATE"].iloc[0]
    cpt1_2a_natn = loca_2a[loca_2a["LOCA_ID"] == "EXAMPLE-2-CPT1"]["LOCA_NATN"].iloc[0]

    # Get the data from 2b (has same LOCA_ID but different coordinates)
    loca_2b = context_2b.get_table("LOCA")
    assert len(loca_2b) == 1
    assert loca_2b["LOCA_ID"].iloc[0] == "EXAMPLE-2-CPT1"
    cpt1_2b_nate = loca_2b["LOCA_NATE"].iloc[0]
    cpt1_2b_natn = loca_2b["LOCA_NATN"].iloc[0]
    # Verify 2b has different coordinates
    assert cpt1_2b_nate == 600000.00  # Different from 2a
    assert cpt1_2b_natn == 5807020.00

    context_2a.merge(other=context_2b)

    # Should have logged warning about duplicate
    assert "Found 1 duplicate LOCA_ID values when merging contexts" in caplog.text

    # LOCA table should have only 1 row (duplicate from 2b was dropped)
    loca_merged = context_2a.get_table("LOCA")
    assert len(loca_merged) == 1
    assert loca_merged["LOCA_ID"].iloc[0] == "EXAMPLE-2-CPT1"

    # Verify we kept the coordinates from 2a (first context), NOT from 2b
    assert loca_merged["LOCA_NATE"].iloc[0] == cpt1_2a_nate == 575800.00
    assert loca_merged["LOCA_NATE"].iloc[0] != cpt1_2b_nate
    assert loca_merged["LOCA_NATN"].iloc[0] == cpt1_2a_natn == 5807020.00

    # Verify SCPG and SCPT tables also kept data from first context
    scpg_merged = context_2a.get_table("SCPG")
    assert len(scpg_merged) == 1
    assert scpg_merged["LOCA_ID"].iloc[0] == "EXAMPLE-2-CPT1"

    scpt_merged = context_2a.get_table("SCPT")
    # All SCPT rows should be from 2a (2b's duplicates were dropped)
    assert all(scpt_merged["LOCA_ID"] == "EXAMPLE-2-CPT1")
    # Should have 7 rows (only from 2a)
    assert len(scpt_merged) == 7
