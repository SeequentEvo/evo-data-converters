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

from pathlib import Path

import pandas as pd
import pytest
from python_ags4 import AGS4
from python_ags4.AGS4 import AGS4Error

from evo.data_converters.ags.common import AgsContext, AgsFileInvalidException, AgsIncompatibleMergeError
from evo.data_converters.ags.common.ags_context import (
    DMS_UNIT,
    LOCA,
    PARSE_FAILURE_REASON,
    PROJ,
    SCPG,
    SCPT,
    ags4_errors_to_diagnostics,
    dms_to_degrees,
    parse_dms,
)


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
        match="Missing importable groups: one or more of SCPT, SCPP, GEOL required.",
    ):
        context.parse_ags(valid_ags_no_cpt_path)


def test_validator_rows_are_normalized_without_raw_row_values() -> None:
    issues = ags4_errors_to_diagnostics(
        {
            "AGS Format Rule 3": [{"line": 7, "group": "", "desc": "Unsafe content that should not be exposed"}],
            "AGS Format Rule 13": [{"line": "-", "group": "PROJ", "desc": "PROJ group not found."}],
        }
    )

    assert [(issue.rule, issue.group, issue.line) for issue in issues] == [
        ("AGS Format Rule 3", None, 7),
        ("AGS Format Rule 13", "PROJ", None),
    ]
    assert issues[0].reason == "A line does not start with a valid AGS data descriptor."
    assert "Unsafe content" not in repr(issues)


def test_legacy_validator_formatter_remains_available() -> None:
    from evo.data_converters.ags.common.ags_context import ags4_errors_to_str

    text = ags4_errors_to_str(
        {
            "AGS Format Rule 3": [{"line": 7, "group": "", "desc": "Invalid descriptor"}],
            "AGS Format Rule 13": [{"line": "-", "group": "PROJ", "desc": "Missing group"}],
        }
    )

    assert text == (
        "\nAGS Format Rule 3:\n  L7, Group NULL: Invalid descriptor\n"
        "\nAGS Format Rule 13:\n  L-, Group PROJ: Missing group\n"
    )


@pytest.mark.parametrize("line", ("0", "-", ""))
def test_validator_rows_without_a_positive_line_have_no_line(line: str) -> None:
    (issue,) = ags4_errors_to_diagnostics({"AGS Format Rule 4": [{"line": line, "group": "LOCA", "desc": "x"}]})

    assert issue.line is None
    assert issue.reason == "Correct the AGS file to comply with AGS Format Rule 4."


def test_validator_rule_5_has_a_quoting_remedy() -> None:
    (issue,) = ags4_errors_to_diagnostics({"AGS Format Rule 5": [{"line": "2", "group": "PROJ", "desc": "x"}]})

    assert (issue.rule, issue.group, issue.line) == ("AGS Format Rule 5", "PROJ", 2)
    assert "double quotes" in issue.reason


def test_validator_reports_ags3_without_the_validator_process_error() -> None:
    issues = ags4_errors_to_diagnostics(
        {
            "AGS Format Rule 3": [{"line": "1", "group": "", "desc": "AGS3 format which is not supported"}],
            "Validator Process Error": [{"line": "-", "group": "", "desc": "Traceback (most recent call last)"}],
        }
    )

    assert [(issue.rule, issue.line) for issue in issues] == [("AGS Format Rule 3", 1)]
    assert "AGS3 files are not supported" in issues[0].reason
    assert "Traceback" not in repr(issues)


@pytest.mark.parametrize("process_key", ("General", "Validator Process Error"))
def test_validator_process_rows_alone_give_a_generic_diagnostic(process_key: str) -> None:
    (issue,) = ags4_errors_to_diagnostics({process_key: [{"line": "-", "group": "", "desc": "Internal details"}]})

    assert (issue.code, issue.severity, issue.rule, issue.line) == ("invalid_file_format", "error", None, None)
    assert "AGS4" in issue.reason
    assert "Internal details" not in repr(issue)


