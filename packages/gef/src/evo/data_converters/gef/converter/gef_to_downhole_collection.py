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
from __future__ import annotations

import dataclasses
import typing
from typing import Any

import numpy as np
import pandas as pd
from pint_pandas import PintType
from pygef.common import Location as PygefLocation
from pygef.cpt import CPTData

import evo.logging
from evo.objects.typed.types import EpsgCode

from .gef_spec import (
    COLLAR_ATTRIBUTES,
    COMPUTED,
    MEASUREMENT_TEXT_NAMES,
    MEASUREMENT_UNIT_CONVERSIONS,
    MEASUREMENT_UNITS,
    MEASUREMENT_VAR_NAMES, CAMEL_TO_SNAKE,
)
from ..common_gef import CPTSource, ParsedCptFile
from ..objects import DownholeCollectionData, DistanceCollection, AttributeDescription
from ...common import crs_from_any, InvalidCRSError
from ...common.crs import SchemaCrsCode, UNSPECIFIED
from ...common.objects.units import UnitMapper

logger = evo.logging.getLogger("data_converters")


# Data types required by the GO schema
HOLE_PROPERTIES_DTYPES: dict[str, str] = {
    "hole_id": "string",
    "x": "float64",
    "y": "float64",
    "z": "float64",
    "final": "float64",
    "current": "float64",
    "target": "float64",
}

PATH_ATTRIBUTES: list[str] = [
    "dip",
    "azimuth",
    "depth_offset",
    "elapsed_time",
    "inclination_ew",
    "inclination_ns",
    "inclination_resultant",
    "depth",
]


@dataclasses.dataclass
class ProcessedCPT:
    project_id: str | None
    parsed: ParsedCptFile
    location: _Location
    delivered_location: _Location | None
    distances: _Distances
    hole_attributes: dict[str, Any]
    cpt_table: pd.DataFrame

    @property
    def hole_id(self):
        return self.parsed.hole_id


@dataclasses.dataclass
class _Location:
    x: float
    y: float
    z: float
    crs: SchemaCrsCode

    def xyz_dict(self):
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }


@dataclasses.dataclass
class _Distances:
    final: float
    current: float
    target: float


def process_cpt_files(parsed_cpt_files: dict[str, tuple[str, CPTData]]) -> list[ProcessedCPT]:
    processed = []
    for hole_id, (filepath, cpt_data) in parsed_cpt_files.items():
        cpt = ParsedCptFile(filepath=filepath, hole_id=hole_id, data=cpt_data)
        processed.append(process_cpt_file(cpt))
    return processed


def process_cpt_file(cpt: ParsedCptFile) -> ProcessedCPT:
    """Extract and process all data we care about from the pygef data"""
    project_id = _extract_project_id(cpt)
    location, delivered_location = _process_locations(cpt)
    distances = _process_distances(cpt)
    hole_attributes = _process_hole_attributes(cpt)
    cpt_table = _process_cpt_table(cpt)

    logger.debug(f"Processed {cpt.hole_id}: {len(cpt_table)} measurements")

    return ProcessedCPT(
        project_id=project_id,
        parsed=cpt,
        location=location,
        delivered_location=delivered_location,
        distances=distances,
        hole_attributes=hole_attributes,
        cpt_table=cpt_table,
    )


def _extract_crs(location: PygefLocation) -> SchemaCrsCode:
    # For GEF, pygef infers srs_name from GEF's bespoke CRS description in the #XYID header
    srs_name = location.srs_name
    try:
        crs: SchemaCrsCode = crs_from_any(srs_name)
    except InvalidCRSError as e:
        logger.warning(f"Invalid or unrecognized CRS description: '{srs_name}'")
        crs = "unspecified"

    if hasattr(crs, "epsg_code") and crs.epsg_code == 404000:
        logger.warning(f"Invalid or unrecognized CRS description: '{srs_name}'")
        crs = "unspecified"

    return crs


