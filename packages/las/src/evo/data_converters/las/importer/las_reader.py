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

"""Reader for CWLS LAS 2.0 well log files.

Header lines have the form ``MNEM.UNIT   DATA : DESCRIPTION``. The mnemonic ends at the first
dot, the unit ends at the first space after that dot, and the description starts after the last colon.
"""

import logging
import os
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

logger = logging.getLogger("data_converters.las")

DEFAULT_NULL_VALUE = -999.25
_DEPTH_MNEMONICS = {"DEPT", "DEPTH"}
_NON_DEPTH_MNEMONICS = {"TIME", "INDEX"}
_METRE_UNITS = {"m", "meter", "meters", "metre", "metres"}
_FEET_UNITS = {"f", "ft", "foot", "feet"}
_METRES_PER_FOOT = 0.3048
_DELIMITERS = {"SPACE": None, "COMMA": ",", "TAB": "\t"}


class LASInvalidDataError(Exception):
    """Raised when the contents of a LAS file are malformed or fail validation."""


class LASDataFileIOError(Exception):
    """Raised when a LAS file cannot be opened or read."""


@dataclass
class LASHeaderItem:
    mnemonic: str
    unit: str
    value: str
    description: str


@dataclass
class LASCurve:
    mnemonic: str
    unit: str
    description: str


@dataclass
class LASFile:
    """The parsed contents of a LAS 2.0 file. All values are in the units of the file."""

    filepath: str
    version: str
    wrapped: bool
    null_value: float
    well: dict[str, LASHeaderItem]
    parameters: dict[str, LASHeaderItem]
    curves: list[LASCurve]
    data: npt.NDArray[np.float64] = field(repr=False)  # rows x curves, null values replaced with NaN

    @property
    def index(self) -> npt.NDArray[np.float64]:
        return self.data[:, 0]

    @property
    def index_unit(self) -> str:
        """The unit of the index curve: ``m`` or ``ft``."""
        unit = self.curves[0].unit.strip().lower()
        if unit in _FEET_UNITS:
            return "ft"
        if unit in _METRE_UNITS:
            return "m"
        # Fall back to the unit declared against STRT, then assume metres.
        strt = self.well.get("STRT")
        strt_unit = strt.unit.strip().lower() if strt else ""
        if strt_unit in _FEET_UNITS:
            return "ft"
        if strt_unit not in _METRE_UNITS:
            logger.warning(f"{self.filepath}: unknown depth unit '{unit}', assuming metres")
        return "m"

    @property
    def depth_in_metres(self) -> npt.NDArray[np.float64]:
        factor = _METRES_PER_FOOT if self.index_unit == "ft" else 1.0
        return self.index * factor

    @property
    def hole_id(self) -> str:
        """The well name (WELL), falling back to the unique well id (UWI) and then the file name."""
        for key in ("WELL", "UWI"):
            item = self.well.get(key)
            if item is not None and item.value.strip():
                return item.value.strip()
        return os.path.splitext(os.path.basename(self.filepath))[0]


def _parse_header_line(line: str, section: str, filepath: str, line_number: int) -> LASHeaderItem:
    dot = line.find(".")
    colon = line.rfind(":")
    if dot < 0 or colon < dot:
        raise LASInvalidDataError(
            f"{filepath}:{line_number}: malformed line in ~{section} section, expected 'MNEM.UNIT DATA : DESCRIPTION'"
        )
    mnemonic = line[:dot].strip()
    rest = line[dot + 1 : colon]
    unit_end = rest.find(" ")
    if unit_end < 0:
        unit, value = rest, ""
    else:
        unit, value = rest[:unit_end], rest[unit_end + 1 :]
    if not mnemonic:
        raise LASInvalidDataError(f"{filepath}:{line_number}: missing mnemonic in ~{section} section")
    return LASHeaderItem(mnemonic.upper(), unit.strip(), value.strip(), line[colon + 1 :].strip())