def test_validator_text_is_logged_but_not_raised(not_ags_path: str, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"), pytest.raises(AgsFileInvalidException) as error:
        AgsContext().check_ags_file(not_ags_path)

    assert "Does not start with a valid data descriptor" in caplog.text
    assert "Does not start with a valid data descriptor" not in str(error.value)
    assert all(issue.code == "invalid_file_format" for issue in error.value.diagnostics)


def test_validator_process_failure_is_a_generic_invalid_input(
    valid_ags_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_to_read(*args: object, **kwargs: object) -> None:
        raise AGS4Error("internal parser detail")

    monkeypatch.setattr(AGS4, "AGS4_to_dataframe", fail_to_read)

    with pytest.raises(AgsFileInvalidException) as error:
        AgsContext().check_ags_file(valid_ags_path)

    assert [(issue.code, issue.rule) for issue in error.value.diagnostics] == [("invalid_file_format", None)]
    assert "internal parser detail" not in str(error.value)


def test_unreadable_ags_contents_are_a_typed_invalid_input(
    valid_ags_path: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail_to_read(*args: object, **kwargs: object) -> None:
        raise AGS4Error("internal parser detail")

    monkeypatch.setattr(AgsContext, "check_ags_file", lambda self, filepath: None)
    monkeypatch.setattr(AGS4, "AGS4_to_dataframe", fail_to_read)

    with caplog.at_level("WARNING"), pytest.raises(AgsFileInvalidException) as error:
        AgsContext().parse_ags(valid_ags_path)

    assert error.value.code == "invalid_file_format"
    assert error.value.reason == PARSE_FAILURE_REASON
    assert isinstance(error.value.__cause__, AGS4Error)
    assert "internal parser detail" not in str(error.value)
    assert "internal parser detail" in caplog.text


@pytest.mark.parametrize(
    "args, expected_reason",
    (
        ((), PARSE_FAILURE_REASON),
        (("first", "second"), "first"),
    ),
)
def test_invalid_file_exception_reason_defaults(args: tuple[str, ...], expected_reason: str) -> None:
    error = AgsFileInvalidException(*args)

    assert error.args == args
    assert error.reason == expected_reason
    assert (error.code, error.rule, error.group, error.line, error.diagnostics) == (
        "invalid_file_format",
        None,
        None,
        None,
        (),
    )


@pytest.mark.parametrize(
    "table",
    (
        None,
        pd.DataFrame(columns=["PROJ_ID"]),
        pd.DataFrame({"PROJ_NAME": ["Project"]}),
    ),
    ids=("no-proj-table", "no-proj-row", "no-proj-id-column"),
)
def test_missing_proj_id_is_a_typed_invalid_input(table: pd.DataFrame | None) -> None:
    context = AgsContext()
    if table is not None:
        context.set_table(PROJ, table)

    with pytest.raises(AgsFileInvalidException, match="PROJ_ID not found") as error:
        _ = context.proj_id

    assert error.value.code == "invalid_file_format"
    assert error.value.reason == "Add a PROJ group containing a PROJ_ID."
    assert isinstance(error.value.__cause__, KeyError)


def test_blank_proj_id_is_returned_as_is() -> None:
    context = AgsContext()
    context.set_table(PROJ, pd.DataFrame({"PROJ_ID": [""]}))

    assert context.proj_id == ""


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
        LOCA,
        SCPG,
        SCPT,
    ]
    for table_name in expected_tables:
        assert table_name in context.tables
        assert not context.tables[table_name].empty
        assert table_name in context.headings
        assert len(context.headings[table_name]) > 0


def test_valid_ags_units(valid_ags_path):
    """Units come from the UNIT rows, except where the conversion consumes them or the column has none"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_units = context.get_units(LOCA)
    assert loca_units["LOCA_NATE"] == "m"
    assert loca_units["LOCA_LAT"] == DMS_UNIT
    assert loca_units["LOCA_LON"] == DMS_UNIT
    assert "HEADING" not in loca_units
    assert "LOCA_ID" not in loca_units
    assert "LOCA_STAR" not in loca_units

    scpt_units = context.get_units(SCPT)
    assert scpt_units["SCPT_DPTH"] == "m"
    assert scpt_units["SCPT_RES"] == "MN/m2"
    assert scpt_units["SCPT_FRR"] == "%"
    assert context.get_units("MISSING") == {}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("51:28:52.498", 51 + 28 / 60 + 52.498 / 3600),
        ("-0:07:39.6", -(7 / 60 + 39.6 / 3600)),
        ("-0:30:00", -0.5),
        ("+1:30", 1.5),
        ("51:28:52.498N", 51 + 28 / 60 + 52.498 / 3600),
        ("N51:28:52.498", 51 + 28 / 60 + 52.498 / 3600),
        (" 0:30:00 s ", -0.5),
        ("W 0:30", -0.5),
        ("1:30E", 1.5),
        ("51.5", 51.5),
        ("-0.25", -0.25),
        (".5", 0.5),
        (12, 12.0),
        (-1.5, -1.5),
    ],
)
def test_parse_dms(value, expected):
    assert parse_dms(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    "value",
    ["", "  ", None, True, "abc", "1:60:00", "1:00:60", "-1:30N", "+1:30S", "1:30.5:10", "1:2:3:4", "N"],
)
def test_parse_dms_unreadable_values_are_missing(value):
    assert pd.isna(parse_dms(value))


def test_dms_to_degrees_warns_about_unreadable_values(caplog):
    series = pd.Series(["51:30:00", "", None, "abc", "1:60:00"])

    with caplog.at_level("WARNING"):
        result = dms_to_degrees(series, "LOCA_LAT")

    assert result.dtype == "float64"
    assert result.iloc[0] == pytest.approx(51.5)
    assert result.iloc[1:].isna().all()
    assert "Could not read 2 values of LOCA_LAT as degrees, minutes and seconds" in caplog.text


def test_dms_to_degrees_without_unreadable_values_does_not_warn(caplog):
    with caplog.at_level("WARNING"):
        dms_to_degrees(pd.Series(["51:30:00", ""]), "LOCA_LAT")

    assert "LOCA_LAT" not in caplog.text


def test_dms_columns_are_parsed(tmp_path, valid_ags_path):
    """DMS values in LOCA_LAT and LOCA_LON are read as decimal degrees"""
    text = Path(valid_ags_path).read_text()
    loca_row = '"50.49","2025-06-17","","","","","","",""'
    assert text.count(loca_row) == 1
    path = tmp_path / "dms.ags"
    path.write_text(text.replace(loca_row, '"50.49","2025-06-17","","","","","51:28:52.498N","0:07:39.6W",""'))

    context = AgsContext()
    context.parse_ags(path)

    loca = context.get_table(LOCA)
    assert loca["LOCA_LAT"].iloc[0] == pytest.approx(51.48125, abs=1e-6)
    assert loca["LOCA_LON"].iloc[0] == pytest.approx(-0.1277, abs=1e-4)


def test_timedelta_type_conversion(test_timedelta_ags_path):
    """Test that T type with different time units is converted to pandas Timedelta"""
    import pandas as pd

    context = AgsContext()
    context.parse_ags(test_timedelta_ags_path)

    scpg_table = context.get_table(SCPG)

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

    scpg_table = context.get_table(SCPG)

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
    loca_table = context.get_table(LOCA)
    loca_table["LOCA_GREF"] = "OSGB"

    assert context.crs_from_loca_gref() == {"EXAMPLE-1-CPT1": 27700}


def test_crs_from_loca_gref_local(valid_ags_path):
    """Test LOCA_GREF returns 'unspecified' for LOCAL"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_GREF"] = "LOCAL"

    assert context.crs_from_loca_gref() == {"EXAMPLE-1-CPT1": "unspecified"}


def test_crs_from_loca_gref_unknown(valid_ags_path, caplog):
    """Test LOCA_GREF returns None and logs warning for unknown value"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_GREF"] = "UNKNOWN_CRS"

    assert context.crs_from_loca_gref() == {"EXAMPLE-1-CPT1": None}
    assert "Could not determine CRS from LOCA_GREF: UNKNOWN_CRS" in caplog.text


def test_crs_from_loca_llz_epsg_code(valid_ags_path):
    """Test LOCA_LLZ returns correct EPSG code for EPSG:4326"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_LLZ"] = "EPSG:4326"

    assert context.crs_from_loca_llz() == {"EXAMPLE-1-CPT1": 4326}


