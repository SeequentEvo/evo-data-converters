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

    Each location gets a single collar, identified by its LOCA_ID, which is also its hole_id. The collar is shared by
    all the groups holding data of the location, such as SCPG and GEOL.

    Multiple CPT pushes per location are not supported. Only the first push of each LOCA_ID in the SCPG table is
    imported, and the rows of the other pushes are excluded from all the groups keyed by SCPG_TESN, with a warning.

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
    scpg_df, skipped_pushes = select_first_pushes(ags_context.get_table(SCPG))
    tables = {
        group: exclude_pushes(ags_context.get_table(group), skipped_pushes, group)
        for group in AgsContext.MEASUREMENT_GROUPS
    }
    collars_df = build_collars(ags_context.get_table(LOCA), scpg_df, tables, crs_definition)

    collections: list[DistanceCollection | IntervalCollection] = []
    stations: pd.DataFrame | None = None
    for group in AgsContext.MEASUREMENT_GROUPS:
        if group in AgsContext.DISTANCE_COLUMNS:
            depth_columns = {"distance": AgsContext.DISTANCE_COLUMNS[group]}
        else:
            from_column, to_column = AgsContext.INTERVAL_COLUMNS[group]
            depth_columns = {"from": from_column, "to": to_column}

        measurements = prepare_measurements(tables[group], group, depth_columns, collars_df)
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

    Tables with SCPG_TESN are matched to the collars on LOCA_ID and the SCPG_TESN of the imported push, so that rows of
    other pushes are never linked to a collar. Rows without a SCPG_TESN are never linked to a collar without a push,
    such as a GEOL-only one. Location-level tables (e.g. GEOL) are matched on LOCA_ID only. Rows without a matching
    collar are dropped. The table itself is left unchanged.

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
    # pandas matches missing keys to each other, so collars without a key value would match rows without one
    lookup = collars_df[[*keys, "hole_index"]].dropna(subset=keys).drop_duplicates(subset=keys, keep="first")
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


