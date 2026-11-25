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

from functools import cached_property
from io import StringIO
from pathlib import Path
from typing import Literal, TypedDict

import pandas as pd
from pyproj import CRS
from pyproj.exceptions import CRSError
from python_ags4 import AGS4
from python_ags4.AGS4 import AGS4Error

import evo.logging

from ..diagnostics import AgsCode, AgsDiagnostic, AgsSource
from .pandas_utils import coerce_to_object_int

logger = evo.logging.getLogger("data_converters")

# AGS group name constants
LOCA = "LOCA"
SCPG = "SCPG"
SCPT = "SCPT"
SCPP = "SCPP"
GEOL = "GEOL"
PROJ = "PROJ"
UNIT = "UNIT"
HORN = "HORN"

CoordinateFamily = Literal["national", "local", "geographic"]

AGS_STANDARD_GRID_REFERENCES: dict[str, int | str] = {
    "OSGB": 27700,
    "OSI": 29902,
    "ITM": 2157,
    "LOCAL": "unspecified",
}

PARSE_FAILURE_REASON = "The AGS contents could not be parsed. Check the file format and required groups."

# python-ags4 rows that describe the validation run rather than a rule broken by the file
VALIDATOR_PROCESS_KEYS: tuple[str, ...] = ("General", "Validator Process Error")


def _normalize_crs_value(value: object) -> str | None:
    if pd.isna(value) or not str(value).strip():
        return None
    return str(value).upper().strip()


def _crs_from_loca_value(column: str, value: str) -> int | str | None:
    if column == "LOCA_GREF" and value in AGS_STANDARD_GRID_REFERENCES:
        return AGS_STANDARD_GRID_REFERENCES[value]

    try:
        crs = CRS.from_user_input(value)
    except CRSError:
        logger.warning(f"Could not determine CRS from {column}: {value}")
        return None

    epsg = crs.to_epsg()
    if epsg is None:
        logger.warning(f"Could not determine EPSG code from {column}: {value}")
    return epsg


class AgsFileInvalidException(Exception):
    """Raised when an AGS file is invalid.

    This can be due to IO errors, corruption, file not conforming to
    specification, or missing importable groups.

    The keyword-only fields describe the failure for diagnostics. ``reason`` is the user-facing remedy and defaults
    to the first positional argument. ``diagnostics`` holds one entry per validator row when the file breaks AGS rules.
    """

    def __init__(
        self,
        *args: object,
        code: AgsCode = "invalid_file_format",
        reason: str | None = None,
        rule: str | None = None,
        group: str | None = None,
        line: int | None = None,
        diagnostics: tuple[AgsDiagnostic, ...] = (),
    ) -> None:
        super().__init__(*args)
        self.code = code
        self.reason = reason or (str(args[0]) if args else PARSE_FAILURE_REASON)
        self.rule = rule
        self.group = group
        self.line = line
        self.diagnostics = diagnostics


class AgsIncompatibleMergeError(ValueError):
    """Raised when AGS contexts cannot be merged due to project or CRS metadata."""


class AgsValidationRow(TypedDict):
    line: str | int
    group: str
    desc: str


