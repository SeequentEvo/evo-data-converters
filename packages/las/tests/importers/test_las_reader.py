#  Copyright © 2026 Bentley Systems, Incorporated
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

import numpy as np
import pytest

from evo.data_converters.las.importer.dev_reader import read_dev_file
from evo.data_converters.las.importer.las_reader import LASDataFileIOError, LASInvalidDataError, read_las_file

DATA = Path(__file__).parent.parent / "data"

_HEADER = """~Version
VERS. 2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0
WRAP. {wrap} : wrap mode
~Well
STRT.{unit} 100.0 : START
STOP.{unit} 102.0 : STOP
STEP.{unit} 1.0 : STEP
NULL. -999.25 : NULL
WELL. W-1 : WELL
~Curve
{index}.{unit} : Index
GR.GAPI : Gamma
POR. : Porosity
~Params
~Other
free text
"""


def _write(tmp_path: Path, text: str, name: str = "a.las") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_read_sample_file() -> None:
    las = read_las_file(DATA / "BR-I-1_V2.las")
    assert las.hole_id == "BR-I-1"
    assert las.curves[0].mnemonic == "DEPT"
    assert [c.mnemonic for c in las.curves[1:4]] == ["BVW", "CAPPOR", "DEPT2"]
    assert las.data.shape[1] == len(las.curves)
    assert las.index[0] == pytest.approx(1690.2067)
    assert las.depth_in_metres[-1] == pytest.approx(1777.4433, abs=1e-3)
    assert not np.any(las.data == -999.25)


def test_wrapped_with_comments_and_nulls(tmp_path: Path) -> None:
    text = _HEADER.format(wrap="YES", unit="M", index="DEPT") + "~A\n# comment\n100.0\n50 0.2\n101.0\n-999.25 0.3\n"
    las = read_las_file(_write(tmp_path, text))
    assert las.index.tolist() == [100.0, 101.0]
    assert las.data[0, 1:].tolist() == [50.0, 0.2]
    assert np.isnan(las.data[1, 1])


def test_feet_converted_to_metres(tmp_path: Path) -> None:
    text = _HEADER.format(wrap="NO", unit="F", index="DEPT") + "~A\n100 1 2\n101 3 4\n"
    las = read_las_file(_write(tmp_path, text))
    assert las.depth_in_metres.tolist() == pytest.approx([30.48, 30.7848])


def test_time_index_rejected(tmp_path: Path) -> None:
    text = _HEADER.format(wrap="NO", unit="S", index="TIME") + "~A\n100 1 2\n"
    with pytest.raises(LASInvalidDataError):
        read_las_file(_write(tmp_path, text))


def test_missing_ascii_section(tmp_path: Path) -> None:
    with pytest.raises(LASInvalidDataError):
        read_las_file(_write(tmp_path, _HEADER.format(wrap="NO", unit="M", index="DEPT")))


def test_wrong_column_count(tmp_path: Path) -> None:
    text = _HEADER.format(wrap="NO", unit="M", index="DEPT") + "~A\n100 1\n"
    with pytest.raises(LASInvalidDataError):
        read_las_file(_write(tmp_path, text))


def test_missing_file() -> None:
    with pytest.raises(LASDataFileIOError):
        read_las_file("does-not-exist.las")


def test_read_dev_file() -> None:
    dev = read_dev_file(DATA / "BR-I-1.dev")
    assert dev.well_name == "BR-I-1"
    assert dev.collar == (-113.0, 5648.0, 35.0)
    assert dev.survey[:, 0].tolist() == [0.0, 1300.0, 1900.0]
    assert np.allclose(dev.survey[:, 2], 90.0)  # vertical: INCL 0 -> dip 90


def test_dev_inclination_converted_to_dip(tmp_path: Path) -> None:
    text = (
        "# WELL NAME: W-2\n# WELL HEAD X-COORDINATE: 1\n# WELL HEAD Y-COORDINATE: 2\n# WELL KB: 3\n"
        "MD X Y Z TVD DX DY AZIM INCL DLS\n"
        "0 1 2 3 0 0 0 0 0 0\n100 1 2 -97 100 0 0 45 30 0\n"
    )
    path = tmp_path / "w2.dev"
    path.write_text(text)
    dev = read_dev_file(path)
    assert dev.survey[1].tolist() == [100.0, 45.0, 60.0]