def _extract_attributes_as_dict_from_object(cpt_data: CPTData) -> dict[str, typing.Any]:
    """Extract collar attributes from CPTData, based on a whitelist of hte ones we care about."""
    filtered_hash: dict[str, typing.Any] = {
        k: v
        for k, v in vars(cpt_data).items()
        # TODO Do we want these computed fields to be published?
        if k in COLLAR_ATTRIBUTES + COMPUTED and not (v is None or v == [] or v == {})
    }
    return filtered_hash

def _extract_attributes_from_raw_headers(cpt_data: CPTData) -> dict[str, typing.Any]:
    """Extract the raw header info we are interested in from CPTData
    The raw headers are 'flattened' into a single dictionary with the format:

    {"measurementtext_1": "value", "measurementtext_2": "value", ...}

    Where 'value' is a comma separated string of the values in the raw header, and
    the raw header name (eg 'MEASUREMENTTEXT') is converted to lowercase and suffixed
    with the id of the raw header (eg '1').
    """
    processed_raw_headers = {}

    raw_headers_to_include = ["MEASUREMENTTEXT", "MEASUREMENTVAR"]
    for raw_header_name in raw_headers_to_include:
        if raw_header_name in (cpt_data.raw_headers or {}):
            items = cpt_data.raw_headers[raw_header_name]

            for id_, *values in items:
                value = ", ".join(str(v) for v in values)
                if raw_header_name == "MEASUREMENTTEXT":
                    key = MEASUREMENT_TEXT_NAMES.get(int(id_), f"measurementtext_{id_}")
                elif raw_header_name == "MEASUREMENTVAR":
                    key = MEASUREMENT_VAR_NAMES.get(int(id_), f"measurementvar_{id_}")
                else:
                    key = f"{raw_header_name.lower()}_{id_}"

                processed_raw_headers[key] = value

    return processed_raw_headers


def _extract_project_id(cpt: ParsedCptFile) -> str | None:
    cpt_source = CPTSource.infer_from_cpt_data(cpt.data)
    if cpt_source == CPTSource.GEF:
        proj_id_list_of_lists: list[list[str]] = cpt.data.raw_headers.get("PROJECTID", [[""]])
        proj_id = ", ".join(proj_id_list_of_lists[0])
        return proj_id
    else:
        # BRO-XML doesn't have anything equivalent to GEF's "PROJECTID"
        return None


def _process_locations(cpt: ParsedCptFile) -> tuple[_Location, _Location | None]:
    z = cpt.data.delivered_vertical_position_offset or 0.0
    delivered_crs = _extract_crs(cpt.data.delivered_location)
    delivered_xyz = _Location(cpt.data.delivered_location.x, cpt.data.delivered_location.y, z, delivered_crs)
    if cpt.data.standardized_location is None:
        # TODO - This is going to be the case with GEF. There's a problem with this. There is no guarantee that
        #  multiple GEFs will all have the same CRS description, but the GO schema is forcing a single CRS.
        #  It might be necessary to standardize this ourselves.
        xyz = delivered_xyz
        delivered_xyz = None
    else:
        standardized_crs = _extract_crs(cpt.data.standardized_location)
        xyz = _Location(cpt.data.standardized_location.x, cpt.data.standardized_location.y, z, standardized_crs)

    return xyz, delivered_xyz


def _process_distances(cpt: ParsedCptFile) -> _Distances:
    """Get final, current, and target depths. They only have one value so it gets duplicated for all three."""
    if cpt.data.final_depth is not None and cpt.data.final_depth != 0.0:
        final_depth = cpt.data.final_depth
    else:
        # TODO - ensure test coverage for this code path
        final_depth = float(cpt.data.data["penetrationLength"].max())
    return _Distances(final=final_depth, current=final_depth, target=final_depth)


def _process_hole_attributes(cpt: ParsedCptFile) -> dict[str, typing.Any]:
    """Extract miscellaneous attributes from the CPT data"""
    collar_attributes = _extract_attributes_as_dict_from_object(cpt.data)
    raw_header_info = _extract_attributes_from_raw_headers(cpt.data)
    return collar_attributes | raw_header_info