def test_crs_from_loca_llz_wgs84(valid_ags_path):
    """Test LOCA_LLZ returns correct EPSG code for WGS84"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_LLZ"] = "WGS84"

    assert context.crs_from_loca_llz() == {"EXAMPLE-1-CPT1": 4326}


def test_crs_from_loca_llz_invalid(valid_ags_path, caplog):
    """Test LOCA_LLZ returns None and logs warning for invalid CRS"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_LLZ"] = "INVALID_CRS"

    assert context.crs_from_loca_llz() == {"EXAMPLE-1-CPT1": None}
    assert "Could not determine CRS from LOCA_LLZ: INVALID_CRS" in caplog.text


def test_coordinate_reference_system_gref_only(valid_ags_path):
    """Test coordinate_reference_system returns GREF value when only GREF is available"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_GREF"] = "OSGB"

    assert context.coordinate_reference_system == 27700


def test_coordinate_reference_system_llz_only(valid_ags_path):
    """Test coordinate_reference_system returns LLZ value when only LLZ is available"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_LLZ"] = "EPSG:4326"

    assert context.coordinate_reference_system == 4326


def test_coordinate_reference_system_both_prefers_gref(valid_ags_path, caplog):
    """Test coordinate_reference_system prefers GREF when both are available"""
    context = AgsContext()
    context.parse_ags(valid_ags_path)

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_GREF"] = "OSGB"
    loca_table["LOCA_LLZ"] = "EPSG:4326"

    assert context.coordinate_reference_system == 27700
    assert (
        "Found CRS for both LOCA_GREF and LOCA_LLZ, preferring LOCA_GREF for LOCA_IDs: ['EXAMPLE-1-CPT1']"
        in caplog.text
    )


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

    loca_table = context.get_table(LOCA)
    loca_table["LOCA_GREF"] = "LOCAL"

    assert context.coordinate_reference_system == "unspecified"