class AgsContext:
    """In-memory context for working with AGS data.

    Provides parsing, validation, table access, and serialization utilities for AGS4 files.
    Handles type conversions, metadata extraction, and merging of multiple AGS contexts.
    """

    _tables: dict[str, pd.DataFrame]
    _headings: dict[str, list[str]]
    _filename: str | None
    sources: tuple[AgsSource, ...]

    # Groups required to import an AGS file as a DownholeCollection
    REQUIRED_GROUPS: tuple[str, ...] = (LOCA, SCPG, SCPT)
    # Non-measurement groups to retain for metadata/geometry
    RETAINED_GROUPS: tuple[str, ...] = (PROJ, UNIT, HORN)
    # Groups that contain measurement data
    MEASUREMENT_GROUPS: tuple[str, ...] = (SCPT, SCPP, GEOL)
    # Depth column of the measurement groups taken at a distance down the hole
    DISTANCE_COLUMNS: dict[str, str] = {SCPT: "SCPT_DPTH"}
    # Top and base depth columns of the measurement groups taken over an interval of the hole
    INTERVAL_COLUMNS: dict[str, tuple[str, str]] = {SCPP: ("SCPP_TOP", "SCPP_BASE"), GEOL: ("GEOL_TOP", "GEOL_BASE")}

    # AGS validation rules that are ignored during file checks
    IGNORED_RULES: tuple[str, ...] = (
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
    )

    # AGS type codes mapped to categories for conversion
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
        # Note: ID, DMS, PA, PT, PU, RL, U, X, XN types fall back to string (default)
    }

    # LOCA coordinate columns (x, y) and elevation column of each coordinate family
    COORDINATE_COLUMNS_BY_FAMILY: dict[CoordinateFamily, tuple[str, str]] = {
        "national": ("LOCA_NATE", "LOCA_NATN"),
        "local": ("LOCA_LOCX", "LOCA_LOCY"),
        "geographic": ("LOCA_LON", "LOCA_LAT"),
    }
    ELEVATION_COLUMN_BY_FAMILY: dict[CoordinateFamily, str] = {
        "national": "LOCA_GL",
        "local": "LOCA_LOCZ",
        "geographic": "LOCA_GL",
    }

    # Used only when the file does not identify a coordinate reference system.
    UNSPECIFIED_COORDINATE_FAMILY_PRIORITY: tuple[CoordinateFamily, ...] = ("national", "local", "geographic")

    def __init__(self) -> None:
        self._tables = dict()
        self._headings = dict()
        self._filename = None
        self.sources = ()

    @property
    def filename(self) -> str:
        """Gets the filename of the AGS file, if available.

        Fallback (e.g. StringIO): combine PROJ_NAME and PROJ_ID from PROJ table.

        :returns: filename or combined project identifier
        :raises ValueError: if neither filename or project identifiers are available
        """
        if self._filename is not None:
            return self._filename
        elif PROJ in self._tables:
            row = self._tables[PROJ].iloc[0]
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
        :raises AgsFileInvalidException: in-memory AGS file is invalid, error while parsing, missing required groups,
            or LOCA rows declaring different coordinate reference systems
        """
        try:
            self.check_ags_file(filepath)
            if isinstance(filepath, (Path, str)):
                self._filename = Path(filepath).stem
            tables, headings = AGS4.AGS4_to_dataframe(filepath, get_line_numbers=False)
            self.set_tables_and_headings(tables, headings)
        except AGS4Error as e:
            logger.warning(f"python-ags4 could not read the AGS file: {e}")
            raise AgsFileInvalidException("Failed to parse AGS file", reason=PARSE_FAILURE_REASON) from e

        # Validate whether we can import these dataframes to a Downhole Collection
        if errors := self._validate_groups():
            reason = " ".join(errors)
            raise AgsFileInvalidException(f"AGS file is invalid: {reason}", reason=reason)

        # Ensure the LOCA rows share a single coordinate reference system
        _ = self.coordinate_reference_system

    def check_ags_file(self, filepath: Path | str | StringIO) -> None:
        """Checks an AGS file to validate conformity to AGS spec.

        Some rules are ignored, defined in this class.

        :param filepath: Path to the AGS file.
        :raises AgsFileInvalidException: if file doesn't conform
        """
        ags_parse_errors: dict[str, list[AgsValidationRow]] = AGS4.check_file(filepath)
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
            logger.warning("AGS validation failed:%s", ags4_errors_to_str(ags_parse_errors))
            diagnostics = ags4_errors_to_diagnostics(ags_parse_errors)
            raise AgsFileInvalidException(
                "AGS file is invalid: "
                + "; ".join(f"{issue.rule}: {issue.reason}" if issue.rule else issue.reason for issue in diagnostics),
                diagnostics=diagnostics,
            )

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
        """Validate the in-memory AGS groups and coordinate reference systems, returning error messages.

        An empty list will be returned if no errors were found.

        :returns: list of error messages, or an empty list.
        """
        errors = self._validate_groups()
        try:
            _ = self.coordinate_reference_system
        except AgsFileInvalidException as e:
            errors.append(str(e))
        return errors

    def _validate_groups(self) -> list[str]:
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
        :raises AgsFileInvalidException: if the PROJ table, its PROJ_ID column or its first row is missing
        """
        try:
            proj_id = self.get_table(PROJ).at[0, "PROJ_ID"]
        except KeyError as e:
            raise AgsFileInvalidException(
                "PROJ_ID not found in PROJ table",
                reason="Add a PROJ group containing a PROJ_ID.",
            ) from e
        return str(proj_id)

    @property
    def coordinate_reference_system(self) -> int | str | None:
        """Gets the coordinate reference system shared by the LOCA rows of the in-memory AGS file.

        The CRS is resolved per LOCA row, preferring `LOCA_GREF` over `LOCA_LLZ`. Rows without
        a CRS adopt the CRS declared by the other rows.

        :returns: epsg code as integer or "unspecified" if a CRS can be determined, None otherwise.
        :raises AgsFileInvalidException: if LOCA rows declare different coordinate reference systems.
        """
        crs_gref = self.crs_from_loca_gref()
        crs_llz = self.crs_from_loca_llz()

        both = [loca_id for loca_id, crs in crs_gref.items() if crs is not None and crs_llz[loca_id] is not None]
        if both:
            logger.warning(f"Found CRS for both LOCA_GREF and LOCA_LLZ, preferring LOCA_GREF for LOCA_IDs: {both}")

        crs_by_location = {loca_id: crs if crs is not None else crs_llz[loca_id] for loca_id, crs in crs_gref.items()}
        return self._shared_crs(crs_by_location)

    def get_table(self, group: str) -> pd.DataFrame:
        """Gets a table by group name.

        :param group: Group name to retrieve the DataFrame for
        :return: DataFrame containing the table data, or an empty DataFrame if not present
        """
        return self.tables.get(group, pd.DataFrame())

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

    def crs_from_loca_gref(self) -> dict[str, int | str | None]:
        """
        Try to determine the CRS declared in LOCA_GREF for each LOCA_ID.

        :returns: Mapping of LOCA_ID to None if we can't determine a CRS, "unspecified" if the
            CRS is locally defined, or an integer if we found an EPSG CRS.
        """
        return self._crs_by_location("LOCA_GREF")

    def crs_from_loca_llz(self) -> dict[str, int | None]:
        """
        Try to determine the CRS declared in LOCA_LLZ for each LOCA_ID.

        :returns: Mapping of LOCA_ID to None if we can't determine a CRS, or the EPSG code if found.
        """
        return {
            loca_id: crs if isinstance(crs, int) else None for loca_id, crs in self._crs_by_location("LOCA_LLZ").items()
        }

    def _crs_by_location(self, column: str) -> dict[str, int | str | None]:
        loca = self.get_table(LOCA)
        if "LOCA_ID" not in loca:
            return {}
        values = loca[column] if column in loca else pd.Series(pd.NA, index=loca.index)
        normalized = [_normalize_crs_value(value) for value in values]
        crs_by_value = {
            value: _crs_from_loca_value(column, value) for value in dict.fromkeys(normalized) if value is not None
        }
        return {
            str(loca_id): crs_by_value[value] if value is not None else None
            for loca_id, value in zip(loca["LOCA_ID"], normalized)
        }

    @staticmethod
    def _shared_crs(crs_by_location: dict[str, int | str | None]) -> int | str | None:
        declared = {crs for crs in crs_by_location.values() if crs is not None}
        if len(declared) > 1:
            raise AgsFileInvalidException(
                f"LOCA rows declare different coordinate reference systems: {sorted(map(str, declared))}. "
                "A downhole collection supports a single coordinate reference system.",
                code="invalid_coordinates",
                reason="Use one coordinate reference system for all LOCA rows.",
            )
        if not declared:
            return None

        crs = declared.pop()
        undeclared = [loca_id for loca_id, value in crs_by_location.items() if value is None]
        if undeclared:
            logger.warning(f"No CRS declared for LOCA_IDs: {undeclared}, assuming {crs}")
        return crs

    def validate_merge(self, other: "AgsContext", raise_on_error: bool = True) -> list[str]:
        """Validate whether another AgsContext can be merged into this one.

        Checks PROJ_ID and CRS compatibility, returning a list of incompatibility
        issues found.

        :param other: The AgsContext to validate for merging
        :param raise_on_error: If True, raises AgsIncompatibleMergeError on first incompatibility found
        :returns: List of incompatibility warning messages (empty if compatible)
        :raises AgsIncompatibleMergeError: If raise_on_error=True and contexts are incompatible
        """
        issues: list[str] = []

        # Check PROJ_ID compatibility
        if self.proj_id != other.proj_id:
            msg = (
                f"Incompatible PROJ_ID: first has '{self.proj_id}', second has '{other.proj_id}'. "
                f"Rows from first context will be kept for duplicate LOCA_IDs and (LOCA_ID, SCPG_TESN) pairs."
            )
            if raise_on_error:
                raise AgsIncompatibleMergeError(f"Cannot merge AgsContext instances: {msg}")
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
                raise AgsIncompatibleMergeError(f"Cannot merge AgsContext instances: {msg}")
            issues.append(msg)

        return issues

    def merge(self, other: "AgsContext", validate_compatibility: bool = True) -> None:
        """Merge another AgsContext into this one (in-place).

        Concatenates measurement and location tables while validating metadata
        compatibility. Modifies self and leaves other unchanged.
        If no longer needed, consider freeing memory by deleting other.

        Merging strategy:
        - Metadata-like tables (e.g., PROJ, UNIT): Keep from self
        - LOCA: Concatenate, check for duplicate LOCA_ID
        - SCPG: Concatenate, check for duplicate (LOCA_ID, SCPG_TESN) pairs
        - HORN: Concatenate all rows for dip/azimuth measurements
        - Measurement tables (SCPT, SCPP, GEOL): Concatenate all rows

        :param other: The AgsContext to merge into this one
        :param validate_compatibility: If True, raises error on incompatibility; if False, logs warnings
        :raises AgsIncompatibleMergeError: If contexts are incompatible and validation is enabled
        """
        # Check compatibility and handle based on validate_compatibility flag
        issues = self.validate_merge(other, raise_on_error=validate_compatibility)

        # Log any issues as warnings when validation is disabled
        for issue in issues:
            logger.warning(f"Merging AgsContext instances: {issue}")

        # LOCA table: concatenate and check for duplicates
        self._merge_loca(other)

        # SCPG table: concatenate and check for duplicate (LOCA_ID, SCPG_TESN) pairs
        self._merge_scpg(other)

        # HORN table: contains dip/azimuth measurements, concatenate all rows
        self._merge_measurement_table(HORN, other)

        # Measurement tables: concatenate all rows
        for group in self.MEASUREMENT_GROUPS:
            self._merge_measurement_table(group, other)

    def _merge_loca(self, other: "AgsContext") -> None:
        """Merge LOCA tables from another AgsContext into this one.

        Checks for duplicate LOCA_ID values and if so, keeps rows from self.
        All unique rows are concatenated.

        :param other: The AgsContext to merge LOCA table from
        """
        self_loca = self.get_table(LOCA)
        other_loca = other.get_table(LOCA)

        # Concatenate and remove duplicates, keeping first occurrence (from self)
        merged_loca = pd.concat([self_loca, other_loca], ignore_index=True)

        # Check for duplicates before dropping them
        duplicate_ids = merged_loca[merged_loca.duplicated(subset=["LOCA_ID"], keep="first")]["LOCA_ID"].tolist()
        if duplicate_ids:
            logger.warning(
                f"Found {len(duplicate_ids)} duplicate LOCA_ID values "
                f"when merging contexts. Keeping rows from first context. "
                f"Duplicate IDs: {duplicate_ids}"
            )

        merged_loca = merged_loca.drop_duplicates(subset=["LOCA_ID"], keep="first", ignore_index=True)
        self.set_table(LOCA, merged_loca)

        # Merge headings (union of both)
        merged_headings = list(dict.fromkeys(self.get_headings(LOCA) + other.get_headings(LOCA)))
        self.set_heading(LOCA, merged_headings)

    def _merge_scpg(self, other: "AgsContext") -> None:
        """Merge SCPG tables from another AgsContext into this one.

        Checks for duplicate (LOCA_ID, SCPG_TESN) pairs and if so, keeps rows from self.
        All unique rows are concatenated.

        :param other: The AgsContext to merge SCPG table from
        """
        self_scpg = self.get_table(SCPG)
        other_scpg = other.get_table(SCPG)

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
        self.set_table(SCPG, merged_scpg)

        # Merge headings
        merged_headings = list(dict.fromkeys(self.get_headings(SCPG) + other.get_headings(SCPG)))
        self.set_heading(SCPG, merged_headings)

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


