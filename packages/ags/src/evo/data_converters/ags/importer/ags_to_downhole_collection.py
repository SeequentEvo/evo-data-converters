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

import numpy as np
import pandas as pd
from pyproj import CRS

import evo.logging
from evo.data_converters.ags.common import AgsContext, AgsFileInvalidException
from evo.data_converters.ags.common.ags_context import GEOL, HORN, LOCA, SCPG, SCPT, CoordinateFamily
from evo.objects.typed import DistanceCollection, DownholeCollectionData, EpsgCode, IntervalCollection

logger = evo.logging.getLogger("data_converters")

# Orientation of a vertical hole, used where the AGS file gives none
DEFAULT_DIP = 90.0
DEFAULT_AZIMUTH = 0.0

DISTANCE_UNIT = "m"

# Standard collar columns, the other columns of the collars are kept as attributes
COLLAR_COLUMNS = ["hole_index", "hole_id", "x", "y", "z", "final_depth"]
STATION_DTYPES = {"hole_index": "int64", "distance": "float64", "dip": "float64", "azimuth": "float64"}


def create_from_parsed_ags(
    ags_context: AgsContext,
    tags: dict[str, str] | None = None,
) -> DownholeCollectionData:
    """Converts the in-memory dataframes of AgsContext to the data of an Evo Downhole Collection.

    Collars are built from both SCPG and GEOL tables:
    - SCPG collars are uniquely identified by (LOCA_ID, SCPG_TESN)
    - GEOL collars are uniquely identified by LOCA_ID only

    Every measurement group with data (SCPT, SCPP, GEOL) becomes a collection named after the group, with its rows
    linked to the collars by hole_index. SCPT is a distance collection, SCPP and GEOL are interval collections.

    The hole paths are made of the measured depths of the first distance table (SCPT), with the dip and azimuth of
    the HORN table when present, otherwise the holes are vertical. A hole without measured depths, such as one that
    only has GEOL data, gets a single vertical station at its final depth, or no station when that is unknown.

    :param ags_context: The context containing the AGS file as dataframes.
    :param tags: Optional dict of tags to add to the DownholeCollection.
    :return: The data of the DownholeCollection, to create in Evo with DownholeCollection.create.
    """

    crs_definition = ags_context.coordinate_reference_system
    collars_df = build_collars(ags_context, crs_definition)

    collections: list[DistanceCollection | IntervalCollection] = []
    stations: pd.DataFrame | None = None
    for group in AgsContext.MEASUREMENT_GROUPS:
        if group in AgsContext.DISTANCE_COLUMNS:
            depth_columns = {"distance": AgsContext.DISTANCE_COLUMNS[group]}
        else:
            from_column, to_column = AgsContext.INTERVAL_COLUMNS[group]
            depth_columns = {"from": from_column, "to": to_column}

        measurements = prepare_measurements(ags_context.get_table(group), group, depth_columns, collars_df)
        if measurements is None:
            continue

        collection_class = DistanceCollection if "distance" in depth_columns else IntervalCollection
        collections.append(
            collection_class(
                name=group,
                holes=hole_chunks(measurements["hole_index"]),
                table=collection_table(measurements, group, depth_columns),
                unit=DISTANCE_UNIT,
            )
        )

        # Only the first distance table is used when building the hole path geometry
        if stations is None and "distance" in depth_columns:
            stations = path_stations(measurements, depth_columns["distance"], ags_context.get_table(HORN))

    path, holes = build_path(collars_df, stations)

    properties = collars_df[["hole_index", "hole_id", "x", "y", "z"]].copy()
    properties["hole_id"] = properties["hole_id"].astype(str)
    properties["final"] = properties["target"] = properties["current"] = collars_df["final_depth"]

    collar_attributes = attribute_frame(collars_df.drop(columns=COLLAR_COLUMNS), "collars")

    return DownholeCollectionData(
        name=ags_context.filename,
        tags=tags,
        coordinate_reference_system=to_evo_crs(crs_definition),
        path=path,
        holes=holes,
        properties=properties,
        attributes=None if collar_attributes.empty else collar_attributes,
        collections=collections,
        distance_unit=DISTANCE_UNIT,
        desurvey=None,
    )


