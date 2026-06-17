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
from .xyz_types import XYZ_Type
from .xyz_data import XYZData

DUMMY = "-1.0e32"


def _is_header_line(line: str) -> bool:
    """Return True if the line is a header and should be skipped.

    A header line is any line whose first character is not a digit,
    a decimal point, a plus sign, or a minus sign (i.e. not numeric data).
    """
    return not line[0].isdigit() and line[0] not in (".", "+", "-")


def read_xyz(file_path: str, x_index: int, y_index: int, z_index: int, data_index: int) -> XYZData:
    rows: list[list[float]] = []
    data_values: list[str] = []

    xyz_type = __get_type(file_path, z_index=z_index, data_index=data_index)
    if xyz_type == XYZ_Type.UNKNOWN:
        raise ValueError("Unsupported XYZ file type")

    with open(file_path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or _is_header_line(stripped):
                continue

            values = __get_list_of_string_values(stripped, xyz_type, x_index=x_index, y_index=y_index, z_index=z_index)
            if len(values) < 3:
                raise ValueError(f"Invalid XYZ format at line {line_number}: expected 3 or 4 values, got {len(values)}")

            values = __replace_stars_for_dummies(values)
            if xyz_type in (XYZ_Type.GEOSOFT_BYNARY_XYZ_DATA, XYZ_Type.GEOSOFT_XYZ_TRIPLET_DATA):
                data_value = __get_string_data_value(stripped, xyz_type, data_index)
                data_values.append(data_value)

            try:
                row = [float(v) for v in values]
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value at line {line_number}: '{stripped}'") from exc

            rows.append(row)

    # Build a float64 array of shape (N, 3)
    points = np.array(rows, dtype=np.float64)

    if len(data_values) > 0:
        try:
            data = [float(v) for v in data_values]
        except ValueError as exc:
            raise ValueError("Invalid data value") from exc
    else:
        data = []

    return XYZData(points=points, data=data)


def __replace_stars_for_dummies(values: list[str]) -> list[str]:
    """Replace any '*' in the list of string values with a dummy value to allow numeric parsing."""
    return [x if x != "*" else DUMMY for x in values]


def __get_type(file_path: str, z_index: int, data_index: int) -> XYZ_Type:
    """Determine the XYZ file type by inspecting the first non-header, non-empty line.

    Detection is based on delimiter and token count:

    Comma-delimited:
    - 2 tokens                              → BINARY               (e.g. "12.2,12.3")
    - 3 tokens                              → POINTS               (e.g. "10.2,10.2,10.3")
    - 4 tokens, first token non-numeric     → GEOCHEMISTRY_COMMA   (e.g. "C,10.1,10.2,10.3")

    Space-delimited:
    - 4 tokens, first token non-numeric     → GEOCHEMISTRY_SPACE   (e.g. "C 10.1 10.2 10.3")
    - 2 tokens                              → GEOSOFT_BYNARY_XYZ   (e.g. "12.2 12.3")
    - ≥3 tokens, data_index set, z_index=-1 → GEOSOFT_BYNARY_XYZ_DATA (e.g. "12.2 12.3 val")
    - exactly 3 tokens                      → GEOSOFT_XYZ_TRIPLET  (e.g. "10.2 10.2 10.3")
    - ≥3 tokens (fallthrough)               → GEOSOFT_XYZ_TRIPLET_DATA (e.g. "10.2 10.2 10.3 val")

    Returns UNKNOWN if no pattern matches.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped or _is_header_line(stripped):
                continue

            values_comma = [v.strip() for v in stripped.split(",")]
            num_values_comma = len(values_comma)
            values_space = [v.strip() for v in stripped.split()]
            num_values_space = len(values_space)

            if num_values_comma == 2:
                return XYZ_Type.BINARY

            if num_values_comma == 3:
                return XYZ_Type.POINTS

            if num_values_comma == 4 and not values_comma[0].replace(".", "", 1).lstrip("-").isdigit():
                return XYZ_Type.GEOCHEMISTRY_COMMA

            if num_values_space == 4 and not values_space[0].replace(".", "", 1).lstrip("-").isdigit():
                return XYZ_Type.GEOCHEMISTRY_SPACE

            # if only 2 values, consider x and y, if three values and a data_index, consider x_index, y_index, data_index and set z to 0
            if num_values_space == 2:
                return XYZ_Type.GEOSOFT_BYNARY_XYZ

            if num_values_space >= 3 and data_index != -1 and z_index == -1:
                return XYZ_Type.GEOSOFT_BYNARY_XYZ_DATA

            if num_values_space == 3 or (num_values_space >= 3 and data_index == -1):
                return XYZ_Type.GEOSOFT_XYZ_TRIPLET

            if num_values_space >= 3:
                return XYZ_Type.GEOSOFT_XYZ_TRIPLET_DATA

            return XYZ_Type.UNKNOWN

    return XYZ_Type.UNKNOWN


def __get_list_of_string_values(line: str, type: XYZ_Type, x_index: int, y_index: int, z_index: int) -> list[str]:
    """Extract exactly 3 coordinate string values from a line based on the XYZ type.

    Always returns a list of 3 strings representing [x, y, z].
    When z is absent in the source data, "0.0" is substituted.

    - POINTS:                   comma-split → [x, y, z]
    - BINARY:                   comma-split, z padded as "0.0" → [x, y, "0.0"]
    - GEOCHEMISTRY_COMMA:       comma-split, leading label token dropped → [x, y, z]
    - GEOCHEMISTRY_SPACE:       space-split, leading label token dropped → [x, y, z]
    - GEOSOFT_BYNARY_XYZ:       space-split, uses x_index/y_index (or positions 0/1), z padded as "0.0"
    - GEOSOFT_BYNARY_XYZ_DATA:  space-split, uses x_index/y_index (or positions 0/1), z padded as "0.0"
    - GEOSOFT_XYZ_TRIPLET:      space-split, uses x_index/y_index/z_index (or positions 0/1/2)
    - GEOSOFT_XYZ_TRIPLET_DATA: space-split, uses x_index/y_index/z_index (or positions 0/1/2)
    """
    if type == XYZ_Type.POINTS:
        return [v.strip() for v in line.split(",")]

    if type == XYZ_Type.BINARY:
        values = [v.strip() for v in line.split(",")]
        values.append("0.0")
        return values

    if type == XYZ_Type.GEOCHEMISTRY_COMMA:
        # First token is the label (e.g. "C"), remaining 3 are coordinates
        return line.split(",")[1:]

    if type == XYZ_Type.GEOCHEMISTRY_SPACE:
        # First token is the label (e.g. "C"), remaining 3 are coordinates
        return line.split()[1:]

    if type == XYZ_Type.GEOSOFT_BYNARY_XYZ:
        values = line.split()

        if x_index >= len(values) or y_index >= len(values):
            raise ValueError(f"Invalid x_index or y_index for line: '{line}'")

        values.append("0.0")

        if x_index == -1 and y_index == -1:
            return values[:3]
        else:
            return [values[x_index], values[y_index], "0.0"]

    if type == XYZ_Type.GEOSOFT_BYNARY_XYZ_DATA:
        values = line.split()

        if x_index >= len(values) or y_index >= len(values):
            raise ValueError(f"Invalid x_index or y_index for line: '{line}'")

        if x_index == -1 and y_index == -1:
            return [values[0], values[1], "0.0"]
        else:
            return [values[x_index], values[y_index], "0.0"]

    if type == XYZ_Type.GEOSOFT_XYZ_TRIPLET:
        values = line.split()

        if x_index >= len(values) or y_index >= len(values) or z_index >= len(values):
            raise ValueError(f"Invalid x_index, y_index, or z_index for line: '{line}'")

        if x_index == -1 and y_index == -1 and z_index == -1:
            return values[:3]

        return [values[x_index], values[y_index], values[z_index]]

    if type == XYZ_Type.GEOSOFT_XYZ_TRIPLET_DATA:
        values = line.split()

        if x_index >= len(values) or y_index >= len(values) or z_index >= len(values):
            raise ValueError(f"Invalid x_index, y_index, or z_index for line: '{line}'")

        if x_index == -1 and y_index == -1:
            return [values[0], values[1], values[z_index]]

        return [values[x_index], values[y_index], values[z_index]]

    raise ValueError(f"Unsupported XYZ type: {type}")


def __get_string_data_value(line: str, type: XYZ_Type, data_index: int) -> str:
    if type not in (XYZ_Type.GEOSOFT_BYNARY_XYZ_DATA, XYZ_Type.GEOSOFT_XYZ_TRIPLET_DATA):
        raise ValueError(
            f"Data index is only supported for GEOSOFT_BYNARY_XYZ_DATA and GEOSOFT_XYZ_TRIPLET_DATA types, got {type}"
        )

    values = line.split()

    if data_index >= len(values):
        raise ValueError(f"Invalid data_index for line: '{line}'")

    if data_index == -1 and type == XYZ_Type.GEOSOFT_BYNARY_XYZ_DATA:
        value = values[2]  # data is in position 2 when x_index/y_index are -1 and z is padded as "0.0"
    elif data_index == -1 and type == XYZ_Type.GEOSOFT_XYZ_TRIPLET_DATA:
        value = values[3]  # data is in position 3 when x_index/y_index/z_index are -1 and z is not padded
    else:
        value = values[data_index]

    return value if value != "*" else DUMMY