def _read_text(filepath: str) -> str:
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise LASDataFileIOError(f"Unable to read LAS file '{filepath}': {e}") from e
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def read_las_file(filepath: str | os.PathLike) -> LASFile:
    """Read a LAS 2.0 file.

    :param filepath: Path to the LAS file to read.
    :return: The parsed file, with null values replaced by NaN.

    :raise LASDataFileIOError: If the file cannot be opened or read.
    :raise LASInvalidDataError: If the file contents are invalid, or the index is not depth.
    """
    filepath = os.fspath(filepath)
    text = _read_text(filepath)

    sections: dict[str, list[tuple[int, str]]] = {}
    current: str | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("~"):
            current = line[1:2].upper()
            if not current or current not in "VWCPOA":
                raise LASInvalidDataError(f"{filepath}:{line_number}: unknown section '{line}'")
            if current in sections:
                raise LASInvalidDataError(f"{filepath}:{line_number}: duplicate section '{line}'")
            sections[current] = []
        elif current is None:
            raise LASInvalidDataError(f"{filepath}:{line_number}: content found before the first section")
        else:
            sections[current].append((line_number, line))

    for required, name in (("V", "Version"), ("W", "Well"), ("C", "Curve"), ("A", "ASCII")):
        if required not in sections:
            raise LASInvalidDataError(f"{filepath}: missing required ~{name} section")

    def header(section: str) -> dict[str, LASHeaderItem]:
        items: dict[str, LASHeaderItem] = {}
        for line_number, line in sections.get(section, []):
            item = _parse_header_line(line, section, filepath, line_number)
            items.setdefault(item.mnemonic, item)
        return items

    version = header("V")
    well = header("W")
    parameters = header("P")

    vers = version.get("VERS")
    if vers is None or not vers.value.startswith("2"):
        raise LASInvalidDataError(
            f"{filepath}: only LAS 2.0 files are supported (VERS = '{vers.value if vers else ''}')"
        )
    wrap = version.get("WRAP")
    wrapped = wrap is not None and wrap.value.strip().upper() == "YES"
    dlm = version.get("DLM")
    delimiter_name = dlm.value.strip().upper() if dlm and dlm.value.strip() else "SPACE"
    if delimiter_name not in _DELIMITERS:
        raise LASInvalidDataError(f"{filepath}: unsupported delimiter DLM = '{delimiter_name}'")
    delimiter = _DELIMITERS[delimiter_name]

    null_item = well.get("NULL")
    try:
        null_value = float(null_item.value) if null_item and null_item.value else DEFAULT_NULL_VALUE
    except ValueError as e:
        raise LASInvalidDataError(f"{filepath}: invalid NULL value '{null_item.value if null_item else ''}'") from e

    curves: list[LASCurve] = []
    seen: dict[str, int] = {}
    for line_number, line in sections["C"]:
        item = _parse_header_line(line, "C", filepath, line_number)
        count = seen.get(item.mnemonic, 0)
        seen[item.mnemonic] = count + 1
        mnemonic = item.mnemonic if count == 0 else f"{item.mnemonic}:{count}"
        curves.append(LASCurve(mnemonic, item.unit, item.description))
    if len(curves) < 2:
        raise LASInvalidDataError(f"{filepath}: the ~Curve section must define an index and at least one curve")

    index_mnemonic = curves[0].mnemonic.upper()
    if index_mnemonic in _NON_DEPTH_MNEMONICS:
        raise LASInvalidDataError(
            f"{filepath}: index curve '{curves[0].mnemonic}' is not depth; "
            "only depth-indexed LAS files can be converted to a downhole collection"
        )
    if index_mnemonic not in _DEPTH_MNEMONICS:
        raise LASInvalidDataError(f"{filepath}: first curve '{curves[0].mnemonic}' must be DEPT or DEPTH")

    data = _parse_data(filepath, sections["A"], len(curves), wrapped, delimiter)
    if data.shape[0] == 0:
        raise LASInvalidDataError(f"{filepath}: the ~ASCII section contains no data")
    data[np.isclose(data, null_value, rtol=0.0, atol=1e-9)] = np.nan
    if np.isnan(data[:, 0]).any():
        raise LASInvalidDataError(f"{filepath}: the index curve contains null values")
    if (np.diff(data[:, 0]) < 0).any():
        raise LASInvalidDataError(f"{filepath}: the index curve must not decrease")

    las = LASFile(filepath, vers.value, wrapped, null_value, well, parameters, curves, data)
    _check_start_stop(las)
    return las


def _parse_data(
    filepath: str, lines: list[tuple[int, str]], n_curves: int, wrapped: bool, delimiter: str | None
) -> npt.NDArray[np.float64]:
    values: list[float] = []
    for line_number, line in lines:
        tokens = [t.strip() for t in line.split(delimiter) if t.strip()]
        if not wrapped and len(tokens) != n_curves:
            raise LASInvalidDataError(f"{filepath}:{line_number}: expected {n_curves} values but found {len(tokens)}")
        try:
            values.extend(float(t) for t in tokens)
        except ValueError as e:
            raise LASInvalidDataError(f"{filepath}:{line_number}: non-numeric value in ~ASCII section") from e
    if len(values) % n_curves != 0:
        raise LASInvalidDataError(
            f"{filepath}: the ~ASCII section has {len(values)} values, which is not a multiple of {n_curves} curves"
        )
    return np.asarray(values, dtype=np.float64).reshape(-1, n_curves)


def _check_start_stop(las: LASFile) -> None:
    for key, actual in (("STRT", las.index[0]), ("STOP", las.index[-1])):
        item = las.well.get(key)
        try:
            declared = float(item.value) if item and item.value else None
        except ValueError:
            declared = None
        if declared is not None and not np.isclose(declared, actual, rtol=0.0, atol=1e-3 * max(1.0, abs(declared))):
            logger.warning(f"{las.filepath}: {key} ({declared}) does not match the data ({actual})")