def to_evo_crs(crs_definition: int | str | None) -> EpsgCode | str | None:
    """Convert the coordinate reference system of an AGS file to the form used by a Downhole Collection.

    :param crs_definition: An EPSG code, "unspecified" or None when the AGS file has no coordinate reference system.
    :return: The EPSG code, or None when unspecified. A CRS given as a string without an EPSG code is returned as WKT.
    """
    if crs_definition is None or crs_definition == "unspecified":
        return None
    if isinstance(crs_definition, int):
        return EpsgCode(crs_definition)

    crs = CRS.from_user_input(crs_definition)
    epsg_code = crs.to_epsg()
    return EpsgCode(epsg_code) if epsg_code is not None else crs.to_wkt()


def prepare_measurements(
    table: pd.DataFrame,
    group: str,
    depth_columns: dict[str, str],
    collars_df: pd.DataFrame,
) -> pd.DataFrame | None:
    """Link the rows of a measurement table to their collars and order them by hole and depth.

    Tables with SCPG_TESN are matched to the collars on LOCA_ID and SCPG_TESN, location-level tables (e.g. GEOL) on
    LOCA_ID only. Rows without a matching collar are dropped. The table itself is left unchanged.

    :param table: The measurement table of an AGS group.
    :param group: The AGS group of the table.
    :param depth_columns: The depth columns of the group, keyed by the name they have in the Downhole Collection.
    :param collars_df: The collars, with their hole_index.
    :return: A copy of the table with a hole_index column and float depth columns, sorted by hole_index and the first
        depth column. None when there are no rows to convert.
    """
    if table.empty:
        logger.debug(f"AGS group {group} has no rows, skipping")
        return None

    missing_columns = [column for column in depth_columns.values() if column not in table.columns]
    if missing_columns:
        logger.warning(f"Skipping AGS group {group}, it has no {', '.join(missing_columns)} column")
        return None

    keys = ["LOCA_ID", "SCPG_TESN"] if "SCPG_TESN" in table.columns else ["LOCA_ID"]
    lookup = collars_df[[*keys, "hole_index"]].drop_duplicates(subset=keys, keep="first")
    measurements = table.merge(lookup, on=keys, how="left")

    unmatched = measurements["hole_index"].isna()
    if unmatched.any():
        logger.warning(f"Dropping {unmatched.sum()} rows with unmatched LOCA_ID in measurement table {group}")
        measurements = measurements[~unmatched]
        if measurements.empty:
            return None

    depths = {
        column: pd.to_numeric(measurements[column], errors="coerce").astype("float64")
        for column in depth_columns.values()
    }
    first_depth_column = next(iter(depths))
    return (
        measurements.assign(hole_index=measurements["hole_index"].astype("int64"), **depths)
        .sort_values(["hole_index", first_depth_column])
        .reset_index(drop=True)
    )


def collection_table(measurements: pd.DataFrame, group: str, depth_columns: dict[str, str]) -> pd.DataFrame:
    """Build the table of a collection from prepared measurements.

    The depth columns come first, named as the Downhole Collection expects them. All the other columns, including the
    LOCA_ID and SCPG_TESN keys, follow as attributes.

    :param measurements: The measurements of an AGS group, from prepare_measurements.
    :param group: The AGS group of the measurements.
    :param depth_columns: The depth columns of the group, keyed by the name they have in the Downhole Collection.
    """
    evo_names = {column: name for name, column in depth_columns.items()}
    depths = measurements[list(evo_names)].rename(columns=evo_names)
    attributes = attribute_frame(measurements.drop(columns=["hole_index", *evo_names]), group)
    return pd.concat([depths, attributes], axis=1)


