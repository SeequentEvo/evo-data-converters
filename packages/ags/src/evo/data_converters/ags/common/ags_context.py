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
from .pandas_utils import coerce_to_object_int
from pyproj import CRS
from pyproj.exceptions import CRSError
from python_ags4 import AGS4
from functools import cached_property

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

    :cvar list[str] REQUIRED_GROUPS: Groups required for import operations (e.g., ``LOCA``, ``SCPG``, ``SCPT``).
    :cvar list[str] MEASUREMENT_GROUPS: Groups that contain measurement data
        (e.g., ``SCPT``, ``SCPP``, ``GEOL``, ``SCDG``).
    :cvar list[str] RETAINED_GROUPS: Other groups retained from an AGS file (e.g., ``PROJ``, ``UNIT``).
    :cvar list[str] IGNORED_RULES: AGS validation rules that are ignored during file checks.
    :cvar dict[str, str] TYPE_CATEGORY: Mapping of AGS ``TYPE`` codes to conversion categories used during
        dataframe coercion. Known categories are ``"int"``, ``"float"``, ``"datetime"``, ``timedelta``, and ``"bool"``.

    :ivar dict[str, pandas.DataFrame] tables: Processed tables keyed by group
        name. Only relevant downhole collection groups are retained.
    :ivar dict[str, list[str]] headings: Original AGS headings per group.
    :ivar str filename: The file name if parsed from a path; otherwise derived
        from ``PROJ.PROJ_NAME`` and ``PROJ.PROJ_ID``. Raises ``ValueError`` if
        neither is available.
    :ivar int | None coordinate_reference_system: The CRS identifier if
        available (e.g., from ``LOCA_GREF``), otherwise ``None``.

    :meth:`parse_ags(filepath)`: Parse an AGS file (path or buffer) into
        DataFrames, apply type conversions based on AGS TYPE rows, and validate
        the result for import suitability.
    :meth:`write_ags(filepath)`: Write the current tables and headings to an AGS4 file.
    :meth:`check_ags_file(filepath)`: Validate an AGS file against the AGS specification, ignoring configured rules.
    :meth:`set_tables_and_headings(tables, headings)`: Store processed tables
        and their headings. Applies dtype conversions from the AGS TYPE row,
        strips UNIT/TYPE rows, standardizes missing values to ``pandas.NA``,
        and indexes on ``LOCA_ID`` where present. Only relevant groups are
        retained.
    :meth:`validate_ags()`: Validate the in-memory AGS data for import requirements.
    :meth:`get_table(group)`: Get a table by group name.
    :meth:`get_tables(groups)`: Get all present tables whose names appear in the provided list.
    :meth:`get_headings(group)`: Get the headings for a group.
    :meth:`set_table(group, df)`: Add or overwrite a table for a group.
    :meth:`set_heading(group, headings)`: Add or overwrite the headings for a group.
    """

    _tables: dict[str, pd.DataFrame]
    _headings: dict[str, list[str]]
    _filename: str | None

    REQUIRED_GROUPS: list[str] = ["LOCA", "SCPG", "SCPT"]
    RETAINED_GROUPS: list[str] = ["PROJ", "UNIT", "HORN"]
    MEASUREMENT_GROUPS: list[str] = ["SCPT", "SCPP", "GEOL", "SCDG"]
    RETAINED_GROUPS: list[str] = ["PROJ", "UNIT"]

    IGNORED_RULES: list[str] = [
        # 2a: Each line should be terminated by CR and LF characters
        # Files from various sources use Unix line endings (LF only)
        # This is a formatting issue that doesn't affect data integrity
        "AGS Format Rule 2a",
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

            # Row 1 (index 0) holds the units each column is in
            unit_row: pd.Series = df.iloc[0]
            # Row 2 (index 1) holds the type codes for each column
            type_codes: list[str] = df.iloc[1].astype(str).tolist()

            # Drop the first two rows (UNIT/TYPE) before conversion
            df: pd.DataFrame = df.iloc[2:].reset_index(drop=True)

            # Ensure the dataframe has at least one data row
            if len(df) < 1:
                logger.warning(f"Table {group!r} has no data rows; skipping type conversion.")
                processed_tables[group] = df
                continue

            # Map each type code to the actual dtype using TYPE_CATEGORY
            for col, typ in zip(df.columns, type_codes):
                category = self.TYPE_CATEGORY.get(typ)
                if category == "int":
                    # Convert to an object dtype with integers and pd.NA's, can be inferred as integer type.
                    df[col] = coerce_to_object_int(df[col])
                elif category == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif category == "datetime":
                    # Check if a datetime format is specified in the UNIT row (index 0)
                    unit_format = str(unit_row[col])
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
                        df[col] = pd.to_datetime(df[col], errors="coerce")
                elif category == "timedelta":
                    # Check if a time unit is specified in the UNIT row (index 0)
                    unit = str(unit_row[col]).lower().strip()
                    # Map AGS time units to pandas timedelta units
                    unit_map = {"s": "s", "min": "min", "hr": "h"}
                    pd_unit = unit_map.get(unit, "s")  # default to seconds
                    # Convert numeric values to timedelta
                    df[col] = pd.to_timedelta(pd.to_numeric(df[col], errors="coerce"), unit=pd_unit)
                elif category == "bool":
                    # Convert Y/N to boolean
                    df[col] = df[col].map({"Y": True, "N": False})
                else:
                    # Default: keep as string, preserve missing values
                    df[col] = df[col].astype(str)

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

    @cached_property
    def proj_id(self) -> str:
        """Gets the PROJ_ID from the PROJ table.

        :returns: PROJ_ID string
        :rtype: str
        :raises ValueError: if PROJ_ID is not found
        """
        try:
            proj_id = self.get_table("PROJ").at[0, "PROJ_ID"]
            return str(proj_id)
        except (KeyError, ValueError):
            raise ValueError("PROJ_ID not found in PROJ table")

    @property
    def coordinate_reference_system(self) -> int | str | None:
        """Gets the coordinate reference system used by the in-memory AGS file.

        :returns: epsg code as integer or "unspecified" if a CRS can be determined, None otherwise.
        """
        crs_gref: int | str | None = self.crs_from_loca_gref()
        crs_llz: int | None = self.crs_from_loca_llz()

        if all([crs_gref, crs_llz]):
            logger.warning(f"Found CRS for both LOCA_GREF and LOCA_LLZ, preferring LOCA_GREF: {crs_gref}")
            return crs_gref

        if crs_gref is not None:
            return crs_gref

        if crs_llz is not None:
            return crs_llz

        return None

    def get_table(self, group: str) -> pd.DataFrame:
        """Gets a table by group name.

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

    def crs_from_loca_gref(self) -> int | str | None:
        """
        Try to determine CRS from LOCA_GREF, if it exists.

        :returns: None if we can't determine a CRS, "unspecified" if the
            CRS is locally defined, an integer if we found the projected CRS.
        """
        try:
            gref = self.get_table("LOCA").at[0, "LOCA_GREF"]
            gref = str(gref).upper().strip()
        except (KeyError, ValueError):
            return None

        # Mapping of AGS standard abbreviations to projected CRS
        ags_standard_map: dict[str, int | str] = {
            "OSGB": 27700,
            "OSI": 29902,
            "ITM": 2157,
            "LOCAL": "unspecified",
        }

        if gref in ags_standard_map:
            return ags_standard_map[gref]

        logger.warning(f"Could not determine CRS from LOCA_GREF: {gref}")

        return None

    def crs_from_loca_llz(self) -> int | None:
        """
        Try to determine CRS from LOCA_LLZ, if it exists.

        :returns: None if we can't determine a CRS, or the epsg code if we found the geographic CRS.
        """
        try:
            llz = self.get_table("LOCA").at[0, "LOCA_LLZ"]
            llz = str(llz).upper().strip()
        except (KeyError, ValueError):
            return None

        try:
            crs = CRS.from_user_input(llz)
        except CRSError:
            logger.warning(f"Could not determine CRS from LOCA_LLZ: {llz}")
            return None

        return crs.to_epsg()

    def validate_merge(self, other: "AgsContext", raise_on_error: bool = True) -> list[str]:
        """Validate whether another AgsContext can be merged into this one.

        Checks PROJ_ID and CRS compatibility, returning a list of incompatibility
        issues found.

        :param other: The AgsContext to validate for merging
        :param raise_on_error: If True, raises ValueError on first incompatibility found
        :returns: List of incompatibility warning messages (empty if compatible)
        :raises ValueError: If raise_on_error=True and contexts are incompatible
        """
        issues = []

        # Check PROJ_ID compatibility
        if self.proj_id != other.proj_id:
            msg = (
                f"Incompatible PROJ_ID: first has '{self.proj_id}', second has '{other.proj_id}'. "
                f"Rows from first context will be kept for duplicate LOCA_IDs and (LOCA_ID, SCPG_TESN) pairs."
            )
            if raise_on_error:
                raise ValueError(f"Cannot merge AgsContext instances: {msg}")
            issues.append(msg)

        # Check CRS compatibility
        self_crs = self.coordinate_reference_system
        other_crs = other.coordinate_reference_system
        if self_crs is not None and other_crs is not None and self_crs != other_crs:
            msg = (
                f"Incompatible CRS: first has '{self_crs}', second has '{other_crs}'. "
                f"This may result in incorrect spatial positioning of merged data."
            )
            if raise_on_error:
                raise ValueError(f"Cannot merge AgsContext instances: {msg}")
            issues.append(msg)

        return issues

    def merge(self, other: "AgsContext", validate_compatibility: bool = True) -> None:
        """Merge another AgsContext into this one (in-place).

        Concatenates measurement and location tables while validating metadata
        compatibility. Modifies self and leaves other unchanged.
        If no longer needed, consider freeing memory by deleting other.

        Merging strategy:
        - Metadata-like tables (e.g., PROJ, UNIT): Keep from self, warn if different
        - LOCA: Concatenate, check for duplicate LOCA_ID
        - SCPG: Concatenate, check for duplicate (LOCA_ID, SCPG_TESN) pairs
        - Measurement tables (SCPT, SCPP, GEOL, SCDG): Concatenate all rows

        :param other: The AgsContext to merge into this one
        :param validate_compatibility: If True, raises error on incompatibility; if False, logs warnings
        :raises ValueError: If contexts are incompatible and validation is enabled
        """
        # Check compatibility and handle based on validate_compatibility flag
        issues = self.validate_merge(other, raise_on_error=validate_compatibility)

        # Log any issues as warnings when validation is disabled
        for issue in issues:
            logger.warning(f"Merging AgsContext instances: {issue}")

        # Metadata tables: keep from self, warn if different
        for group in self.RETAINED_GROUPS:
            if group in other.tables and group in self.tables:
                # Check if tables are identical
                # TODO: This may not be necessary for most tables - consider removing or limiting to PROJ only
                if not self.get_table(group).equals(other.get_table(group)):
                    logger.warning(f"Table '{group}' differs between files. Keeping values from first context.")

        # LOCA table: concatenate and check for duplicates
        self._merge_loca(other)

        # SCPG table: concatenate and check for duplicate (LOCA_ID, SCPG_TESN) pairs
        self._merge_scpg(other)

        # Measurement tables: concatenate all rows
        for group in self.MEASUREMENT_GROUPS:
            self._merge_measurement_table(group, other)

    def _merge_loca(self, other: "AgsContext") -> None:
        """Merge LOCA tables from another AgsContext into this one.

        Checks for duplicate LOCA_ID values and if so, keeps rows from self.
        All unique rows are concatenated.

        :param other: The AgsContext to merge LOCA table from
        """
        self_loca = self.get_table("LOCA")
        other_loca = other.get_table("LOCA").copy()

        # Concatenate and remove duplicates, keeping first occurrence (from self)
        merged_loca = pd.concat([self_loca, other_loca], ignore_index=True)

        # Check for duplicates before dropping them
        duplicate_count = merged_loca.duplicated(subset=["LOCA_ID"], keep="first").sum()
        if duplicate_count > 0:
            duplicate_ids = merged_loca[merged_loca.duplicated(subset=["LOCA_ID"], keep="first")]["LOCA_ID"].tolist()
            logger.warning(
                f"Found {duplicate_count} duplicate LOCA_ID values "
                f"when merging contexts. Keeping rows from first context. "
                f"Duplicate IDs: {duplicate_ids}"
            )

        merged_loca = merged_loca.drop_duplicates(subset=["LOCA_ID"], keep="first", ignore_index=True)
        self.set_table("LOCA", merged_loca)

        # Merge headings (union of both)
        merged_headings = list(dict.fromkeys(self.get_headings("LOCA") + other.get_headings("LOCA")))
        self.set_heading("LOCA", merged_headings)

    def _merge_scpg(self, other: "AgsContext") -> None:
        """Merge SCPG tables from another AgsContext into this one.

        Checks for duplicate (LOCA_ID, SCPG_TESN) pairs and if so, keeps rows from self.
        All unique rows are concatenated.

        :param other: The AgsContext to merge SCPG table from
        """
        self_scpg = self.get_table("SCPG")
        other_scpg = other.get_table("SCPG").copy()

        # Concatenate and remove duplicates, keeping first occurrence (from self)
        merged_scpg = pd.concat([self_scpg, other_scpg], ignore_index=True)

        # Check for duplicates before dropping them
        duplicate_count = merged_scpg.duplicated(subset=["LOCA_ID", "SCPG_TESN"], keep="first").sum()
        if duplicate_count > 0:
            logger.warning(
                f"Found {duplicate_count} duplicate (LOCA_ID, SCPG_TESN) pairs "
                f"when merging contexts. Keeping rows from first context."
            )

        merged_scpg = merged_scpg.drop_duplicates(subset=["LOCA_ID", "SCPG_TESN"], keep="first", ignore_index=True)
        self.set_table("SCPG", merged_scpg)

        # Merge headings
        merged_headings = list(dict.fromkeys(self.get_headings("SCPG") + other.get_headings("SCPG")))
        self.set_heading("SCPG", merged_headings)

    def _merge_measurement_table(self, group: str, other: "AgsContext") -> None:
        """Merge a measurement table from another AgsContext into this one.

        Concatenates all rows from both tables, removing duplicate rows.

        :param group: The measurement group name to merge (e.g., SCPT, SCPP)
        :param other: The AgsContext to merge the measurement table from
        """
        if group in other.tables:
            if group in self.tables:
                self_table = self.get_table(group)
                other_table = other.get_table(group)

                # Concatenate and remove duplicates
                merged_table = pd.concat([self_table, other_table], ignore_index=True)
                merged_table = merged_table.drop_duplicates(ignore_index=True)
                self.set_table(group, merged_table)

                # Merge headings
                merged_headings = list(dict.fromkeys(self.get_headings(group) + other.get_headings(group)))
                self.set_heading(group, merged_headings)
            else:
                # Add table and headings from other
                self.set_table(group, other.get_table(group).copy())
                self.set_heading(group, other.get_headings(group))


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
