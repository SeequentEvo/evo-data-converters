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

from evo.data_converters.common.objects.downhole_collection import (
    ColumnMapping,
    DownholeCollection,
    HoleCollars,
    MeasurementTableFactory,
)
from pygef.cpt import CPTData
import pandas as pd
import polars as pl
import typing
import evo.logging

from collections import defaultdict

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
        self.measurement_dfs: list[pl.DataFrame] = []
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
        if cpt_data.final_depth != 0.0:
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
        return collar_data | collar_attributes

    def _prepare_measurements(self, hole_index: int, cpt_data: CPTData) -> pl.DataFrame:
        """Prepare measurements DataFrame with hole_index as first column.

        :param hole_index: Sequential index for this hole
        :param cpt_data: CPT data object

        :return: Polars DataFrame with measurements
        """
        measurements = cpt_data.data.with_columns(pl.lit(hole_index).cast(pl.Int32).alias("hole_index"))

        # Reorder columns to put hole_index first
        other_cols = [col for col in cpt_data.data.columns if col != "hole_index"]
        return measurements.select(["hole_index"] + other_cols)

    def _track_nan_values(self, cpt_data: CPTData) -> None:
        """Track NaN values by attribute name.

        :param cpt_data: CPT data object
        """
        for attribute_name, value in cpt_data.column_void_mapping.items():
            if value not in self.nan_values_by_attribute[attribute_name]:
                self.nan_values_by_attribute[attribute_name].append(value)

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
            measurements_pl = pl.concat(items=self.measurement_dfs, how="vertical")
            measurements = measurements_pl.to_pandas()
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
        column_mapping = ColumnMapping(DEPTH_COLUMNS=["penetrationLength"])
        distance_measurements = MeasurementTableFactory.create(
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
