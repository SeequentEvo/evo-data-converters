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
    """
    Raised when an AGS file is invalid.
    This can be due to IO errors, corruption, file not conforming to
    specification, or missing importable groups.
    """

    pass


class AgsContext:
    """
    Contains an AGS file while in memory.
    This can be used for both reading and writing.
    """

    _tables: dict[str, pd.DataFrame]
    _headings: dict[str, list[str]]

    # Groups that can be imported from an AGS file to a downhole collection.
    # Any parents (e.g. LOCA, SCPG) missing will be caught by AGS4 parser.
    DOWNHOLE_COLLECTION_GROUPS: list[str] = ["SCPG", "SCPT", "SCPP"]

    # AGS rules to be ignored
    IGNORED_RULES: list[str] = [
        # 15: Each data file shall contain the UNIT GROUP to list all units used within the data file.
        # Units are not always defined, such as '%'
        "AGS Format Rule 15",
        # 16: Each data file shall contain the ABBR GROUP when abbreviations have been included in the data file.
        # Abbreviations are not always defined, and sometime erroneously detected.
        "AGS Format Rule 16",
    ]

    # "TYPE" column names, which should be parsed to their appropriate type. All others assumed string.
    # TODO: SCI, SF, DMS
    INT_TYPES: list[str] = ["0DP"]
    FLOAT_TYPES: list[str] = ["1DP", "2DP", "3DP", "4DP", "5DP"]
    DATETIME_TYPES: list[str] = ["DT"]
    BOOL_TYPES: list[str] = ["YN"]

    def __init__(self) -> None:
        self._tables = dict()
        self._headings = dict()

    def parse_ags(self, filepath: Path | str | StringIO) -> None:
        """
        Parses an AGS file to dataframes for each table.
        Table and Headings are available through the `tables` and `headings` properties,
        or getters for specific groups.

        TODO:
        - build indexes on LOCA_ID for tables that use it
        - include/retain units (currently discarded)
        - use formats specified by units to parse datetime with correct format
        - discard tables we don't need early so we're not parsing them

        :param filepath: path or buffer to the AGS file
        :raises FileNotFoundError: file not found at path
        :raises AgsFileInvalidException: in-memory AGS file is invalid, error while parsing, or missing required groups
        """
        self.check_ags_file(filepath)

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
        """
        Checks an AGS file to validate conformity to AGS spec.
        Some rules are ignored, defined in this class.

        :param filepath: Path to the AGS file.
        :raises: AgsFileInvalidException, if file doesn't conform
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
        """
        Sets the private `_tables` and `_headings` attributes.
        The dataframe already contains the first three rows:
        * row 0 - column names (HEADING)
        * row 1 - units (UNIT)
        * row 2 - type codes (TYPE)

        For each table we:

        1. Read the type codes from row 2.
        2. Convert the remaining rows (row 3+) to the appropriate dtype.
        3. Drop the first two metadata rows.
        4. Store the cleaned dataframe and the original headings list.
        """
        processed_tables: dict[str, pd.DataFrame] = {}

        for group, df in tables.items():
            # Ensure the dataframe has at least two rows for meta information and one data row
            if len(df) < 3:
                logger.warning(f"Table {group!r} has fewer than 3 rows; skipping type conversion.")
                processed_tables[group] = df
                continue

            # Row 2 (index 2) holds the type codes for each column
            type_codes: list[str] = df.iloc[1].astype(str).tolist()

            # Map each type code to the actual dtype
            for col, typ in zip(df.columns, type_codes):
                print(f"col: {col}, typ: {typ}")
                if typ in self.INT_TYPES:
                    # Use pandas nullable Int64 to preserve NaNs
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif typ in self.FLOAT_TYPES:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif typ in self.DATETIME_TYPES:
                    df[col] = pd.to_datetime(df[col], errors="coerce", format="%Y-%m-%d")
                elif typ in self.BOOL_TYPES:
                    # Convert Y/N to boolean (nullable)
                    df[col] = df[col].map({"Y": True, "N": False}).astype("boolean")
                else:
                    # Default: keep as string, preserve missing values
                    df[col] = df[col].astype(str)

            # Drop the first two rows (UNIT/TYPE) after conversion
            df: pd.DataFrame = df.iloc[2:].reset_index(drop=True)
            processed_tables[group] = df

        # Store the processed tables and keep the original headings dict
        self._tables = processed_tables
        self._headings = headings

    def validate_ags(self) -> list[str]:
        """
        Validate the in-memory AGS dataframes, returning a list of error messages.
        An empty list will be returned if no errors were found.

        :returns: list of error messages, or an empty list.
        """
        errors: list[str] = list()

        # Ensure one or more importable groups are present
        if not any(group in self.headings.keys() for group in self.DOWNHOLE_COLLECTION_GROUPS):
            required_groups_str = ", ".join(self.DOWNHOLE_COLLECTION_GROUPS)
            errors.append(f"Missing importable groups: one or more of {required_groups_str} required.")

        return errors

    @property
    def tables(self) -> dict[str, pd.DataFrame]:
        """
        A dictionary containing all tables present in the AGS file, keyed by group.

        :returns: dict[str, pd.DataFrame]: dictionary of [GROUP, table] from AGS file
        """
        return self._tables

    @property
    def headings(self) -> dict[str, list[str]]:
        """
        A dictionary containing all table headings present in each group, keyed by group.

        :returns: dict[str, list[str]]: dictionary of headers for each group
        """
        return self._headings

    @property
    def coordinate_reference_system(self) -> int | str:
        """
        Gets the coordinate reference system used by the in-memory AGS file.

        TODO: CRS can be provided by LOCA_LLZ, or for national grids, LOCA_GREF.
        We may need to ask for this from the user, and make sure those columns
        exist/non-null. Some files only provide national grid coordinates.
        """
        try:
            return self.get_table("LOCA").at[0, "LOCA_GREF"]
        except (KeyError, ValueError):
            return "unspecified"

    def get_table(self, group: str) -> pd.DataFrame:
        """Gets a table by group name.

        TODO: Add documentation for filtering by LOCA_ID

        :param group: Group name to retrieve the DataFrame for
        :return: DataFrame containing the table data, or an empty DataFrame if not present
        """
        return self.tables.get(group, pd.DataFrame())

    def get_tables(self, groups: list[str]) -> list[pd.DataFrame]:
        """
        Get all tables whose name is in `groups`. No error is raised for missing groups.

        :param groups: List of group names to retrieve DataFrames for
        :return: List of DataFrames, one for each matching group
        """
        return [self.get_table(group) for group in groups if group in self.tables.keys()]

    def get_headings(self, group: str) -> list[str]:
        """
        Gets the list of headings for a group, by group name.

        :param group: Group name to retrieve the list of headings for
        :return: List of heading strings, or an empty list if not present
        """
        return self.headings.get(group, list())

    def set_table(self, group: str, df: pd.DataFrame) -> None:
        """
        Add or overwrite a table for a specific group.

        :param group: Group name to store the DataFrame under
        :param df: The DataFrame containing the table data
        """
        self._tables[group] = df

    def set_heading(self, group: str, headings: list[str]) -> None:
        """
        Add or overwrite the headings list for a specific group.

        :param group: Group name to store the headings list under
        :param headings: List of heading strings
        """
        self._headings[group] = headings


def ags4_errors_to_str(errors: dict[str, dict[str, str | int]]) -> str:
    """
    Convert an AGS4.check_file() errors dictionary to a multiline string.
    """
    out = str()
    for group, error_rows in errors.items():
        out += f"\n{group}:\n"
        for row in error_rows:
            out += f"  L{row['line']}, Group {row['group'] or 'NULL'}: {row['desc']}\n"
    return out
