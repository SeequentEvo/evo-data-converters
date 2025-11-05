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

import pandas as pd


HOLE_COLLARS_SCHEMA: dict[str, str] = {
    # Unique identifier for each row, 1-based
    "hole_index": "int",
    # Unique identifier for each survey
    "hole_id": "str",
    # Easting coordinate
    "x": "float",
    # Northing coordinate
    "y": "float",
    # Elevation at collar
    "z": "float",
    # Depth of final measurement
    "final_depth": "float",
}


class HoleCollars:
    """
    Hole collar information (one row per hole)

    Any columns that do not appear in the schema are treated as attributes.

    In the following example, both SCPG_ENV and SCPG_RATE will become attributes.

    | hole_index | hole_id |  x  |  y  |  z  | final_depth    | SCPG_ENV | SCPG_RATE |
    | 1          | CPT-001 | 1.0 | 2.0 | 3.0 | 5.00           | Sunny    | 20        |
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df: pd.DataFrame = df
        self._validate()

    def _validate(self) -> None:
        if not all(col in self.df.columns for col in HOLE_COLLARS_SCHEMA.keys()):
            raise ValueError("Could not find all required columns")

        if not self.is_schema_valid(self.df, HOLE_COLLARS_SCHEMA):
            raise ValueError("Data is of incorrect type in collars table")

    def is_schema_valid(self, df: pd.DataFrame, schema: dict[str, str]) -> bool:
        for col, expected_type in schema.items():
            actual_dtype = df[col].dtype

            if expected_type == "int" and not pd.api.types.is_integer_dtype(actual_dtype):
                return False
            elif expected_type == "float" and not pd.api.types.is_float_dtype(actual_dtype):
                return False
            elif expected_type == "str" and not pd.api.types.is_string_dtype(actual_dtype) and actual_dtype != "object":
                return False

        return True

    def get_attribute_column_names(self) -> list[str]:
        return [col for col in self.df.columns if col not in HOLE_COLLARS_SCHEMA.keys()]

    def get_attributes_df(self) -> pd.DataFrame:
        return self.df[self.get_attribute_column_names()]
