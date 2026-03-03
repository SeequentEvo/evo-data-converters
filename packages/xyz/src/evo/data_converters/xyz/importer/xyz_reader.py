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

import numpy as np
import numpy.typing as npt
from .xyz_types import XYZ_Type


def _is_header_line(line: str) -> bool:
    """Return True if the line is a header and should be skipped.

    A header line is any line whose first character is not a digit,
    a decimal point, a plus sign, or a minus sign (i.e. not numeric data).
    """
    return not line[0].isdigit() and line[0] not in (".", "+", "-")


def read_xyz(file_path: str) -> npt.NDArray[np.float64]:
    rows: list[list[float]] = []

    xyz_type = __get_type(file_path)
    if xyz_type == XYZ_Type.UNKNOWN:
        raise ValueError(f"Unsupported XYZ file type")

    with open(file_path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or _is_header_line(stripped):
                continue

            values = __get_list_of_string_values(stripped, xyz_type)
            if len(values) != 3:
                raise ValueError(f"Invalid XYZ format at line {line_number}: expected 3 values, got {len(values)}")

            try:
                row = [float(v) for v in values]
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value at line {line_number}: '{stripped}'") from exc

            rows.append(row)

    # Build a float64 array of shape (N, 3)
    points = np.array(rows, dtype=np.float64)
    return points


def __get_type(file_path: str) -> XYZ_Type:
    """Determine the XYZ file type by inspecting the first non-empty line.

    - 2 numeric values        → BINARY        (e.g. "12.2,12.3")
    - 3 numeric values        → POINTS        (e.g. "10.2,10.2,10.3")
    - letter + 3 numeric vals → GEOCHEMISTRY  (e.g. "C,10.1,10.2,10.2")
    """
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped or _is_header_line(stripped):
                continue

            values = [v.strip() for v in stripped.split(",")]
            num_values = len(values)

            if num_values == 2:
                return XYZ_Type.BINARY

            if num_values == 3:
                return XYZ_Type.POINTS

            if num_values == 4 and not values[0].replace(".", "", 1).lstrip("-").isdigit():
                return XYZ_Type.GEOCHEMISTRY

            return XYZ_Type.UNKNOWN

    return XYZ_Type.UNKNOWN


def __get_list_of_string_values(line: str, type: XYZ_Type) -> list[str]:
    """Extract numeric string values from a line based on the XYZ type.

    Returns a list of 3 string values:
    - POINTS:       splits on comma → ["10.1", "10.2", "10.3"]
    - BINARY:       splits on comma, appends "0.0" → ["10.1", "10.2", "0.0"]
    - GEOCHEMISTRY: splits on whitespace, drops the leading label → ["10.1", "10.2", "10.3"]
    """
    if type == XYZ_Type.POINTS:
        return [v.strip() for v in line.split(",")]

    if type == XYZ_Type.BINARY:
        values = [v.strip() for v in line.split(",")]
        values.append("0.0")
        return values

    if type == XYZ_Type.GEOCHEMISTRY:
        # First token is the label (e.g. "C"), remaining 3 are coordinates
        return line.split()[1:]

    raise ValueError(f"Unsupported XYZ type: {type}")
