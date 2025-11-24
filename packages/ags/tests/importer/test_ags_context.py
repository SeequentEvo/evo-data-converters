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
