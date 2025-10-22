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

    def __init__(self) -> None:
        self._tables = dict()
        self._headings = dict()

    def parse_ags(self, filepath: Path | str | StringIO) -> None:
        """
        Parses an AGS file to dataframes for each table.
        Table and Headings are available through the `tables` and `headings` properties,
        or getters for specific groups.

        :param filepath: path or buffer to the AGS file
        :raises FileNotFoundError: file not found at path
        :raises AgsFileInvalidException: in-memory AGS file is invalid, error while parsing, or missing required groups
        """
        self.check_ags_file(filepath)

        try:
            self._tables, self._headings = AGS4.AGS4_to_dataframe(filepath, get_line_numbers=False)
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

    def get_table(self, group: str) -> pd.DataFrame:
        """Gets a table by group name.

        :param group: Group name to retrieve the DataFrame for
        :return: DataFrame containing the table data, or an empty DataFrame if not present
        """
        return self.tables.get(group, pd.DataFrame())

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
