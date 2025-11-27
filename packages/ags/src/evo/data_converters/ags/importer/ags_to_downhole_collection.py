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

import evo.logging
from evo.data_converters.ags.common import AgsContext
from evo.data_converters.common.objects.downhole_collection import (
    ColumnMapping,
    DownholeCollection,
    HoleCollars,
)
from evo.data_converters.common.objects.downhole_collection.tables import DEFAULT_AZIMUTH, DEFAULT_DIP, DistanceTable
import pandas as pd

logger = evo.logging.getLogger("data_converters")


def create_from_parsed_ags(
    ags_context: AgsContext,
    tags: dict[str, str] | None = None,
) -> DownholeCollection:
    """Converts the in-memory dataframes of AgsContext to an Evo Downhole Collection.

    For hole collars, we need information from the SCPG table as well as the LOCA details of the SCPG row.
    Collars are uniquely identified by LOCA_ID and SCPG_TESN together.

    Fetches measurements from all relevant tables (SCPT, SCPP, GEOL, SCDG) and assigns hole_index.

    :param ags_context: The context containing the AGS file as dataframes.
    :param tags: Optional dict of tags to add to the DownholeCollection.
    :return: A DownholeCollection object
    """

    # Build collars from LOCA and SCPG, and SCPT for final depth
    hole_collars: HoleCollars = build_collars(ags_context)
    collars_df = hole_collars.df

    # Prepare lookup tables for merging hole_index into measurements
    # GEOL only has LOCA_ID, all others have both LOCA_ID and SCPG_TESN
    lookup_with_tesn = collars_df[["LOCA_ID", "SCPG_TESN", "hole_index"]]
    lookup_without_tesn = collars_df[["LOCA_ID", "hole_index"]]

    measurements: list[pd.DataFrame] = ags_context.get_tables(groups=AgsContext.MEASUREMENT_GROUPS)
    for table in measurements:
        if "SCPG_TESN" in table.columns:
            # CPT-specific data: merge on both LOCA_ID and SCPG_TESN
            table_with_index = table.merge(lookup_with_tesn, on=["LOCA_ID", "SCPG_TESN"], how="left")
        else:
            # Location-level data (e.g., GEOL): merge on LOCA_ID only
            # This will duplicate rows if multiple collars exist at the same location
            table_with_index = table.merge(lookup_without_tesn, on=["LOCA_ID"], how="left")

        table["hole_index"] = table_with_index["hole_index"]

    downhole_collection: DownholeCollection = DownholeCollection(
        collars=hole_collars,
        name=ags_context.filename,
        measurements=measurements,
        coordinate_reference_system=ags_context.coordinate_reference_system or "unspecified",
        tags=tags,
        column_mapping=ColumnMapping(
            DEPTH_COLUMNS=["SCPT_DPTH", "SCDG_DPTH"],
            FROM_COLUMNS=["GEOL_TOP", "SCPP_TOP"],
            TO_COLUMNS=["GEOL_BASE", "SCPP_BASE"],
        ),
    )

    # Calculate dip and azimuth for the first distance table, which is used to build the Location->Path component.
    horn_df = ags_context.get_table("HORN")
    if horn_df is not None and not horn_df.empty:
        for mt in downhole_collection.measurements:
            if isinstance(mt, DistanceTable):
                depth_col = mt.get_primary_column()
                calculate_dip_and_azimuth(horn_df, mt.df, depth_col)
                mt.mapping.DIP_COLUMNS.append("dip")
                mt.mapping.AZIMUTH_COLUMNS.append("azimuth")
                break

    return downhole_collection


