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

"""Reader for Petrel ASCII well deviation (.dev) files.

Header comments give ``WELL NAME``, ``WELL HEAD X-COORDINATE``, ``WELL HEAD Y-COORDINATE`` and ``WELL KB``.
The data table has the columns ``MD X Y Z TVD DX DY AZIM INCL DLS``. Z is elevation (negative down), MD and TVD are
measured from KB, and angles are in degrees with INCL measured from vertical.
"""

import os
import re
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from evo.data_converters.las.importer.las_reader import LASDataFileIOError, LASInvalidDataError

_DEFAULT_COLUMNS = ["MD", "X", "Y", "Z", "TVD", "DX", "DY", "AZIM", "INCL", "DLS"]
_HEADER_PATTERN = re.compile(
    r"^#\s*(WELL NAME|WELL HEAD X-COORDINATE|WELL HEAD Y-COORDINATE|WELL KB)\s*:\s*(.*)$", re.I
)
_NULL_VALUES = (-999.0, -999.25, -99999.0)


@dataclass
class DeviationSurvey:
    """A well collar and survey. ``survey`` rows are (MD, azimuth, dip), with dip positive down."""

    filepath: str
    well_name: str
    collar: tuple[float, float, float]  # x, y, elevation
    survey: npt.NDArray[np.float64] = field(repr=False)


def read_dev_file(filepath: str | os.PathLike) -> DeviationSurvey:
    """Read a Petrel deviation file.

    :raise LASDataFileIOError: If the file cannot be read.
    :raise LASInvalidDataError: If the file contents are invalid.
    """
    filepath = os.fspath(filepath)
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as e:
        raise LASDataFileIOError(f"Unable to read deviation file '{filepath}': {e}") from e

    header: dict[str, str] = {}
    columns: list[str] | None = None
    rows: list[list[float]] = []
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            match = _HEADER_PATTERN.match(line)
            if match:
                header[match.group(1).upper()] = match.group(2).strip()
            continue
        tokens = line.split()
        try:
            numbers = [float(t) for t in tokens]
        except ValueError:
            if columns is None and not rows:
                columns = [t.upper() for t in tokens]
                continue
            raise LASInvalidDataError(f"{filepath}:{line_number}: non-numeric value in deviation data")
        if len(numbers) != len(columns or _DEFAULT_COLUMNS):
            raise LASInvalidDataError(
                f"{filepath}:{line_number}: expected {len(columns or _DEFAULT_COLUMNS)} values but found {len(numbers)}"
            )
        rows.append(numbers)

    if not rows:
        raise LASInvalidDataError(f"{filepath}: no deviation data found")
    columns = columns or _DEFAULT_COLUMNS
    table = {name: np.array([r[i] for r in rows]) for i, name in enumerate(columns)}
    valid = np.ones(len(rows), dtype=bool)
    for values in table.values():
        valid &= ~np.isnan(values) & ~np.isin(values, _NULL_VALUES)
    table = {name: values[valid] for name, values in table.items()}
    if len(table[columns[0]]) == 0:
        raise LASInvalidDataError(f"{filepath}: no valid deviation rows found")

    survey = _build_survey(filepath, table)
    collar = (
        _header_float(header, "WELL HEAD X-COORDINATE", table.get("X")),
        _header_float(header, "WELL HEAD Y-COORDINATE", table.get("Y")),
        _header_float(header, "WELL KB", table.get("Z")),
    )
    name = header.get("WELL NAME") or os.path.splitext(os.path.basename(filepath))[0]
    return DeviationSurvey(filepath, name, collar, survey)


def _header_float(header: dict[str, str], key: str, column: npt.NDArray[np.float64] | None) -> float:
    try:
        return float(header[key])
    except (KeyError, ValueError):
        if column is not None and len(column):
            return float(column[0])
    raise LASInvalidDataError(f"deviation file has no '{key}' header and no matching data column")


def _build_survey(filepath: str, table: dict[str, npt.NDArray[np.float64]]) -> npt.NDArray[np.float64]:
    if "AZIM" in table and "INCL" in table:
        azimuth, incl = table["AZIM"], table["INCL"]
    elif {"X", "Y", "Z"} <= table.keys():
        azimuth, incl = _angles_from_positions(table["X"], table["Y"], table["Z"])
    else:
        raise LASInvalidDataError(f"{filepath}: deviation data needs AZIM and INCL, or X, Y and Z, columns")

    if "MD" in table:
        md = table["MD"]
    elif {"X", "Y", "Z"} <= table.keys():
        steps = np.sqrt(sum(np.diff(table[c]) ** 2 for c in "XYZ"))
        md = np.concatenate([[0.0], np.cumsum(steps)])
    else:
        raise LASInvalidDataError(f"{filepath}: deviation data needs an MD column")
    if (np.diff(md) < 0).any():
        raise LASInvalidDataError(f"{filepath}: MD must not decrease")

    # Evo dips are positive down from horizontal; Petrel inclination is measured from vertical.
    survey = np.column_stack([md, azimuth, 90.0 - incl])
    if survey[0, 0] > 0:
        survey = np.vstack([survey[0], survey])
        survey[0, 0] = 0.0
    return survey


def _angles_from_positions(
    x: npt.NDArray[np.float64], y: npt.NDArray[np.float64], z: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    dx, dy, dz = np.diff(x), np.diff(y), -np.diff(z)
    if len(dx) == 0:
        return np.zeros(1), np.zeros(1)
    azimuth = np.degrees(np.arctan2(dx, dy)) % 360.0
    incl = np.degrees(np.arctan2(np.hypot(dx, dy), dz))
    return np.append(azimuth, azimuth[-1]), np.append(incl, incl[-1])
