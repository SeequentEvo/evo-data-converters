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
    - All are assumed vertical at this stage, which will be the case with some AGS files
    - Use Z when CRS provided gives us it
    - Include GEOL table, append SCPG to collars
    - Avoid iterating over dataframes, computationally expensive
    - Avoid appending to dataframes, build dict and pass into df

    :param ags_context: The context containing the AGS file as dataframes.
    :return: A DownholeCollection object
    """

    loca_id_to_hole_index: dict[str, int] = {}
    collars_df: pd.DataFrame = pd.DataFrame()
    scpt_df: pd.DataFrame = ags_context.get_table("SCPT")

    for hole_index, loca_row in enumerate(ags_context.get_table("LOCA").itertuples(index=False), start=1):
        loca_id_to_hole_index[loca_row.LOCA_ID] = hole_index
        # Assemble one row for the collars table
        collar_row = {
            # 1‑based index for each hole
            "hole_index": hole_index,
            # Unique survey identifier from the LOCA table
            "hole_id": loca_row.LOCA_ID,
            # Easting (x) and Northing (y) coordinates – cast to float
            "x": float(loca_row.LOCA_NATE),
            "y": float(loca_row.LOCA_NATN),
            "z": 0.0,
            "final_depth": _calculate_final_depth(
                scpt_df,
                loca_id=loca_row.LOCA_ID,
            ),
        }
        # Append the new row to the DataFrame
        collars_df = pd.concat([collars_df, pd.DataFrame([collar_row])], ignore_index=True)

    hole_collars: HoleCollars = HoleCollars(df=collars_df)
    measurements: list[pd.DataFrame] = ags_context.get_tables(groups=["SCPT"])
    for table in measurements:
        table["hole_index"] = table["LOCA_ID"].map(loca_id_to_hole_index)

    downhole_collection: DownholeCollection = DownholeCollection(
        collars=hole_collars,
        name="TODO",
        measurements=measurements,
        coordinate_reference_system=ags_context.coordinate_reference_system,
        tags=tags,
    )

    return downhole_collection


def _calculate_final_depth(scpt_df: pd.DataFrame, loca_id: str) -> float:
    """Calculate the final depth of a borehole, specified by loca_id, from an SCPT table"""
    scpt_df_for_loca = scpt_df[scpt_df["LOCA_ID"] == loca_id]
    return float(scpt_df_for_loca["SCPT_DPTH"].max())