def _process_cpt_table(cpt: ParsedCptFile) -> pd.DataFrame:
    """Process the primary CPT table data"""
    df = cpt.data.data.to_pandas()
    df = _apply_nan_mapping(df, cpt)
    df = _calculate_dip(df)
    df = _calculate_azimuth(df)
    df = _apply_measurement_units(df)
    df = df.rename(columns=CAMEL_TO_SNAKE)

    return df


def _calculate_dip(df: pd.DataFrame) -> pd.DataFrame:
    """Create dip column from inclinationResultant.

    Inclination resultant is degrees of deviation from vertical, dip requires degrees from horizontal.

    :param df: Polars dataframe with possible inclination column.

    :return: Polars dataframe with new "dip" column, or the original.
    """
    if "inclinationResultant" not in df.columns:
        df["dip"] = 90.0
    else:
        df["dip"] = 90 - df["inclinationResultant"]
    return df


def _calculate_azimuth(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate azimuth from N-S/E-W inclination components.

    Adds an 'azimuth' column if inclinationNS and inclinationEW exist.

    :param df: Polars dataframe with possible directional data.

    :return: Polars dataframe with new "azimuth" column, or the original.
    """
    has_ns = "inclinationNS" in df.columns
    has_ew = "inclinationEW" in df.columns

    if not (has_ns and has_ew):
        df["azimuth"] = 0.0
        return df

    ns = df["inclinationNS"]
    ew = df["inclinationEW"]

    # Calculate azimuth and normalise to 0-360°
    # Note: atan2(ew, ns) gives angle clockwise from north
    azimuth = (np.degrees(np.arctan2(ew, ns)) + 360) % 360

    # Default to 0
    azimuth[azimuth.isna()] = 0.0

    df["azimuth"] = azimuth
    return df


def _apply_measurement_units(cpt_df: pd.DataFrame) -> pd.DataFrame:
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
    for col in cpt_df.columns:
        if col in MEASUREMENT_UNITS and MEASUREMENT_UNITS[col] != "":
            gef_unit = MEASUREMENT_UNITS[col]
            cpt_df[col] = cpt_df[col].astype(f"pint[{gef_unit}]")
            if gef_unit in MEASUREMENT_UNIT_CONVERSIONS:
                cpt_df[col] = cpt_df[col].pint.to(MEASUREMENT_UNIT_CONVERSIONS[gef_unit])

    return cpt_df


def _apply_nan_mapping(df: pd.DataFrame, cpt: ParsedCptFile) -> pd.DataFrame:
    """pd.DataFrame with NaN sentinels -> pd.DataFrame with NaNs"""
    if cpt.data.column_void_mapping is None:
        return df
    for col, sentinel in cpt.data.column_void_mapping.items():
        if col in df.columns:
            df[col] = df[col].mask(df[col] == sentinel)
    return df


def build_downhole_collection(
    cpts: list[ProcessedCPT],
    name: str | None = None,
    tags: dict[str, typing.Any] = None,
) -> DownholeCollectionData:
    """Create a DownholeCollection from parsed GEF CPT files.

    :param cpts: CPTs parsed from pygef
    :param name: (Optional) custom name - will be generated from hole_ids if None
    :param tags:

    :return: DownholeCollectionData

    :raises ValueError: If required data is missing/malformed
    """
    if not cpts:
        raise ValueError("No CPT data provided")

    if name is None:
        name = _generate_collection_name(cpts)

    hole_properties = _build_hole_properties(cpts)
    attributes = _build_attributes(cpts)
    hole_descriptions = _build_hole_descriptions(cpts)
    _combined_table = _combine_cpt_tables(cpts)
    paths = _build_paths(_combined_table)
    collections = _build_collections(_combined_table, hole_descriptions)
    crs = _get_crs(cpts)

    return DownholeCollectionData(
        name=name,
        tags=tags,
        coordinate_reference_system=crs,
        path=paths,
        collections=collections,
        holes=hole_descriptions,
        properties=hole_properties,
        attributes=attributes,
    )


def _generate_collection_name(cpts: list[ProcessedCPT]) -> str:
    """Generate a collection name from collar data.

    :return: Collection name
    """
    hole_ids = [cpt.hole_id for cpt in cpts]
    if not hole_ids:
        return ""
    elif len(hole_ids) == 1:
        return f"GEF CPT {hole_ids[0]}"
    else:
        return f"GEF CPT {len(hole_ids)} holes {hole_ids[0]}...{hole_ids[-1]}"


def _build_hole_properties(cpts: list[ProcessedCPT]) -> pd.DataFrame:
    rows = [{"hole_id": cpt.hole_id, **cpt.location.xyz_dict(), **dataclasses.asdict(cpt.distances)} for cpt in cpts]
    df = pd.DataFrame(rows)
    return df.astype(HOLE_PROPERTIES_DTYPES)


def _build_attributes(cpts: list[ProcessedCPT]) -> pd.DataFrame:
    rows = []
    for cpt in cpts:
        row = {}
        if cpt.project_id is not None:
            row["project_id"] = cpt.project_id
        if cpt.delivered_location is not None:
            loc = cpt.delivered_location
            row |= {"delivered_x": loc.x, "delivered_y": loc.y, "delivered_crs": loc.crs}
        row |= cpt.hole_attributes
        rows.append(row)
    df = pd.DataFrame(rows)

    for col in df.columns:
        series = df[col]
        # Columns could have NA if the different rows have differing fields. Update integer and string columns to be
        # compatible with the schema and future processing.
        if series.isna().any():
            inferred_type: str = pd.api.types.infer_dtype(series, skipna=True)
            if inferred_type == "integer":
                df[col] = series.astype("Int64")
            elif inferred_type == "string":
                df[col] = series.astype("string")

    return df


def _build_hole_descriptions(cpts: list[ProcessedCPT]) -> pd.DataFrame:
    hole_sizes = {
        'hole_index': [],
        'offset': [],
        'count': [],
    }
    begin = 0
    for i, cpt in enumerate(cpts):
        count = len(cpt.cpt_table)

        hole_sizes['hole_index'].append(i)
        hole_sizes['offset'].append(begin)
        hole_sizes['count'].append(count)

        begin += count

    return pd.DataFrame(hole_sizes).astype({
        "hole_index": np.int32, "offset": np.uint64, "count": np.uint64,
    })


def _convert_from_pint_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        series = df[col]
        if isinstance(series.dtype, PintType):
            unit = UnitMapper.lookup(series.dtype)
            if unit is not None:
                df.attrs.setdefault("attribute_descriptions", {})[col] = AttributeDescription(unit=unit)
            df[col] = series.pint.magnitude
    return df


def _combine_cpt_tables(cpts: list[ProcessedCPT]) -> pd.DataFrame:
    cpt_tables = [cpt.cpt_table for cpt in cpts]
    combined_table = pd.concat(cpt_tables, ignore_index=True)
    combined_table = combined_table.rename(columns={"penetration_length": "distance"})
    return _convert_from_pint_columns(combined_table)


def _build_paths(combined_table: pd.DataFrame) -> pd.DataFrame:
    path_attr_columns = ["distance"] + [col for col in combined_table.columns if col in  PATH_ATTRIBUTES]
    paths_df = combined_table[path_attr_columns]
    return paths_df


def _build_collections(combined_table: pd.DataFrame, holes: pd.DataFrame) -> list[DistanceCollection]:
    distance_collection_attrs = [col for col in combined_table.columns if col not in PATH_ATTRIBUTES]
    distance_collection_df = combined_table[distance_collection_attrs]
    dc = DistanceCollection(
        name="cpt",
        holes=holes,
        distance_table=distance_collection_df,
    )
    return [dc]


def _get_crs(cpts: list[ProcessedCPT]) -> SchemaCrsCode:
    for cpt in cpts:
        if cpt.location.crs != UNSPECIFIED:
            return cpt.location.crs
    return UNSPECIFIED
