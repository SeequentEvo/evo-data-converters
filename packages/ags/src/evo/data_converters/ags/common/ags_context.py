from io import StringIO
from pathlib import Path

import pandas as pd
from python_ags4 import AGS4


class AgsContext:
    _tables: dict[str, pd.DataFrame]
    _headings: dict[str, list[str]]

    def __init__(self) -> None:
        self._tables = dict[str, pd.DataFrame]()
        self._headings = dict[str, list[str]]()

    def parse_ags(self, filepath: Path | str | StringIO) -> None:
        """
        Parses an AGS file to dataframes for each table.
        Table and Headings are available through the `tables` and `headings` properties.

        :param filepath: path or buffer to the AGS file
        :raises AGS4Error: Any error in parsing the AGS file
        """
        self._tables, self._headings = AGS4.AGS4_to_dataframe(filepath, get_line_numbers=False)

    def write_ags(self, filepath: Path | str) -> None:
        return AGS4.dataframe_to_AGS4(self._tables, self._headings, filepath)

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
