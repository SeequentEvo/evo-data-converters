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
from unittest import skip
from evo.data_converters.ags.common import AgsContext, AgsFileInvalidException


def test_not_ags_file():
    """An AGS file not conforming to spec cannot be imported"""
    filepath = _get_path("not_ags.ags")
    context = AgsContext()
    with pytest.raises(AgsFileInvalidException, match="AGS Format Rule 2a"):
        context.parse_ags(filepath)


def test_ags_file_missing_cpt_groups():
    """An AGS file without cpt data cannot be imported"""
    context = AgsContext()
    with pytest.raises(
        AgsFileInvalidException,
        match="Missing importable groups: one or more of SCPG, SCPT, SCPP required.",
    ):
        context.parse_ags(_get_path("valid_ags_no_cpt.ags"))


def test_file_not_found():
    """An AGS file not found cannot be imported"""
    context = AgsContext()
    with pytest.raises(FileNotFoundError):
        context.parse_ags(_get_path("does_not_exist.ags"))


def test_valid_ags():
    """An AGS with correct structure and required tables present can be imported"""
    context = AgsContext()
    context.parse_ags(_get_path("valid_ags.ags"))
    assert context.headings == {
        "PROJ": [
            "HEADING",
            "PROJ_ID",
            "PROJ_NAME",
            "PROJ_LOC",
            "PROJ_CLNT",
            "PROJ_CONT",
            "PROJ_ENG",
            "PROJ_MEMO",
            "FILE_FSET",
        ],
        "TRAN": [
            "HEADING",
            "TRAN_ISNO",
            "TRAN_DATE",
            "TRAN_PROD",
            "TRAN_STAT",
            "TRAN_DESC",
            "TRAN_AGS",
            "TRAN_RECV",
            "TRAN_DLIM",
            "TRAN_RCON",
            "TRAN_REM",
            "FILE_FSET",
        ],
        "ABBR": ["HEADING", "ABBR_HDNG", "ABBR_CODE", "ABBR_DESC"],
        "TYPE": ["HEADING", "TYPE_TYPE", "TYPE_DESC"],
        "DICT": [
            "HEADING",
            "DICT_TYPE",
            "DICT_GRP",
            "DICT_HDNG",
            "DICT_STAT",
            "DICT_DTYP",
            "DICT_DESC",
            "DICT_UNIT",
            "DICT_EXMP",
            "DICT_PGRP",
        ],
        "UNIT": ["HEADING", "UNIT_UNIT", "UNIT_DESC"],
        "LOCA": [
            "HEADING",
            "LOCA_ID",
            "LOCA_TYPE",
            "LOCA_STAT",
            "LOCA_NATE",
            "LOCA_NATN",
            "LOCA_GL",
            "LOCA_REM",
            "LOCA_FDEP",
            "LOCA_STAR",
            "LOCA_PURP",
            "LOCA_TERM",
            "LOCA_ENDD",
            "LOCA_DATM",
            "LOCA_LAT",
            "LOCA_LON",
            "LOCA_LLZ",
        ],
        "HDPH": [
            "HEADING",
            "LOCA_ID",
            "HDPH_TOP",
            "HDPH_BASE",
            "HDPH_TYPE",
            "HDPH_STAR",
            "HDPH_ENDD",
            "HDPH_CREW",
            "HDPH_EXC",
            "HDPH_SHOR",
            "HDPH_STAB",
            "HDPH_DIML",
            "HDPH_DIMW",
            "HDPH_DBIT",
            "HDPH_BCON",
            "HDPH_BTYP",
            "HDPH_BLEN",
            "HDPH_LOG",
            "HDPH_LOGD",
            "HDPH_REM",
            "HDPH_ENV",
            "HDPH_METH",
            "HDPH_CONT",
            "FILE_FSET",
        ],
        "SCPG": [
            "HEADING",
            "LOCA_ID",
            "SCPG_TESN",
            "SCPG_TYPE",
            "SCPG_REF",
            "SCPG_CSA",
            "SCPG_RATE",
            "SCPG_FILT",
            "SCPG_FRIC",
            "SCPG_WAT",
            "SCPG_WATA",
            "SCPG_REM",
            "SCPG_ENV",
            "SCPG_CONT",
            "SCPG_METH",
            "SCPG_CRED",
            "SCPG_CAR",
            "SCPG_SLAR",
            "FILE_FSET",
            "SCPG_CDIA",
            "SCPG_SLVL",
            "SCPG_SLVA",
            "SCPG_ZLOC",
        ],
        "SCPT": [
            "HEADING",
            "LOCA_ID",
            "SCPG_TESN",
            "SCPT_DPTH",
            "SCPT_RES",
            "SCPT_FRES",
            "SCPT_PWP2",
            "SCPT_FRR",
            "SCPT_QT",
            "SCPT_QNET",
            "SCPT_BQ",
            "FILE_FSET",
        ],
    }


@skip("XLSX not yet generated")
def test_valid_xlsx():
    """A valid AGS in XLSX format can be imported"""
    context = AgsContext()
    context.parse_ags(_get_path("valid_ags.xlsx"))


def _get_path(filename: str) -> Path:
    return (Path(__file__).parent / "data" / filename).resolve()