def hole_chunks(hole_index: pd.Series, holes: pd.Series | None = None) -> pd.DataFrame:
    """Locate the rows of each hole in a table that is sorted by hole_index.

    :param hole_index: The hole_index of each row of the table.
    :param holes: When given, every one of these holes gets a chunk, with a count of zero when it has no rows.
        Otherwise only the holes with rows do.
    :return: The hole_index, offset and count of each chunk, with the data types of the Downhole Collection tables.
    """
    counts = hole_index.value_counts()
    if holes is not None:
        counts = counts.reindex(holes.to_numpy(), fill_value=0)
    counts = counts.sort_index()

    return pd.DataFrame(
        {
            "hole_index": counts.index.to_numpy(dtype="int32"),
            "offset": (counts.cumsum() - counts).to_numpy(dtype="uint64"),
            "count": counts.to_numpy(dtype="uint64"),
        }
    )


def path_stations(measurements: pd.DataFrame, depth_column: str, horn_df: pd.DataFrame) -> pd.DataFrame:
    """Build the path stations of the holes from the measured depths of a distance table.

    Dip and azimuth come from the HORN table when it has data, otherwise the holes are vertical.

    :param measurements: The measurements of a distance group, from prepare_measurements.
    :param depth_column: The depth column of the measurements.
    :param horn_df: The HORN table, empty when the AGS file has none.
    :return: The hole_index, distance, dip and azimuth of each station, ordered by hole and distance.
    """
    stations = (
        measurements[["hole_index", "LOCA_ID", depth_column]].dropna(subset=[depth_column]).reset_index(drop=True)
    )

    if horn_df.empty:
        stations["dip"] = DEFAULT_DIP
        stations["azimuth"] = DEFAULT_AZIMUTH
    else:
        calculate_dip_and_azimuth(horn_df, stations, depth_column)
        stations["dip"] = stations["dip"].fillna(DEFAULT_DIP)
        stations["azimuth"] = stations["azimuth"].fillna(DEFAULT_AZIMUTH)

    return stations.rename(columns={depth_column: "distance"})[list(STATION_DTYPES)]