def select_first_pushes(scpg_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select the CPT push to import for each location.

    Multiple CPT pushes per location are not supported. Only the first push of each LOCA_ID in the order of the AGS
    data is imported. The SCPG_TESN values are not sorted, as they need not be numeric. A warning names the pushes of
    each location that are not imported.

    :param scpg_df: The SCPG table.
    :return: The SCPG rows of the imported pushes, one per LOCA_ID in the order of the AGS data, and the LOCA_ID and
        SCPG_TESN of the pushes that are not imported.
    """
    keys = ["LOCA_ID", "SCPG_TESN"]
    if scpg_df.empty or not set(keys).issubset(scpg_df.columns):
        return scpg_df.copy(), pd.DataFrame(columns=keys)

    imported = scpg_df[~scpg_df.duplicated(subset="LOCA_ID", keep="first")].reset_index(drop=True)

    pushes = scpg_df[keys].drop_duplicates()
    skipped = pushes[pushes.duplicated(subset="LOCA_ID", keep="first")].reset_index(drop=True)

    imported_tesn = dict(zip(imported["LOCA_ID"], imported["SCPG_TESN"]))
    for loca_id, skipped_tesn in skipped.groupby("LOCA_ID", sort=False)["SCPG_TESN"]:
        if len(skipped_tesn) == 1:
            not_imported = f"Push {quoted_list(skipped_tesn)} was"
        else:
            not_imported = f"Pushes {quoted_list(skipped_tesn)} were"
        logger.warning(
            f"Multiple CPT pushes found for LOCA_ID '{loca_id}'. "
            f"Only the first push ('{imported_tesn[loca_id]}') was imported. "
            f"{not_imported} not imported because multiple pushes per location are not currently supported."
        )

    return imported, skipped


def quoted_list(values: pd.Series) -> str:
    """Join values in quotes for a log message, e.g. "'2', '3' and '4'"."""
    quoted = [f"'{value}'" for value in values]
    if len(quoted) == 1:
        return quoted[0]
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"


def exclude_pushes(table: pd.DataFrame, pushes: pd.DataFrame, group: str) -> pd.DataFrame:
    """Remove the rows of the given CPT pushes from a table keyed by SCPG_TESN.

    This keeps the data of the pushes that are not imported out of every CPT group, such as SCPT and SCPP, so it is
    never merged with the data of the imported push. Tables without SCPG_TESN, such as GEOL, are returned unchanged.
    The table itself is left unchanged.

    :param table: The table of an AGS group.
    :param pushes: The LOCA_ID and SCPG_TESN of the pushes to remove, from select_first_pushes.
    :param group: The AGS group of the table.
    :return: The rows of the table that do not belong to the pushes.
    """
    keys = ["LOCA_ID", "SCPG_TESN"]
    if pushes.empty or table.empty or not set(keys).issubset(table.columns):
        return table

    matches = table[keys].merge(pushes[keys].drop_duplicates(), on=keys, how="left", indicator=True)
    excluded = (matches["_merge"] == "both").to_numpy()
    if not excluded.any():
        return table

    logger.debug(f"Excluding {excluded.sum()} rows of CPT pushes that are not imported from AGS group {group}")
    return table[~excluded]


def final_depths(scpg_df: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> pd.Series:
    """Find the final depth of each location.

    :param scpg_df: The SCPG rows of the imported pushes, from select_first_pushes.
    :param tables: The measurement tables, keyed by AGS group.
    :return: The deepest SCPT_DPTH of the imported push or GEOL_BASE of each location, indexed by LOCA_ID.
    """
    keys = ["LOCA_ID", "SCPG_TESN"]
    depths = []

    scpt_df = tables.get(SCPT, pd.DataFrame())
    if set(keys).issubset(scpg_df.columns) and {*keys, "SCPT_DPTH"}.issubset(scpt_df.columns):
        imported_scpt = scpt_df[[*keys, "SCPT_DPTH"]].merge(scpg_df[keys].drop_duplicates(), on=keys)
        depths.append(imported_scpt[["LOCA_ID", "SCPT_DPTH"]].rename(columns={"SCPT_DPTH": "depth"}))

    geol_df = tables.get(GEOL, pd.DataFrame())
    if {"LOCA_ID", "GEOL_BASE"}.issubset(geol_df.columns):
        depths.append(geol_df[["LOCA_ID", "GEOL_BASE"]].rename(columns={"GEOL_BASE": "depth"}))

    depths = [df for df in depths if not df.empty]
    if not depths:
        return pd.Series(dtype="float64")

    combined = pd.concat(depths, ignore_index=True)
    return pd.to_numeric(combined["depth"], errors="coerce").groupby(combined["LOCA_ID"]).max()


def build_collars(
    loca_df: pd.DataFrame,
    scpg_df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    crs_definition: int | str | None,
) -> pd.DataFrame:
    """Builds the collars, one per location, with the LOCA_ID as hole_id.

    A location gets a collar when it has an imported CPT push in SCPG, or GEOL data and a LOCA row. The measurements
    of all its groups are linked to this collar through its hole_index. The collars of the CPT locations come first,
    in the order of the SCPG table, followed by the GEOL-only locations in the order of the LOCA table.

    The final depth of a collar is the deepest SCPT_DPTH of its imported push or GEOL_BASE of its location.

    :param loca_df: The LOCA table.
    :param scpg_df: The SCPG rows of the imported pushes, one per LOCA_ID, from select_first_pushes.
    :param tables: The measurement tables, keyed by AGS group, without the rows of the pushes that are not imported.
    :param crs_definition: The coordinate reference system shared by the LOCA rows.
    :return: A DataFrame with a row per collar. The standard columns (hole_index, hole_id, x, y, z, final_depth) come
        first, followed by the LOCA_ID and the SCPG_TESN of the imported push, and the other LOCA and SCPG columns.
    """
    collars = []
    cpt_loca_ids = pd.Series(dtype="object")
    if not scpg_df.empty and "LOCA_ID" in scpg_df.columns:
        collars.append(scpg_df.merge(loca_df, on="LOCA_ID", how="left"))
        cpt_loca_ids = scpg_df["LOCA_ID"]

    geol_df = tables.get(GEOL, pd.DataFrame())
    if "LOCA_ID" in geol_df.columns and "LOCA_ID" in loca_df.columns:
        geol_only = loca_df["LOCA_ID"].isin(geol_df["LOCA_ID"]) & ~loca_df["LOCA_ID"].isin(cpt_loca_ids)
        collars.append(loca_df[geol_only].assign(SCPG_TESN=pd.NA))

    collars = [df for df in collars if not df.empty]
    collars_df = pd.concat(collars, ignore_index=True) if collars else loca_df.iloc[0:0].copy()
    if "LOCA_ID" not in collars_df.columns:
        collars_df["LOCA_ID"] = pd.Series(dtype="object")
    if "SCPG_TESN" not in collars_df.columns:
        collars_df["SCPG_TESN"] = pd.Series(dtype="object")

    duplicates = collars_df["LOCA_ID"].duplicated(keep="first")
    if duplicates.any():
        logger.error(
            f"Dropping {duplicates.sum()} duplicate collar entries with the same LOCA_ID, keeping first occurrence"
        )
        collars_df = collars_df[~duplicates].reset_index(drop=True)

    collars_df["hole_index"] = range(1, len(collars_df) + 1)
    collars_df["hole_id"] = collars_df["LOCA_ID"].astype(str)
    collars_df["final_depth"] = collars_df["LOCA_ID"].map(final_depths(scpg_df, tables)).astype("float64")

    coordinate_families = assign_coordinates(collars_df, crs_definition)
    collars_df, coordinate_families = exclude_unlocated_collars(collars_df, coordinate_families)
    family = shared_coordinate_family(collars_df, coordinate_families)
    assign_elevations(collars_df, family)
    assign_vertical_datum(collars_df, family)

    key_cols = ["LOCA_ID", "SCPG_TESN"]
    other_cols = [c for c in collars_df.columns if c not in COLLAR_COLUMNS + key_cols]
    return collars_df[COLLAR_COLUMNS + key_cols + other_cols]


def assign_coordinates(collars_df: pd.DataFrame, crs_definition: int | str | None) -> pd.Series:
    """Assign each collar's coordinates from the family compatible with its CRS."""
    if crs_definition is None:
        logger.warning("CRS is unavailable; coordinate columns cannot be verified.")
        return assign_unspecified_coordinates(collars_df)
    elif crs_definition == "unspecified":
        logger.warning("CRS is local or unspecified; using local grid coordinates.")
        return assign_family_coordinates(collars_df, "local")
    else:
        return assign_horizontal_coordinates(collars_df, crs_definition)


def assign_unspecified_coordinates(collars_df: pd.DataFrame) -> pd.Series:
    """Choose the first complete coordinate family for each collar when no CRS is declared."""
    families = pd.Series(pd.NA, index=collars_df.index, dtype="object")
    x = pd.Series(np.nan, index=collars_df.index, dtype="float64")
    y = pd.Series(np.nan, index=collars_df.index, dtype="float64")

    local_reference = collars_df.get("LOCA_LREF")
    if local_reference is not None:
        local_rows = local_reference.fillna("").astype(str).str.strip().ne("")
        families.loc[local_rows] = "local"
        local_x, local_y = family_coordinates(collars_df, "local")
        x.loc[local_rows] = local_x.loc[local_rows]
        y.loc[local_rows] = local_y.loc[local_rows]

    for family in AgsContext.UNSPECIFIED_COORDINATE_FAMILY_PRIORITY:
        family_x, family_y = family_coordinates(collars_df, family)
        complete = np.isfinite(family_x) & np.isfinite(family_y)
        use_family = families.isna() & complete
        x.loc[use_family] = family_x.loc[use_family]
        y.loc[use_family] = family_y.loc[use_family]
        families.loc[use_family] = family

    collars_df["x"] = x
    collars_df["y"] = y
    return families


def exclude_unlocated_collars(collars_df: pd.DataFrame, families: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Drop the collars without finite x and y, renumber the rest, and fail when no collar is located."""
    located = np.isfinite(collars_df["x"]) & np.isfinite(collars_df["y"])
    if not located.all():
        holes = collars_df.loc[~located, "hole_id"].tolist()
        logger.warning(f"Excluding collars and measurements without complete finite coordinates for holes: {holes}")
    if not located.any():
        raise AgsFileInvalidException(
            "No holes have a complete finite coordinate pair in the LOCA table; "
            f"expected {expected_coordinate_columns(families)}."
        )

    collars_df = collars_df.loc[located].reset_index(drop=True)
    collars_df["hole_index"] = range(1, len(collars_df) + 1)
    return collars_df, families.loc[located].reset_index(drop=True)


def expected_coordinate_columns(families: pd.Series) -> str:
    """Describe the coordinate column pairs searched for the collars."""
    searched = families.unique() if families.notna().all() else AgsContext.UNSPECIFIED_COORDINATE_FAMILY_PRIORITY
    return " or ".join("/".join(AgsContext.COORDINATE_COLUMNS_BY_FAMILY[family]) for family in searched)


def shared_coordinate_family(collars_df: pd.DataFrame, families: pd.Series) -> CoordinateFamily:
    """Return the coordinate family of the located collars, rejecting families that no CRS can reconcile."""
    used_families = families.unique()
    if len(used_families) > 1:
        holes_by_family = {
            family: collars_df.loc[families.eq(family), "hole_id"].tolist() for family in used_families
        }
        raise AgsFileInvalidException(
            f"LOCA rows use different coordinate types without a shared CRS: {holes_by_family}."
        )
    family: CoordinateFamily = used_families[0]
    return family


def numeric_column(collars_df: pd.DataFrame, column: str) -> pd.Series:
    """Return a column as floats, with NaN where the column or its values are missing."""
    if column not in collars_df:
        return pd.Series(np.nan, index=collars_df.index, dtype=float)
    return pd.to_numeric(collars_df[column], errors="coerce").astype(float)


def family_coordinates(collars_df: pd.DataFrame, family: CoordinateFamily) -> tuple[pd.Series, pd.Series]:
    """Return the numeric x and y columns of a coordinate family."""
    x_column, y_column = AgsContext.COORDINATE_COLUMNS_BY_FAMILY[family]
    return numeric_column(collars_df, x_column), numeric_column(collars_df, y_column)


def assign_family_coordinates(collars_df: pd.DataFrame, family: CoordinateFamily) -> pd.Series:
    """Assign x and y from one coordinate family, without mixing coordinate references."""
    collars_df["x"], collars_df["y"] = family_coordinates(collars_df, family)
    return pd.Series(family, index=collars_df.index, dtype="object")


def assign_elevations(collars_df: pd.DataFrame, family: CoordinateFamily) -> None:
    """Assign the elevation field associated with the selected coordinate family."""
    column = AgsContext.ELEVATION_COLUMN_BY_FAMILY[family]
    elevation = numeric_column(collars_df, column)

    invalid = ~np.isfinite(elevation)
    if invalid.any():
        holes = collars_df.loc[invalid, "hole_id"].tolist()
        logger.warning(f"No valid z coordinate data found in {column} for holes: {holes}, defaulting to 0.0")
    collars_df["z"] = elevation.mask(invalid, 0.0)


def assign_vertical_datum(collars_df: pd.DataFrame, family: CoordinateFamily) -> None:
    """Preserve LOCA_DATM and warn when LOCA_GL has no declared vertical datum."""
    datum = collars_df.get("LOCA_DATM", pd.Series(pd.NA, index=collars_df.index))
    datum = datum.astype("string").str.strip()
    missing = datum.isna() | datum.eq("")

    if AgsContext.ELEVATION_COLUMN_BY_FAMILY[family] == "LOCA_GL" and missing.any():
        holes = collars_df.loc[missing, "hole_id"].tolist()
        logger.warning(f"LOCA_GL used without a declared vertical datum (LOCA_DATM) for holes: {holes}")

    collars_df["LOCA_DATM"] = datum.mask(missing, "undeclared")


def assign_horizontal_coordinates(collars_df: pd.DataFrame, crs_definition: int | str) -> pd.Series:
    """Select the coordinate family matching a projected or geographic CRS and assign x and y."""
    crs = CRS.from_user_input(crs_definition)
    family: CoordinateFamily
    if crs.is_projected:
        family = "national"
    elif crs.is_geographic:
        family = "geographic"
    else:
        raise AgsFileInvalidException(f"CRS {crs_definition} is neither projected nor geographic.")

    return assign_family_coordinates(collars_df, family)


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