def ags4_errors_to_str(errors: dict[str, list[AgsValidationRow]]) -> str:
    """Render raw validator rows for logs and legacy callers, not user-facing conversion feedback."""
    parts: list[str] = []
    for rule, rows in errors.items():
        parts.append(f"\n{rule}:\n")
        for row in rows:
            parts.append(f"  L{row['line']}, Group {row['group'] or 'NULL'}: {row['desc']}\n")
    return "".join(parts)


def ags4_errors_to_diagnostics(errors: dict[str, list[AgsValidationRow]]) -> tuple[AgsDiagnostic, ...]:
    """Normalize python-ags4 validation rows to diagnostics without exposing raw row values.

    Notes and failures of the validation run itself only produce a generic diagnostic when no AGS rule was reported.
    """
    diagnostics = tuple(
        _validator_row_to_diagnostic(rule, row)
        for rule, rows in errors.items()
        if rule not in VALIDATOR_PROCESS_KEYS
        for row in rows
    )
    return diagnostics or (
        AgsDiagnostic(
            code="invalid_file_format",
            severity="error",
            sources=(),
            reason="The file could not be validated as AGS4. Check that it is a valid AGS4 file.",
        ),
    )


def _validator_row_to_diagnostic(rule: str, row: AgsValidationRow) -> AgsDiagnostic:
    raw_line = str(row["line"])
    line = int(raw_line) if raw_line.isdecimal() and int(raw_line) > 0 else None
    if rule == "AGS Format Rule 3":
        if "AGS3" in row["desc"]:
            reason = "AGS3 files are not supported. Convert the file to AGS4."
        else:
            reason = "A line does not start with a valid AGS data descriptor."
    elif rule == "AGS Format Rule 5":
        reason = "Enclose every AGS field in double quotes."
    else:
        reason = f"Correct the AGS file to comply with {rule}."
    return AgsDiagnostic(
        code="invalid_file_format",
        severity="error",
        sources=(),
        reason=reason,
        rule=rule,
        group=row["group"].strip() or None,
        line=line,
    )