def build_path(collars_df: pd.DataFrame, stations: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the path of the Downhole Collection and the chunks locating the stations of every hole in it.

    A hole without stations gets a single vertical station at its final depth, or no station when that is unknown.

    :param collars_df: The collars, with their hole_index and final_depth.
    :param stations: The stations of the holes with measured depths, from path_stations. None when there are none.
    :return: The path, with distance, dip and azimuth columns, and the chunks of all the holes.
    """
    if stations is None:
        stations = pd.DataFrame({column: pd.Series(dtype=dtype) for column, dtype in STATION_DTYPES.items()})

    final_depth = collars_df["final_depth"]
    needs_station = (
        ~collars_df["hole_index"].isin(stations["hole_index"]) & np.isfinite(final_depth) & (final_depth > 0)
    )
    vertical_stations = pd.DataFrame(
        {
            "hole_index": collars_df.loc[needs_station, "hole_index"],
            "distance": final_depth[needs_station],
            "dip": DEFAULT_DIP,
            "azimuth": DEFAULT_AZIMUTH,
        }
    )

    path = pd.concat([stations, vertical_stations], ignore_index=True).astype(STATION_DTYPES)
    path = path.sort_values("hole_index", kind="stable").reset_index(drop=True)
    return path[["distance", "dip", "azimuth"]], hole_chunks(path["hole_index"], collars_df["hole_index"])


def attribute_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Convert the columns of a dataframe to data types that can be uploaded as attributes.

    Columns that cannot be represented as an attribute are dropped, with a warning when they hold unsupported data.

    :param df: The dataframe with the attribute columns.
    :param source: What the columns belong to, for log messages.
    """
    columns = {}
    for name in df.columns:
        series = attribute_series(df[name], source)
        if series is not None:
            columns[name] = series
    return pd.DataFrame(columns, index=df.index)


def attribute_series(series: pd.Series, source: str) -> pd.Series | None:
    """Convert a column to a data type that can be uploaded as an attribute.

    The data type is inferred from the values, ignoring missing ones, since AGS columns are often of object dtype
    holding values and pd.NA. Integers, floats, booleans, strings and datetimes are supported.

    :param series: The column to convert.
    :param source: What the column belongs to, for log messages.
    :return: The converted column, or None if it has no values or they are of an unsupported type.
    """
    kind = pd.api.types.infer_dtype(series, skipna=True)

    if kind == "integer":
        return series.astype("Int64")
    if kind in ("floating", "mixed-integer-float", "decimal"):
        return pd.to_numeric(series, errors="coerce").astype("float64")
    if kind == "boolean":
        return series.astype("boolean")
    if kind == "string":
        return series.astype("string")
    if kind in ("datetime64", "datetime", "date"):
        return pd.to_datetime(series, errors="coerce")

    if kind == "empty":
        logger.debug(f"Skipping attribute {series.name!r} of {source}, it has no values")
    else:
        logger.warning(f"Skipping attribute {series.name!r} of {source}, unsupported data type {kind!r}")
    return None


def build_scpg_collars(ags_context: AgsContext) -> pd.DataFrame:
    """Builds collars from SCPG data.

    SCPG collars are uniquely identified by (LOCA_ID, SCPG_TESN).
    Final depth is calculated from SCPT_DPTH.

    :param ags_context: The context containing the AGS file as dataframes.
    :return: DataFrame of SCPG collars, or empty DataFrame if no SCPG data
    """
    loca_df: pd.DataFrame = ags_context.get_table(LOCA)
    scpg_df: pd.DataFrame = ags_context.get_table(SCPG)
    scpt_df: pd.DataFrame = ags_context.get_table(SCPT)

    if scpg_df.empty:
        return pd.DataFrame()

    scpg_collars = scpg_df.copy().merge(loca_df, on="LOCA_ID", how="left")

    # Compute final depth per (LOCA_ID, SCPG_TESN) from SCPT
    if not scpt_df.empty:
        final_depths = scpt_df.groupby(["LOCA_ID", "SCPG_TESN"], dropna=False)["SCPT_DPTH"].max().reset_index()
        final_depths = final_depths.rename(columns={"SCPT_DPTH": "final_depth"})
        scpg_collars = scpg_collars.merge(final_depths, on=["LOCA_ID", "SCPG_TESN"], how="left")

    # Create hole_id as composite of LOCA_ID and SCPG_TESN
    loca_str = scpg_collars["LOCA_ID"].astype(str)
    tesn_str = scpg_collars["SCPG_TESN"].fillna("").astype(str)
    scpg_collars["hole_id"] = np.where(tesn_str != "", loca_str + ":" + tesn_str, loca_str)

    if not scpg_collars["hole_id"].is_unique:
        logger.warning("Duplicate hold IDs found, based on on LOCA_ID and SCPG_TESN")

    return scpg_collars


def build_geol_collars(ags_context: AgsContext) -> pd.DataFrame:
    """Builds collars from GEOL data.

    GEOL collars are uniquely identified by LOCA_ID only.
    Final depth is calculated from GEOL_BASE.

    :param ags_context: The context containing the AGS file as dataframes.
    :return: DataFrame of GEOL collars, or empty DataFrame if no GEOL data
    """
    loca_df: pd.DataFrame = ags_context.get_table(LOCA)
    geol_df: pd.DataFrame = ags_context.get_table(GEOL)

    if geol_df.empty:
        return pd.DataFrame()

    # Get unique LOCA_IDs from GEOL
    geol_loca_ids = geol_df["LOCA_ID"].unique()
    geol_collars = loca_df[loca_df["LOCA_ID"].isin(geol_loca_ids)].copy()

    # Compute final depth per LOCA_ID from GEOL_BASE
    if "GEOL_BASE" in geol_df.columns:
        final_depths = geol_df.groupby("LOCA_ID", dropna=False)["GEOL_BASE"].max().reset_index()
        final_depths = final_depths.rename(columns={"GEOL_BASE": "final_depth"})
        geol_collars = geol_collars.merge(final_depths, on="LOCA_ID", how="left")

    # Create hole_id from LOCA_ID only (no SCPG_TESN for GEOL)
    geol_collars["hole_id"] = geol_collars["LOCA_ID"].astype(str)
    geol_collars["SCPG_TESN"] = pd.NA

    return geol_collars


def build_collars(ags_context: AgsContext, crs_definition: int | str | None) -> pd.DataFrame:
    """Builds the collars from the AGS context.

    Collars are built from both SCPG and GEOL tables:
    - SCPG collars are uniquely identified by (LOCA_ID, SCPG_TESN)
    - GEOL collars are uniquely identified by LOCA_ID only

    If a LOCA_ID appears in both SCPG and GEOL, both collar types are created,
    but a warning is logged.

    :param ags_context: The context containing the AGS file as dataframes.
    :param crs_definition: The coordinate reference system shared by the LOCA rows.
    :return: A DataFrame with a row per collar. The standard columns (hole_index, hole_id, x, y, z, final_depth) come
        first, followed by the LOCA_ID and SCPG_TESN keys and the other LOCA and SCPG columns.
    """
    scpg_collars = build_scpg_collars(ags_context)
    geol_collars = build_geol_collars(ags_context)

    # Check for duplicate LOCA_IDs between SCPG and GEOL
    if not scpg_collars.empty and not geol_collars.empty:
        scpg_loca_ids = set(scpg_collars["LOCA_ID"].unique())
        geol_loca_ids = set(geol_collars["LOCA_ID"].unique())
        duplicates = scpg_loca_ids & geol_loca_ids
        if duplicates:
            logger.warning(
                f"Found {len(duplicates)} LOCA_IDs present in both SCPG and GEOL tables. "
                f"Creating collars for both types. LOCA_IDs: {list(duplicates)}"
            )

    # Combine dataframes and set hole_index
    collars_df = pd.concat([scpg_collars, geol_collars], ignore_index=True)
    collars_df["hole_index"] = range(1, len(collars_df) + 1)

    assign_coordinates(collars_df, crs_definition)

    # Ensure final_depth is float dtype even if NaN
    collars_df["final_depth"] = pd.to_numeric(collars_df["final_depth"], errors="coerce").astype(float)

    # Reorder columns to standard first but retain useful keys
    key_cols = ["LOCA_ID", "SCPG_TESN"]
    other_cols = [c for c in collars_df.columns if c not in COLLAR_COLUMNS + key_cols]
    collars_df = collars_df[COLLAR_COLUMNS + key_cols + other_cols]

    duplicates_count = len(collars_df) - collars_df["hole_id"].nunique()
    if duplicates_count > 0:
        logger.error(
            f"Dropping {duplicates_count} duplicate collar entries with the same hole_id, keeping first occurrence"
        )
        collars_df = collars_df.drop_duplicates(subset=["hole_id"], keep="first").reset_index(drop=True)

    return collars_df


def assign_coordinates(collars_df: pd.DataFrame, crs_definition: int | str | None) -> None:
    """Assign coordinates and elevation from the same spatial coordinate family."""
    if crs_definition is None:
        logger.warning("CRS is unavailable; coordinate column family cannot be verified.")
        family = assign_unspecified_coordinates(collars_df)
    elif crs_definition == "unspecified":
        logger.warning("CRS is local or unspecified; using the local coordinate family.")
        family = assign_family_coordinates(collars_df, "local", "local reference", require_complete=True)
    else:
        family = assign_horizontal_coordinates(collars_df, crs_definition)

    assign_elevations(collars_df, family)
    assign_vertical_datum(collars_df, family)


def assign_unspecified_coordinates(collars_df: pd.DataFrame) -> CoordinateFamily:
    """Choose one coordinate family for the table when no CRS is declared."""
    local_reference = collars_df.get("LOCA_LREF")
    if local_reference is not None and local_reference.fillna("").astype(str).str.strip().ne("").any():
        return assign_family_coordinates(collars_df, "local", "LOCA_LREF", require_complete=True)

    for family in AgsContext.UNSPECIFIED_COORDINATE_FAMILY_PRIORITY:
        if has_complete_coordinates(collars_df, family):
            return assign_family_coordinates(collars_df, family, "unspecified CRS", require_complete=False)

    collars_df[["x", "y"]] = 0.0
    logger.warning("No valid x coordinate data found in LOCA table, defaulting to 0.0")
    logger.warning("No valid y coordinate data found in LOCA table, defaulting to 0.0")
    return "national"


def numeric_column(collars_df: pd.DataFrame, column: str) -> pd.Series:
    """Return a column as floats, with NaN where the column or its values are missing."""
    if column not in collars_df:
        return pd.Series(np.nan, index=collars_df.index, dtype=float)
    return pd.to_numeric(collars_df[column], errors="coerce").astype(float)


def family_coordinates(collars_df: pd.DataFrame, family: CoordinateFamily) -> tuple[pd.Series, pd.Series]:
    """Return the numeric x and y columns of a coordinate family."""
    x_column, y_column = AgsContext.COORDINATE_COLUMNS_BY_FAMILY[family]
    return numeric_column(collars_df, x_column), numeric_column(collars_df, y_column)


def has_complete_coordinates(collars_df: pd.DataFrame, family: CoordinateFamily) -> bool:
    """Return whether a coordinate family contains at least one complete numeric row."""
    x, y = family_coordinates(collars_df, family)
    return bool((x.notna() & y.notna()).any())


def assign_family_coordinates(
    collars_df: pd.DataFrame,
    family: CoordinateFamily,
    reference: str,
    require_complete: bool,
) -> CoordinateFamily:
    """Assign x and y from one coordinate family, without mixing coordinate references."""
    collars_df["x"], collars_df["y"] = family_coordinates(collars_df, family)

    missing = collars_df["x"].isna() | collars_df["y"].isna()
    if missing.any():
        holes = collars_df.loc[missing, "hole_id"].tolist()
        if require_complete:
            raise AgsFileInvalidException(
                f"No complete {family} coordinate pair for {reference} in LOCA table for holes: {holes}."
            )
        logger.warning(f"No complete {family} coordinate pair for holes: {holes}, defaulting x and y to 0.0")
        collars_df.loc[missing, ["x", "y"]] = 0.0
    return family


def assign_elevations(collars_df: pd.DataFrame, family: CoordinateFamily) -> None:
    """Assign the elevation field associated with the selected coordinate family."""
    column = AgsContext.ELEVATION_COLUMN_BY_FAMILY[family]
    elevation = numeric_column(collars_df, column)

    missing = elevation.isna()
    if missing.any():
        holes = collars_df.loc[missing, "hole_id"].tolist()
        logger.warning(f"No valid z coordinate data found in {column} for holes: {holes}, defaulting to 0.0")
    collars_df["z"] = elevation.fillna(0.0)


def assign_vertical_datum(collars_df: pd.DataFrame, family: CoordinateFamily) -> None:
    """Preserve LOCA_DATM and warn when LOCA_GL has no declared vertical datum."""
    datum = collars_df.get("LOCA_DATM", pd.Series(pd.NA, index=collars_df.index))
    datum = datum.astype("string").str.strip()
    missing = datum.isna() | datum.eq("")

    if AgsContext.ELEVATION_COLUMN_BY_FAMILY[family] == "LOCA_GL" and missing.any():
        holes = collars_df.loc[missing, "hole_id"].tolist()
        logger.warning(f"LOCA_GL used without a declared vertical datum (LOCA_DATM) for holes: {holes}")

    collars_df["LOCA_DATM"] = datum.mask(missing, "undeclared")


def assign_horizontal_coordinates(collars_df: pd.DataFrame, crs_definition: int | str) -> CoordinateFamily:
    """Select the coordinate family matching a projected or geographic CRS and assign x and y."""
    crs = CRS.from_user_input(crs_definition)
    family: CoordinateFamily
    if crs.is_projected:
        family = "national"
    elif crs.is_geographic:
        family = "geographic"
    else:
        raise AgsFileInvalidException(f"CRS {crs_definition} is neither projected nor geographic.")

    return assign_family_coordinates(collars_df, family, f"CRS {crs_definition}", require_complete=True)


def calculate_dip_and_azimuth(
    horn_df: pd.DataFrame,
    measurements_df: pd.DataFrame,
    depth_column: str,
) -> None:
    """Add dip and azimuth columns from HORN table (vectorized).

    Matches each measurement to a HORN interval where HORN_TOP <= depth < HORN_BASE.
    Measurements outside all intervals for their LOCA_ID get vertical defaults (90°/0°).
    The columns are added to measurements_df, which must have LOCA_ID and the depth column.
    """
    n_rows = len(measurements_df)

    # Initialize results with defaults
    dip_result = np.full(n_rows, DEFAULT_DIP, dtype="float64")
    azimuth_result = np.full(n_rows, DEFAULT_AZIMUTH, dtype="float64")

    # Create working copy with original index tracking
    work_df = measurements_df[["LOCA_ID", depth_column]].copy()
    work_df[depth_column] = pd.to_numeric(work_df[depth_column], errors="coerce").astype("float64")
    work_df["_orig_idx"] = np.arange(n_rows)

    # merge_asof needs keys of the same type on both sides
    horn_df = horn_df.assign(
        HORN_TOP=pd.to_numeric(horn_df["HORN_TOP"], errors="coerce").astype("float64"),
        HORN_BASE=pd.to_numeric(horn_df["HORN_BASE"], errors="coerce").astype("float64"),
    )

    # Pre-sort HORN intervals by LOCA_ID
    horn_by_loca = {loca_id: group.sort_values("HORN_TOP") for loca_id, group in horn_df.groupby("LOCA_ID")}

    unmatched_count = 0

    for loca_id, m_group in work_df.groupby("LOCA_ID"):
        horn_group = horn_by_loca.get(loca_id)

        if horn_group is None:
            unmatched_count += len(m_group)
            continue

        m_sorted = m_group.sort_values(depth_column)

        merged = pd.merge_asof(
            m_sorted[[depth_column, "_orig_idx"]],
            horn_group[["HORN_TOP", "HORN_BASE", "HORN_INCL", "HORN_ORNT"]],
            left_on=depth_column,
            right_on="HORN_TOP",
            direction="backward",
        )

        # Match is valid only if depth falls within the interval
        in_interval = (merged["HORN_BASE"].notna()) & (merged[depth_column] < merged["HORN_BASE"])

        orig_idx = merged["_orig_idx"].values
        dip_result[orig_idx] = np.where(in_interval, merged["HORN_INCL"], DEFAULT_DIP)
        azimuth_result[orig_idx] = np.where(in_interval, merged["HORN_ORNT"], DEFAULT_AZIMUTH)

        unmatched_count += (~in_interval).sum()

    if unmatched_count > 0:
        logger.info(f"{unmatched_count} depth measurements outside HORN intervals, assuming vertical")

    measurements_df["dip"] = pd.Series(dip_result, index=measurements_df.index, dtype="float64")
    measurements_df["azimuth"] = pd.Series(azimuth_result, index=measurements_df.index, dtype="float64")