def _context_with_loca(**columns: list[str]) -> AgsContext:
    context = AgsContext()
    context.set_table(LOCA, pd.DataFrame({"LOCA_ID": ["BH01", "BH02", "BH03"], **columns}))
    return context


def test_coordinate_reference_system_resolved_per_location():
    """Test equivalent CRS declarations from different LOCA rows and columns resolve to one CRS"""
    context = _context_with_loca(LOCA_GREF=["OSGB", "EPSG:27700", ""], LOCA_LLZ=["", "", "EPSG:27700"])

    assert context.coordinate_reference_system == 27700


def test_coordinate_reference_system_rows_without_crs_adopt_shared_crs(caplog):
    """Test LOCA rows without a CRS adopt the CRS declared by the other rows, with a warning"""
    context = _context_with_loca(LOCA_GREF=["OSGB", "", "OSGB"])

    assert context.coordinate_reference_system == 27700
    assert "No CRS declared for LOCA_IDs: ['BH02'], assuming 27700" in caplog.text


def test_coordinate_reference_system_invalid_value_warns_once(caplog):
    """Test an unresolvable CRS repeated across LOCA rows is reported once"""
    context = _context_with_loca(LOCA_GREF=["NOT_A_CRS", "NOT_A_CRS", "NOT_A_CRS"])

    assert context.coordinate_reference_system is None
    assert caplog.text.count("Could not determine CRS from LOCA_GREF: NOT_A_CRS") == 1


@pytest.mark.parametrize(
    "columns",
    [
        {"LOCA_GREF": ["OSGB", "OSGB", "ITM"]},
        {"LOCA_GREF": ["OSGB", "", ""], "LOCA_LLZ": ["", "WGS84", ""]},
        {"LOCA_GREF": ["OSGB", "LOCAL", "OSGB"]},
    ],
    ids=["different_gref", "gref_and_llz_rows", "national_and_local"],
)
def test_coordinate_reference_system_conflicting_locations_raise(columns):
    """Test LOCA rows declaring different CRSs are rejected instead of sharing one CRS"""
    context = _context_with_loca(**columns)

    with pytest.raises(AgsFileInvalidException, match="LOCA rows declare different coordinate reference systems"):
        _ = context.coordinate_reference_system


def test_parse_ags_rejects_conflicting_crs(conflicting_crs_ags_path: str) -> None:
    """An AGS file whose LOCA rows declare different CRSs cannot be imported"""
    context = AgsContext()
    with pytest.raises(
        AgsFileInvalidException, match="LOCA rows declare different coordinate reference systems"
    ) as error:
        context.parse_ags(conflicting_crs_ags_path)

    assert error.value.code == "invalid_coordinates"
    assert error.value.reason == "Use one coordinate reference system for all LOCA rows."


@pytest.mark.parametrize("include_required_groups", [True, False])
def test_validate_ags_reports_conflicting_crs(include_required_groups: bool) -> None:
    context = _context_with_loca(LOCA_GREF=["OSGB", "ITM", "OSGB"])
    if include_required_groups:
        for group in AgsContext.REQUIRED_GROUPS:
            context.set_heading(group, ["LOCA_ID"])

    errors = context.validate_ags()

    assert any("different coordinate reference systems" in error for error in errors)
    if not include_required_groups:
        assert "Missing required group: SCPT." in errors
        assert any("Missing importable groups" in error for error in errors)