def build_collars(ags_context: AgsContext) -> HoleCollars:
    """Builds the HoleCollars object from the AGS context.

    Collars are uniquely identified by LOCA_ID and SCPG_TESN together.

    .. todo::
       Use Z when possible (from CRS?)

    :param ags_context: The context containing the AGS file as dataframes.
    :return: A HoleCollars object
    """
    loca_df: pd.DataFrame = ags_context.get_table("LOCA").copy()
    scpg_df: pd.DataFrame = ags_context.get_table("SCPG").copy()
    scpt_df: pd.DataFrame = ags_context.get_table("SCPT").copy()

    # One row per (LOCA_ID, SCPG_TESN): take SCPG (which carries both keys) and add entire LOCA
    collars_df: pd.DataFrame = scpg_df.merge(loca_df, on="LOCA_ID", how="left")

    # Compute final depth per (LOCA_ID, SCPG_TESN)
    final_depths = scpt_df.groupby(["LOCA_ID", "SCPG_TESN"], dropna=False)["SCPT_DPTH"].max().reset_index()
    final_depths = final_depths.rename(columns={"SCPT_DPTH": "final_depth"})

    # Merge final depths into collars
    collars_df = collars_df.merge(final_depths, on=["LOCA_ID", "SCPG_TESN"], how="left")

    # Create hole_id as composite of LOCA_ID and SCPG_TESN and assign hole_index
    collars_df["hole_id"] = collars_df["LOCA_ID"].astype(str) + ":" + collars_df["SCPG_TESN"].astype(str)
    collars_df["hole_index"] = range(1, len(collars_df) + 1)

    # Rename coordinates and set z
    collars_df = collars_df.rename(columns={"LOCA_NATE": "x", "LOCA_NATN": "y"})
    collars_df["z"] = 0.0

    # Ensure final_depth is float dtype even if NaN
    collars_df["final_depth"] = pd.to_numeric(collars_df["final_depth"], errors="coerce").astype(float)

    # Reorder columns to standard first but retain useful keys
    standard_cols = ["hole_index", "hole_id", "x", "y", "z", "final_depth"]
    key_cols = ["LOCA_ID", "SCPG_TESN"]
    other_cols = [c for c in collars_df.columns if c not in standard_cols + key_cols]
    collars_df = collars_df[standard_cols + key_cols + other_cols]

    # Drop duplicate collars if present (defensive)
    collars_df = collars_df.drop_duplicates(subset=["LOCA_ID", "SCPG_TESN"], keep="first").reset_index(drop=True)

    return HoleCollars(df=collars_df)


def calculate_dip_and_azimuth(
    horn_df: pd.DataFrame,
    measurements_df: pd.DataFrame,
    depth_column: str,
) -> None:
    """Add dip and azimuth columns from HORN table.

    Matches each measurement to a HORN interval where HORN_TOP <= depth < HORN_BASE.
    Measurements outside all intervals for their LOCA_ID get vertical defaults (90°/0°).

    :param horn_df: The HORN table DataFrame.
    :param measurements_df: The distance table DataFrame where dip/azimuth columns will be added.
    :param depth_column: Name of the depth column in distance table.
    """
    dip_values = []
    azimuth_values = []
    unmatched_count = 0

    # Group HORN intervals by LOCA_ID for faster lookup
    horn_by_loca = {loca_id: group for loca_id, group in horn_df.groupby("LOCA_ID")}

    for _, row in measurements_df.iterrows():
        loca_id = row["LOCA_ID"]
        depth = row[depth_column]

        intervals = horn_by_loca.get(loca_id)

        if intervals is None:
            dip_values.append(DEFAULT_DIP)
            azimuth_values.append(DEFAULT_AZIMUTH)
            unmatched_count += 1
            continue

        # Find interval containing this depth
        matching = intervals[(intervals["HORN_TOP"] <= depth) & (intervals["HORN_BASE"] > depth)]

        if len(matching) >= 1:
            dip_values.append(matching.iloc[0]["HORN_INCL"])
            azimuth_values.append(matching.iloc[0]["HORN_ORNT"])
        else:
            dip_values.append(DEFAULT_DIP)
            azimuth_values.append(DEFAULT_AZIMUTH)
            unmatched_count += 1

    if unmatched_count > 0:
        logger.info(f"{unmatched_count} depth measurements outside HORN intervals, assuming vertical")

    measurements_df["dip"] = pd.Series(dip_values, dtype="float64")
    measurements_df["azimuth"] = pd.Series(azimuth_values, dtype="float64")
