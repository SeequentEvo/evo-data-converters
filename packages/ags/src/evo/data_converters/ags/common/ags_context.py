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

from io import StringIO
from pathlib import Path
import evo.logging
import pandas as pd
from python_ags4 import AGS4

logger = evo.logging.getLogger("data_converters")


class AgsFileInvalidException(Exception):
    """Raised when an AGS file is invalid.

    This can be due to IO errors, corruption, file not conforming to
    specification, or missing importable groups.
    """

    pass


class AgsContext:
    """
    In-memory context for working with AGS data. Provides parsing, validation,
    table access, and serialization utilities for AGS4 files.

    Attributes
    ----------
    REQUIRED_GROUPS : list[str]
        Groups required for import operations (e.g., ``LOCA``, ``SCPG``, ``SCPT``).
    RETAINED_GROUPS : list[str]
        Groups always retained from an AGS file (e.g., ``PROJ``, ``UNIT``, ``ABBR``, ``DICT``, ``TRAN``).
    MEASUREMENT_GROUPS : list[str]
        Groups that contain measurement data (e.g., ``SCPT``, ``SCPP``, ``GEOL``, ``SCDG``).
    IGNORED_RULES : list[str]
        AGS validation rules that are ignored during file checks.
    TYPE_CATEGORY : dict[str, str]
        Mapping of AGS ``TYPE`` codes to conversion categories used during
        dataframe coercion. Known categories are ``"int"``, ``"float"``,
        ``"datetime"``, ``timedelta``, and ``"bool"``.

    Properties
    ----------
    filename : str
        The file name if parsed from a path; otherwise derived from ``PROJ.PROJ_NAME``
        and ``PROJ.PROJ_ID``. Raises ``ValueError`` if neither is available.
    tables : dict[str, pandas.DataFrame]
        Processed tables keyed by group name. Only relevant downhole collection
        groups are retained.
    headings : dict[str, list[str]]
        Original AGS headings per group.
    coordinate_reference_system : int | None
        The CRS identifier if available (e.g., from ``LOCA_GREF``), otherwise ``None``.

    Methods
    -------
    parse_ags(filepath)
        Parse an AGS file (path or buffer) into DataFrames, apply type conversions
        based on AGS TYPE rows, and validate the result for import suitability.
    write_ags(filepath)
        Write the current tables and headings to an AGS4 file.
    check_ags_file(filepath)
        Validate an AGS file against the AGS specification, ignoring configured rules.
    set_tables_and_headings(tables, headings)
        Store processed tables and their headings. Applies dtype conversions from
        the AGS TYPE row, strips UNIT/TYPE rows, standardizes missing values to
        ``pandas.NA``, and indexes on ``LOCA_ID`` where present. Only relevant groups are
        retained.
    validate_ags()
        Validate the in-memory AGS data for import requirements.
    get_table(group)
        Get a table by group name.
    get_tables(groups)
        Get all present tables whose names appear in the provided list.
    get_headings(group)
        Get the headings for a group.
    set_table(group, df)
        Add or overwrite a table for a group.
    set_heading(group, headings)
        Add or overwrite the headings for a group.
    """

    _tables: dict[str, pd.DataFrame]
    _headings: dict[str, list[str]]
    _filename: str | None

    REQUIRED_GROUPS: list[str] = ["LOCA", "SCPG", "SCPT"]
    RETAINED_GROUPS: list[str] = ["PROJ", "UNIT", "ABBR", "DICT", "TRAN"]
    MEASUREMENT_GROUPS: list[str] = ["SCPT", "SCPP", "GEOL", "SCDG"]

    IGNORED_RULES: list[str] = [
        # 8: Data values shall match their specified data types
        # We handle type conversions ourselves and allow lenient parsing
        "AGS Format Rule 8",
        # 10b: Required fields must not be empty
        # Some TYPE entries may have empty values for legacy compatibility
        "AGS Format Rule 10b",
        # 15: Each data file shall contain the UNIT GROUP to list all units used within the data file.
        # Units are not always defined, such as '%'
        "AGS Format Rule 15",
        # 16: Each data file shall contain the ABBR GROUP when abbreviations have been included in the data file.
        # Abbreviations are not always defined, and sometime erroneously detected.
        "AGS Format Rule 16",
    ]

    # TODO: Implement proper handling for DMS (degrees/minutes/seconds)
    TYPE_CATEGORY: dict[str, str] = {
        # integers
        "0DP": "int",
        # floats
        "1DP": "float",
        "2DP": "float",
        "3DP": "float",
        "4DP": "float",
        "5DP": "float",
        "MC": "float",  # Moisture content
        # scientific notation - treat as float
        "0SCI": "float",
        "1SCI": "float",
        "2SCI": "float",
        "3SCI": "float",
        "4SCI": "float",
        # significant figures - treat as float
        "1SF": "float",
        "2SF": "float",
        "3SF": "float",
        "4SF": "float",
        # datetime
        "DT": "datetime",
        # timedelta (elapsed time)
        "T": "timedelta",
        # boolean
        "YN": "bool",
        # Note: ID, PA, PT, PU, RL, U, X, XN types fall back to string (default)
    }

    def __init__(self) -> None:
        self._tables = dict()
        self._headings = dict()
        self._filename = None

    @property
    def filename(self) -> str:
        """Gets the filename of the AGS file, if available.

        Fallback (e.g. StringIO): combine PROJ_NAME and PROJ_ID from PROJ table.

        :returns: filename or combined project identifier
        :raises ValueError: if neither filename or project identifiers are available
        """
        if self._filename is not None:
            return self._filename
        elif "PROJ" in self._tables:
            row = self._tables["PROJ"].iloc[0]
            name = row.get("PROJ_NAME")
            proj_id = row.get("PROJ_ID")
            parts = [str(p).strip() for p in (name, proj_id) if isinstance(p, str) and p.strip()]
            if parts:
                return " - ".join(parts)
        raise ValueError("Filename not available and PROJ_NAME/PROJ_ID not found in PROJ table")

    def parse_ags(self, filepath: Path | str | StringIO) -> None:
        """Parses an AGS file to dataframes for each table.

        Table and Headings are available through the `tables` and `headings` properties,
        or getters for specific groups.

        :param filepath: path or buffer to the AGS file
        :raises FileNotFoundError: file not found at path
        :raises AgsFileInvalidException: in-memory AGS file is invalid, error while parsing, or missing required groups
        """
        self.check_ags_file(filepath)

        if isinstance(filepath, (Path, str)):
            self._filename = Path(filepath).stem

        try:
            tables, headings = AGS4.AGS4_to_dataframe(filepath, get_line_numbers=False)
            self.set_tables_and_headings(tables, headings)
        except AGS4.AGS4Error as e:
            raise AgsFileInvalidException("Failed to parse AGS file") from e

        # Validate whether we can import these dataframes to a Downhole Collection
        if errors := self.validate_ags():
            raise AgsFileInvalidException("AGS file is invalid: ", ", ".join(errors))

    def write_ags(self, filepath: Path | str) -> None:
        AGS4.dataframe_to_AGS4(self._tables, self._headings, filepath)

    def check_ags_file(self, filepath: Path | str | StringIO) -> None:
        """Checks an AGS file to validate conformity to AGS spec.

        Some rules are ignored, defined in this class.

        :param filepath: Path to the AGS file.
        :raises AgsFileInvalidException: if file doesn't conform
        """
        # Errors contains a dictionary keyed by rule number/name, with the value
        # containing the line number, group name, and description.
        ags_parse_errors: dict[str, dict[str, str | int]] = AGS4.check_file(filepath)
        for rule_key in list(ags_parse_errors.keys()):
            # Remove non-error entries
            if rule_key in ("Summary of data", "Metadata"):
                ags_parse_errors.pop(rule_key)
            # Remove FYI's (warnings)
            if rule_key.startswith("FYI"):
                ags_parse_errors.pop(rule_key)
            # Remove ignored rules
            if rule_key in self.IGNORED_RULES:
                ags_parse_errors.pop(rule_key)

        if ags_parse_errors:
            raise AgsFileInvalidException("AGS file is invalid: %s", ags4_errors_to_str(ags_parse_errors))

    def set_tables_and_headings(self, tables: dict[str, pd.DataFrame], headings: dict[str, list[str]]) -> None:
        """Sets the private `_tables` and `_headings` attributes.

        The dataframe already contains the first three rows:

        * row 0 - column names (HEADING)
        * row 1 - units (UNIT)
        * row 2 - type codes (TYPE)

        For each relevant table we:

        1. Read the type codes from row 2.
        2. Convert the remaining rows (row 3+) to the appropriate dtype.
        3. Drop the first two metadata rows.
        4. Store the cleaned dataframe and the original headings list.

        All other tables are discarded.
        """
        processed_tables: dict[str, pd.DataFrame] = {}

        for group, df in tables.items():
            if group not in self.REQUIRED_GROUPS + self.MEASUREMENT_GROUPS + self.RETAINED_GROUPS:
                # discard non-relevant groups
                continue

            # Ensure the dataframe has at least two rows for meta information and one data row
            if len(df) < 3:
                logger.warning(f"Table {group!r} has fewer than 3 rows; skipping type conversion.")
                processed_tables[group] = df
                continue

            # Row 2 (index 1) holds the type codes for each column
            type_codes: list[str] = df.iloc[1].astype(str).tolist()

            # Map each type code to the actual dtype using TYPE_CATEGORY
            for col, typ in zip(df.columns, type_codes):
                category = self.TYPE_CATEGORY.get(typ)
                if category == "int":
                    # Use pandas nullable Int64 to preserve NaNs
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif category == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif category == "datetime":
                    # Check if a datetime format is specified in the UNIT row (index 0)
                    unit_format = str(df.iloc[0, df.columns.get_loc(col)])
                    # Map common AGS datetime formats to pandas-compatible formats
                    format_map = {
                        "yyyy-mm-ddThh:mm": "%Y-%m-%dT%H:%M",
                        "yyyy-mm-dd": "%Y-%m-%d",
                        "dd/mm/yyyy": "%d/%m/%Y",
                        "dd-mm-yyyy": "%d-%m-%Y",
                        "day": "%d",
                        "month": "%m",
                        "yr": "%Y",
                        "hhmm": "%H%M",
                        "hhmmss": "%H%M%S",
                    }
                    if fmt := format_map.get(unit_format, None):
                        df[col] = pd.to_datetime(df[col], format=fmt, errors="coerce")
                    else:
                        # Fallback: let pandas infer the format
                        df[col] = pd.to_datetime(df[col], infer_datetime_format=True, errors="coerce")
                elif category == "timedelta":
                    # Check if a time unit is specified in the UNIT row (index 0)
                    unit = str(df.iloc[0, df.columns.get_loc(col)]).lower().strip()
                    # Map AGS time units to pandas timedelta units
                    unit_map = {"s": "s", "min": "min", "hr": "h"}
                    pd_unit = unit_map.get(unit, "s")  # default to seconds
                    # Convert numeric values to timedelta
                    df[col] = pd.to_timedelta(pd.to_numeric(df[col], errors="coerce"), unit=pd_unit)
                elif category == "bool":
                    # Convert Y/N to boolean (nullable)
                    df[col] = df[col].map({"Y": True, "N": False}).astype("boolean")
                else:
                    # Default: keep as string, preserve missing values
                    df[col] = df[col].astype(str)

            # Drop the first two rows (UNIT/TYPE) after conversion
            df: pd.DataFrame = df.iloc[2:].reset_index(drop=True)

            # Convert all NaN-like values (NaT, None, NaN) to pd.NA
            df = df.mask(df.isna(), pd.NA)

            processed_tables[group] = df

        # Store the processed tables and keep the original headings dict
        self._tables = processed_tables
        self._headings = {group: headings[group] for group in processed_tables.keys()}

    def validate_ags(self) -> list[str]:
        """Validate the in-memory AGS dataframes, returning a list of error messages.

        An empty list will be returned if no errors were found.

        :returns: list of error messages, or an empty list.
        """
        errors: list[str] = []

        # Ensure all required groups are present
        for group in self.REQUIRED_GROUPS:
            if group not in self.headings.keys():
                errors.append(f"Missing required group: {group}.")

        # Ensure one or more importable groups are present
        if not any(group in self.headings.keys() for group in self.MEASUREMENT_GROUPS):
            measurement_groups_str = ", ".join(self.MEASUREMENT_GROUPS)
            errors.append(f"Missing importable groups: one or more of {measurement_groups_str} required.")

        return errors

    @property
    def tables(self) -> dict[str, pd.DataFrame]:
        """A dictionary containing all downhole collection tables present in the AGS file, keyed by group.

        :returns: dictionary of [GROUP, table] from AGS file
        :rtype: dict[str, pd.DataFrame]
        """
        return self._tables

    @property
    def headings(self) -> dict[str, list[str]]:
        """A dictionary containing all table headings present in each group, keyed by group.

        :returns: dictionary of headers for each group
        :rtype: dict[str, list[str]]
        """
        return self._headings

    @property
    def coordinate_reference_system(self) -> int | None:
        """Gets the coordinate reference system used by the in-memory AGS file.

        .. todo::
           CRS can be provided by LOCA_LLZ, or for national grids, LOCA_GREF.
           We may need to ask for this from the user, and make sure those columns
           exist/non-null. Some files only provide national grid coordinates.
        """
        try:
            return self.get_table("LOCA").at[0, "LOCA_GREF"]
        except (KeyError, ValueError):
            return None

    def get_table(self, group: str) -> pd.DataFrame:
        """Gets a table by group name.

        .. todo::
           Add documentation for filtering by LOCA_ID

        :param group: Group name to retrieve the DataFrame for
        :return: DataFrame containing the table data, or an empty DataFrame if not present
        """
        return self.tables.get(group, pd.DataFrame())

    def get_tables(self, groups: list[str]) -> list[pd.DataFrame]:
        """Get all tables whose name is in `groups`. No error is raised for missing groups.

        :param groups: List of group names to retrieve DataFrames for
        :return: List of DataFrames, one for each matching group
        """
        return [self.get_table(group) for group in groups if group in self.tables.keys()]

    def get_headings(self, group: str) -> list[str]:
        """Gets the list of headings for a group, by group name.

        :param group: Group name to retrieve the list of headings for
        :return: List of heading strings, or an empty list if not present
        """
        return self.headings.get(group, list())

    def set_table(self, group: str, df: pd.DataFrame) -> None:
        """Add or overwrite a table for a specific group.

        :param group: Group name to store the DataFrame under
        :param df: The DataFrame containing the table data
        """
        self._tables[group] = df

    def set_heading(self, group: str, headings: list[str]) -> None:
        """Add or overwrite the headings list for a specific group.

        :param group: Group name to store the headings list under
        :param headings: List of heading strings
        """
        self._headings[group] = headings


def ags4_errors_to_str(errors: dict[str, dict[str, str | int]]) -> str:
    """Convert an AGS4.check_file() errors dictionary to a multiline string.

    :param errors: dictionary of errors from AGS4.check_file()
    :return: multiline string representation of errors
    """
    out = str()
    for group, error_rows in errors.items():
        out += f"\n{group}:\n"
        for row in error_rows:
            out += f"  L{row['line']}, Group {row['group'] or 'NULL'}: {row['desc']}\n"
    return out