def test_merge_with_conflicting_crs_file_skipped(test_elevations_ags_path, conflicting_crs_ags_path, caplog):
    """Test that a file with conflicting CRSs is skipped instead of failing the merge of the other files"""
    from evo.data_converters.ags.importer.parse_ags_files import parse_ags_files

    contexts = parse_ags_files([test_elevations_ags_path, conflicting_crs_ags_path])

    assert len(contexts) == 1
    assert contexts[0].get_table(LOCA)["LOCA_ID"].tolist() == ["BH01", "BH02", "BH03", "BH04", "BH05"]
    assert "Failed to parse AGS file" in caplog.text
    assert conflicting_crs_ags_path in caplog.text


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
    loca_table = context_2a.get_table(LOCA)
    assert len(loca_table) == 1
    assert loca_table.iloc[0]["LOCA_ID"] == "EXAMPLE-2-CPT1"
    # Verify we kept the coordinates from first file
    assert loca_table.iloc[0]["LOCA_NATE"] == 575800.00


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
    assert len(context1.get_table(LOCA)) == 1
    assert len(context2.get_table(LOCA)) == 1
    assert context1.get_table(LOCA)["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT1"
    assert context2.get_table(LOCA)["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT2"

    # Get initial counts
    context1_scpt_count = len(context1.get_table(SCPT))
    context2_scpt_count = len(context2.get_table(SCPT))

    # Merge context2 into context1. context2 is not modified by this operation
    context1.merge(other=context2)

    # Verify LOCA table has both locations
    loca_table = context1.get_table(LOCA)
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
    scpg_table = context1.get_table(SCPG)
    assert len(scpg_table) == 2
    scpg_pairs = set(zip(scpg_table["LOCA_ID"], scpg_table["SCPG_TESN"]))
    assert scpg_pairs == {("EXAMPLE-1-CPT1", "1"), ("EXAMPLE-1-CPT2", "1")}

    # Verify SCPT measurement data from both files is present
    scpt_table = context1.get_table(SCPT)
    assert len(scpt_table) == context1_scpt_count + context2_scpt_count
    scpt_loca_ids = set(scpt_table["LOCA_ID"])
    assert scpt_loca_ids == {"EXAMPLE-1-CPT1", "EXAMPLE-1-CPT2"}

    # Verify SCPT data integrity for both locations
    cpt1_scpt = scpt_table[scpt_table["LOCA_ID"] == "EXAMPLE-1-CPT1"]
    cpt2_scpt = scpt_table[scpt_table["LOCA_ID"] == "EXAMPLE-1-CPT2"]
    assert len(cpt1_scpt) == context1_scpt_count
    assert len(cpt2_scpt) == context2_scpt_count

    # Verify original context2 is unchanged
    assert len(context2.get_table(LOCA)) == 1
    assert len(context2.get_table(SCPT)) == context2_scpt_count


def test_merge_multiple_files_different_proj_ids(valid_ags_1a_path, valid_ags_2a_path):
    """Test that files with different PROJ_IDs should not be merged into a single context."""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_2a_path)

    # Verify different PROJ_IDs
    assert context1.proj_id == "EXAMPLE-1"
    assert context2.proj_id == "EXAMPLE-2"

    with pytest.raises(ValueError, match="Cannot merge AgsContext instances: Incompatible PROJ_ID") as error:
        context1.merge(other=context2)

    assert isinstance(error.value, AgsIncompatibleMergeError)
    assert context1.validate_merge(context2, raise_on_error=False)[0].startswith("Incompatible PROJ_ID")

    # Verify contexts are unchanged after failed merge
    assert len(context1.get_table(LOCA)) == 1
    assert context1.get_table(LOCA)["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT1"
    assert len(context2.get_table(LOCA)) == 1
    assert context2.get_table(LOCA)["LOCA_ID"].iloc[0] == "EXAMPLE-2-CPT1"


def test_merge_with_invalid_file_skipped(valid_ags_1a_path, not_ags_path):
    """Test that invalid files are handled gracefully when parsing multiple files."""
    from evo.data_converters.ags.importer.parse_ags_files import parse_ags_files

    # Parse multiple files including an invalid one
    filepaths = [valid_ags_1a_path, not_ags_path]
    contexts = parse_ags_files(filepaths)

    # Should only return one context (invalid file skipped)
    assert len(contexts) == 1
    assert contexts[0].proj_id == "EXAMPLE-1"

    # Verify the valid context has correct data
    context = contexts[0]
    assert len(context.get_table(LOCA)) == 1
    assert context.get_table(LOCA)["LOCA_ID"].iloc[0] == "EXAMPLE-1-CPT1"


def test_merge_handles_duplicate_loca_ids_correctly(valid_ags_2a_path, invalid_ags_2b_path, caplog):
    """Test that duplicate LOCA_IDs during merge keeps first occurrence with correct data."""
    context_2a = AgsContext()
    context_2a.parse_ags(valid_ags_2a_path)

    context_2b = AgsContext()
    context_2b.parse_ags(invalid_ags_2b_path)

    # Get the data from 2a before merge
    loca_2a = context_2a.get_table(LOCA)
    cpt1_2a_nate = loca_2a[loca_2a["LOCA_ID"] == "EXAMPLE-2-CPT1"]["LOCA_NATE"].iloc[0]
    cpt1_2a_natn = loca_2a[loca_2a["LOCA_ID"] == "EXAMPLE-2-CPT1"]["LOCA_NATN"].iloc[0]

    # Get the data from 2b (has same LOCA_ID but different coordinates)
    loca_2b = context_2b.get_table(LOCA)
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
    loca_merged = context_2a.get_table(LOCA)
    assert len(loca_merged) == 1
    assert loca_merged["LOCA_ID"].iloc[0] == "EXAMPLE-2-CPT1"

    # Verify we kept the coordinates from 2a (first context), NOT from 2b
    assert loca_merged["LOCA_NATE"].iloc[0] == cpt1_2a_nate == 575800.00
    assert loca_merged["LOCA_NATE"].iloc[0] != cpt1_2b_nate
    assert loca_merged["LOCA_NATN"].iloc[0] == cpt1_2a_natn == 5807020.00

    # Verify SCPG and SCPT tables also kept data from first context
    scpg_merged = context_2a.get_table(SCPG)
    assert len(scpg_merged) == 1
    assert scpg_merged["LOCA_ID"].iloc[0] == "EXAMPLE-2-CPT1"

    scpt_merged = context_2a.get_table(SCPT)
    # All SCPT rows should be from 2a (2b's duplicates were dropped)
    assert all(scpt_merged["LOCA_ID"] == "EXAMPLE-2-CPT1")
    # Should have 7 rows (only from 2a)
    assert len(scpt_merged) == 7


def test_units_are_merged(valid_ags_1a_path, valid_ags_1b_path):
    """Units declared in either context are kept, and the other context is left unchanged"""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_1b_path)
    context2.set_units(SCPT, {**context2.get_units(SCPT), "SCPT_EXTRA": "kN/m2"})
    other_units = context2.get_units(SCPT).copy()

    context1.merge(other=context2)

    assert context1.get_units(SCPT)["SCPT_RES"] == "MN/m2"
    assert context1.get_units(SCPT)["SCPT_EXTRA"] == "kN/m2"
    assert context2.get_units(SCPT) == other_units


def test_unit_mismatch_in_merge(valid_ags_1a_path, valid_ags_1b_path, caplog):
    """Test that a column in different units fails with validation, warns without, and keeps the first unit"""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_1b_path)
    context2.set_units(SCPT, {**context2.get_units(SCPT), "SCPT_RES": "kN/m2"})
    scpt_rows = len(context1.get_table(SCPT))

    with pytest.raises(
        AgsIncompatibleMergeError,
        match="Incompatible units for SCPT.SCPT_RES: first has 'MN/m2', second has 'kN/m2'",
    ):
        context1.merge(other=context2)
    assert len(context1.get_table(SCPT)) == scpt_rows

    context1.merge(other=context2, validate_compatibility=False)
    assert "Incompatible units for SCPT.SCPT_RES" in caplog.text
    assert context1.get_units(SCPT)["SCPT_RES"] == "MN/m2"


def test_duplicate_measurement_rows_during_merge_warn(valid_ags_1a_path, caplog):
    """Identical measurement rows from both contexts are kept once, with a warning"""
    context1 = AgsContext()
    context1.parse_ags(valid_ags_1a_path)

    context2 = AgsContext()
    context2.parse_ags(valid_ags_1a_path)
    scpt_rows = len(context2.get_table(SCPT))

    with caplog.at_level("WARNING"):
        context1.merge(other=context2)

    assert f"Found {scpt_rows} duplicate SCPT rows when merging contexts. Keeping one of each." in caplog.text
    assert len(context1.get_table(SCPT)) == scpt_rows
