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


from evo.data_converters.ags.common import AgsContext
from evo.data_converters.common.objects.downhole_collection import (
    ColumnMapping,
    DownholeCollection,
    HoleCollars,
)
import pandas as pd


def create_from_parsed_ags(
    ags_context: AgsContext,
    tags: dict[str, str] | None = None,
) -> DownholeCollection:
    """
    Converts the in-memory dataframes of AgsContext to an Evo Downhole Collection.

    For hole collars, we need information from the SCPG table as well as the LOCA details of the SCPG row.

    TODO:
    - Use Z when CRS provided gives us it

    :param ags_context: The context containing the AGS file as dataframes.
    :return: A DownholeCollection object
    """

    loca_df: pd.DataFrame = ags_context.get_table("LOCA").copy()
    scpt_df: pd.DataFrame = ags_context.get_table("SCPT")

    # Calculate final depths for all LOCA_IDs at once
    final_depths = scpt_df.groupby("LOCA_ID")["SCPT_DPTH"].max().reset_index()
    final_depths.columns = ["LOCA_ID", "final_depth"]

    # Create collars dataframe using vectorised operations
    collars_df: pd.DataFrame = loca_df.merge(final_depths, on="LOCA_ID", how="left")
    collars_df["hole_index"] = range(1, len(collars_df) + 1)
    collars_df = collars_df.rename(
        columns={
            "LOCA_ID": "hole_id",
            "LOCA_NATE": "x",
            "LOCA_NATN": "y",
        }
    )
    collars_df["z"] = 0.0
    collars_df["hole_id"] = collars_df["hole_id"].astype(str)
    collars_df["x"] = collars_df["x"].astype(float)
    collars_df["y"] = collars_df["y"].astype(float)

    # Get SCPG table and merge with collars
    scpg_df: pd.DataFrame = ags_context.get_table("SCPG")
    collars_df = collars_df.merge(scpg_df, left_on="hole_id", right_on="LOCA_ID", how="left")

    # Drop duplicate LOCA_ID column from SCPG merge
    if "LOCA_ID" in collars_df.columns:
        collars_df = collars_df.drop(columns=["LOCA_ID"])

    # Reorder columns to keep standard columns first
    standard_cols = ["hole_index", "hole_id", "x", "y", "z", "final_depth"]
    other_cols = [col for col in collars_df.columns if col not in standard_cols]
    collars_df = collars_df[standard_cols + other_cols]

    # Create LOCA_ID to hole_index mapping
    loca_id_to_hole_index: dict[str, int] = collars_df.set_index("hole_id")["hole_index"].to_dict()
    hole_collars: HoleCollars = HoleCollars(df=collars_df)

    measurements: list[pd.DataFrame] = ags_context.get_tables(groups=["SCPT", "GEOL"])
    for table in measurements:
        table["hole_index"] = table["LOCA_ID"].map(loca_id_to_hole_index)

    downhole_collection: DownholeCollection = DownholeCollection(
        collars=hole_collars,
        name="TODO",
        measurements=measurements,
        coordinate_reference_system=ags_context.coordinate_reference_system,
        tags=tags,
        column_mapping=ColumnMapping(DEPTH_COLUMNS=["SCPT_DPTH"]),
    )

    return downhole_collection
