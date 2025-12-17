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

import typing
from collections import defaultdict

import pandas as pd
import polars as pl
from pint_pandas import PintType as _  # noqa: F401
from pygef.cpt import CPTData

import evo.logging
from evo.data_converters.common.objects.downhole_collection import (
    ColumnMapping,
    DownholeCollection,
    HoleCollars,
    create_measurement_table,
)

from .gef_spec import MEASUREMENT_TEXT_NAMES, MEASUREMENT_UNIT_CONVERSIONS, MEASUREMENT_UNITS, MEASUREMENT_VAR_NAMES

logger = evo.logging.getLogger("data_converters")


class DownholeCollectionBuilder:
    """Builds an intermediary DownholeCollection from parsed GEF CPT files."""

    # Keys to exclude from CPTData when building hole collar attributes
    COLLAR_EXCLUDE_KEYS: list[str] = [
        "alias",
        "bro_id",
        "column_void_mapping",
        "data",
        "delivered_location",
        "delivered_vertical_position_datum",
        "final_depth",
        "raw_headers",
    ]

    # Data types we expect for required hole collar information
    COLLAR_DTYPES: dict[str, str] = {
        "hole_index": "int32",
        "hole_id": "string",
        "x": "float64",
        "y": "float64",
        "z": "float64",
        "final_depth": "float64",
    }

    def __init__(self) -> None:
        self.epsg_code: int | str | None = None
        self.collar_rows: list[dict[str, typing.Any]] = []
        self.collection_name: str | None = None
        self.measurement_dfs: list[pd.DataFrame] = []
        self.nan_values_by_attribute: dict[str, list[typing.Any]] = defaultdict(list)

    def process_cpt_file(self, hole_index: int, hole_id: str, cpt_data: CPTData) -> None:
        """Process a single CPT file and add to the collection.

        :param hole_index: Sequential index for this hole
        :param hole_id: Unique identifier for this hole
        :param cpt_data: Parsed CPT data object
        """
        self._validate_and_set_epsg(cpt_data, hole_id)
        self._validate_location_attributes(cpt_data, hole_id)

        collar_row = self._create_collar_row(hole_index, hole_id, cpt_data)
        self.collar_rows.append(collar_row)

        measurements = self._prepare_measurements(hole_index, cpt_data)
        measurements = self._apply_measurement_units(measurements, cpt_data)

        self.measurement_dfs.append(measurements)

        self._track_nan_values(cpt_data)

        logger.debug(f"Processed {hole_id}: {len(measurements)} measurements")

    def build(self) -> DownholeCollection:
        """Build the final DownholeCollection.

        :return: Completed DownholeCollection object

        :raises ValueError: If EPSG code was not set during processing
        """
        self._validate_epsg_code()

        collars_df = self._create_collars_dataframe()
        measurements_df = self._create_measurements_dataframe()
        measurements_df = self._apply_nan_values_to_measurements(measurements_df)
        collection_name = self.collection_name or self._generate_collection_name()

        return self._create_collection(collection_name, collars_df, measurements_df)

    def set_name(self, name: str) -> None:
        self.collection_name = name

    def _extract_epsg_code(self, cpt_data: CPTData, hole_id: str) -> int | str:
        """Extract EPSG code from CPTData object.

        :param cpt_data: CPT data object
        :param hole_id: Hole identifier for error messages

        :return: EPSG code as int, or "unspecified" string

        :raises ValueError: If EPSG code is missing or malformed
        """
        try:
            srs_name = cpt_data.delivered_location.srs_name
        except AttributeError:
            raise ValueError(f"CPT file '{hole_id}' is missing delivered_location.srs_name attribute")

        if ":" not in srs_name:
            raise ValueError(f"CPT file '{hole_id}' has malformed SRS name: '{srs_name}'. Expected format: 'urn:123'")

        try:
            epsg_code = int(srs_name.split(":")[-1])
        except (ValueError, IndexError) as e:
            raise ValueError(f"CPT file '{hole_id}' has invalid EPSG code in SRS name: '{srs_name}'. Error: {e}")

        if epsg_code == 404000:
            epsg_code = "unspecified"

        return epsg_code

    def _validate_and_set_epsg(self, cpt_data: CPTData, hole_id: str) -> None:
        """Validate and set EPSG code, ensuring consistency across files.

        :param cpt_data: CPT data object
        :param hole_id: Hole identifier for error messages

        :raises ValueError: If EPSG codes are inconsistent across files
        """
        current_epsg = self._extract_epsg_code(cpt_data, hole_id)

        if self.epsg_code is None:
            self.epsg_code = current_epsg
            logger.info(f"Using EPSG code {self.epsg_code} from first CPT file")
        elif self.epsg_code != current_epsg:
            raise ValueError(
                f"Inconsistent EPSG codes: {hole_id} has EPSG:{current_epsg}, but expected EPSG:{self.epsg_code}"
            )

    def _validate_epsg_code(self) -> None:
        """Validate that an EPSG code was found during processing.

        :raises ValueError: If no EPSG code was set
        """
        if self.epsg_code is None:
            raise ValueError("Could not find valid epsg code in CPT files")

    def _validate_location_attributes(self, cpt_data: CPTData, hole_id: str) -> None:
        """Validate that required x, y location attributes exist.

        :param cpt_data: CPT data object
        :param hole_id: Hole identifier for error messages

        :raises ValueError: If x or y location attributes are missing
        """
        try:
            _ = cpt_data.delivered_location.x
            _ = cpt_data.delivered_location.y
        except AttributeError as e:
            raise ValueError(f"CPT file '{hole_id}' is missing required location attribute (x or y): {e}")

    def _calculate_final_depth(self, cpt_data: CPTData, hole_id: str) -> float:
        """Calculate final depth from CPTData.

        :param cpt_data: CPT data object
        :param hole_id: Hole identifier for error messages

        :return: Final depth value

        :raises ValueError: If depth cannot be determined
        """
        if cpt_data.final_depth is not None and cpt_data.final_depth != 0.0:
            return cpt_data.final_depth

        # Try to calculate from penetrationLength column
        if "penetrationLength" not in cpt_data.data.columns:
            raise ValueError(f"CPT file '{hole_id}' is missing 'penetrationLength' column.")

        penetration_lengths = cpt_data.data["penetrationLength"]

        if len(penetration_lengths) == 0:
            raise ValueError(f"CPT file '{hole_id}' has empty penetrationLength column.")

        try:
            return float(penetration_lengths.max())
        except Exception as e:
            raise ValueError(f"CPT file '{hole_id}' has invalid penetrationLength data: {e}")

    def _get_collar_attributes(self, cpt_data: CPTData) -> dict[str, typing.Any]:
        """Extract collar attributes from CPTData, excluding specified keys and empty values.

        :param cpt_data: CPT data object

        :return: Dictionary of filtered attributes
        """
        filtered_hash: dict[str, typing.Any] = {
            k: v
            for k, v in vars(cpt_data).items()
            if k not in self.COLLAR_EXCLUDE_KEYS and not k.startswith("_") and not (v is None or v == [] or v == {})
        }
        return filtered_hash

    def _get_raw_header_info(self, cpt_data: CPTData) -> dict[str, typing.Any]:
        """Extract the raw header info we are interested in from CPTData
        The raw headers are 'flattened' into a single dictionary with the format:

        {"measurementtext_1": "value", "measurementtext_2": "value", ...}

        Where 'value' is a comma separated string of the values in the raw header, and
        the raw header name (eg 'MEASUREMENTTEXT') is converted to lowercase and suffixed
        with the id of the raw header (eg '1').

        :param cpt_data: CPT data object

        :return: Dictionary of raw header information
        """
        raw_header_info = {}

        if not hasattr(cpt_data, "raw_headers"):
            return raw_header_info

        raw_headers_to_include = ["MEASUREMENTTEXT", "MEASUREMENTVAR"]
        for raw_header_name in raw_headers_to_include:
            if raw_header_name in cpt_data.raw_headers:
                items = cpt_data.raw_headers[raw_header_name]

                for id_, *values in items:
                    value = ", ".join(str(v) for v in values)
                    if raw_header_name == "MEASUREMENTTEXT":
                        key = MEASUREMENT_TEXT_NAMES.get(int(id_), f"measurementtext_{id_}")
                    elif raw_header_name == "MEASUREMENTVAR":
                        key = MEASUREMENT_VAR_NAMES.get(int(id_), f"measurementvar_{id_}")
                    else:
                        key = f"{raw_header_name.lower()}_{id_}"

                    raw_header_info[key] = value

        return raw_header_info

    def _create_collar_row(self, hole_index: int, hole_id: str, cpt_data: CPTData) -> dict[str, typing.Any]:
        """Create a collar data row for a single hole.

        :param hole_index: Sequential index for this hole
        :param hole_id: Unique identifier for this hole
        :param cpt_data: CPT data object

        :return: Dictionary containing collar data and attributes
        """
        final_depth = self._calculate_final_depth(cpt_data, hole_id)

        collar_data = {
            "hole_index": hole_index,
            "hole_id": hole_id,
            "x": cpt_data.delivered_location.x,
            "y": cpt_data.delivered_location.y,
            "z": cpt_data.delivered_vertical_position_offset or 0.0,
            "final_depth": final_depth,
        }
        collar_attributes = self._get_collar_attributes(cpt_data)
        raw_header_info = self._get_raw_header_info(cpt_data)
        return collar_data | collar_attributes | raw_header_info

    def _prepare_measurements(self, hole_index: int, cpt_data: CPTData) -> pd.DataFrame:
        """Prepare measurements DataFrame with hole_index as first column.

        :param hole_index: Sequential index for this hole
        :param cpt_data: CPT data object

        :return: Pandas DataFrame with measurements
        """
        df = cpt_data.data.with_columns(pl.lit(hole_index).cast(pl.Int32).alias("hole_index"))

        df = self.calculate_dip(df)
        df = self.calculate_azimuth(df)

        # Reorder columns to put hole_index first
        other_cols = [col for col in df.columns if col != "hole_index"]
        df = df.select(["hole_index"] + other_cols).to_pandas()

        return df

    def calculate_dip(self, df: pl.DataFrame) -> pl.DataFrame:
        """Create dip column from inclinationResultant.

        Inclination resultant is degrees of deviation from vertical, dip requires degrees from horizontal.

        :param df: Polars dataframe with possible inclination column.

        :return: Polars dataframe with new "dip" column, or the original.
        """
        if "inclinationResultant" not in df.columns:
            return df

        return df.with_columns((90 - pl.col("inclinationResultant")).alias("dip"))

    def calculate_azimuth(self, df: pl.DataFrame) -> pl.DataFrame:
        """Calculate azimuth from N-S/E-W inclination components.

        Adds an 'azimuth' column if inclinationNS and inclinationEW exist.

        :param df: Polars dataframe with possible directional data.

        :return: Polars dataframe with new "azimuth" column, or the original.
        """
        has_ns = "inclinationNS" in df.columns
        has_ew = "inclinationEW" in df.columns

        if not (has_ns and has_ew):
            return df

        ns = pl.col("inclinationNS")
        ew = pl.col("inclinationEW")

        # Calculate azimuth and normalise to 0-360°
        # Note: atan2(ew, ns) gives angle clockwise from north
        azimuth = (pl.arctan2(ew, ns).degrees() + 360) % 360

        # Set to null if either input is null
        azimuth = pl.when(ns.is_null() | ew.is_null()).then(None).otherwise(azimuth)

        return df.with_columns(azimuth.alias("azimuth"))

    def _apply_measurement_units(self, measurements: pd.DataFrame, cpt_data: CPTData) -> pd.DataFrame:
        """Apply pint units to the measurements DataFrame based on looking up the expected
        units for the column name in the MEASUREMENT_UNITS dictionary. If the column name
        maps to an empty string then the column is treated as dimensionless, and is not
        modified here. If the column name maps to a unit that is in the
        MEASUREMENT_UNIT_CONVERSIONS dictionary then the column is converted to the
        specified unit. NOTE: This conversion will possibly modify the data.

        :param measurements: The measurements DataFrame to apply units to
        :param cpt_data: CPT data object

        :return: DataFrame with applied pint units
        """
        for col in cpt_data.data.columns:
            if col in MEASUREMENT_UNITS and MEASUREMENT_UNITS[col] != "":
                gef_unit = MEASUREMENT_UNITS[col]
                measurements[col] = measurements[col].astype(f"pint[{gef_unit}]")
                if gef_unit in MEASUREMENT_UNIT_CONVERSIONS:
                    measurements[col] = measurements[col].pint.to(MEASUREMENT_UNIT_CONVERSIONS[gef_unit])

        return measurements

    def _track_nan_values(self, cpt_data: CPTData) -> None:
        """Track NaN values by attribute name.

        :param cpt_data: CPT data object
        """
        try:
            for attribute_name, value in cpt_data.column_void_mapping.items():
                if value not in self.nan_values_by_attribute[attribute_name]:
                    self.nan_values_by_attribute[attribute_name].append(value)
        except AttributeError:
            return

    def _apply_nan_values_to_measurements(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replace sentinel values with np.nan in measurement dataframe.

        :param df: The dataframe containing all measurements
        """
        for col, sentinels in self.nan_values_by_attribute.items():
            if col in df.columns:
                df[col] = df[col].mask(df[col].isin(sentinels))

        return df

    def _create_collars_dataframe(self) -> pd.DataFrame:
        """Create the collars DataFrame from accumulated collar rows.

        :return: Pandas DataFrame with typed collar data
        """
        return pd.DataFrame(self.collar_rows).astype(dtype=self.COLLAR_DTYPES)

    def _create_measurements_dataframe(self) -> pd.DataFrame:
        """Create the measurements DataFrame from accumulated measurement DataFrames.

        :return: Pandas DataFrame with all measurements
        """
        if self.measurement_dfs:
            measurements = pd.concat(self.measurement_dfs, axis=0, ignore_index=True)
            logger.info(f"Creating collection with {len(measurements)} total measurements")
            return measurements
        else:
            logger.warning("No measurement data found in CPT files")
            return pd.DataFrame(columns=["hole_index"])

    def _generate_collection_name(self) -> str:
        """Generate a collection name from collar data.

        :return: Collection name
        """
        if not self.collar_rows:
            return ""
        elif len(self.collar_rows) == 1:
            return self.collar_rows[0]["hole_id"]
        else:
            return f"{self.collar_rows[0]['hole_id']}...{self.collar_rows[-1]['hole_id']}"

    def _create_collection(
        self, collection_name: str, collars_df: pd.DataFrame, measurements_df: pd.DataFrame
    ) -> DownholeCollection:
        """Create the intermediary DownholeCollection object.

        :param collection_name: Name for the collection
        :param collars_df: DataFrame with collar data
        :param measurements_df: DataFrame with measurement data

        :return: Intermediary DownholeCollection object
        """
        column_mapping = ColumnMapping(
            DEPTH_COLUMNS=["penetrationLength"], DIP_COLUMNS=["dip"], AZIMUTH_COLUMNS=["azimuth"]
        )
        distance_measurements = create_measurement_table(
            df=measurements_df, column_mapping=column_mapping, nan_values_by_column=self.nan_values_by_attribute
        )
        collars = HoleCollars(df=collars_df)

        return DownholeCollection(
            name=collection_name,
            collars=collars,
            measurements=[distance_measurements],
            coordinate_reference_system=self.epsg_code,
        )


def create_from_parsed_gef_cpts(
    parsed_cpt_files: dict[str, CPTData],
    name: str | None = None,
) -> DownholeCollection:
    """
    Create a DownholeCollection from parsed GEF CPT files.

    :param parsed_cpt_files: Dictionary mapping hole IDs to CPTData objects
    :param name: (Optional) custom name, or generated from GEF IDs

    :return: DownholeCollection containing collar and measurement data

    :raises ValueError: If no CPT files provided, EPSG codes are inconsistent,
                        or required data is missing/malformed
    """
    if not parsed_cpt_files:
        raise ValueError("No CPT files provided - parsed_cpt_files dictionary is empty")

    builder = DownholeCollectionBuilder()

    if name:
        builder.set_name(name)

    for hole_index, (hole_id, cpt_data) in enumerate(parsed_cpt_files.items(), start=1):
        builder.process_cpt_file(hole_index, hole_id, cpt_data)

    return builder.build()
