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
    Container for hole collar information with one row per downhole.

    Manages the collar data for a collection of downholes. Each row represents a
    single hole with its spatial location and metadata. Columns that match the
    schema are treated as core data, while any additional columns are treated as
    custom attributes.

    **Core columns (required):**

    - hole_index: Integer identifier (1-based) for each hole
    - hole_id: String identifier for each survey/hole
    - x, y, z: Float coordinates (easting, northing, elevation)
    - final_depth: Float representing the depth of the final measurement

    **Example DataFrame structure:**

    ========== ======== === === === =========== ======== =========
    hole_index hole_id  x   y   z   final_depth SCPG_ENV SCPG_RATE
    ========== ======== === === === =========== ======== =========
    1          CPT-001  1.0 2.0 3.0 5.0         Sunny    20
    2          CPT-002  4.0 5.0 6.0 7.5         Cloudy   25
    ========== ======== === === === =========== ======== =========

    In this example, SCPG_ENV and SCPG_RATE are treated as attribute columns.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """
        Initialise hole collars from a DataFrame.

        :param df: DataFrame containing collar information with required schema columns

        :raises ValueError: If required columns are missing or data types are incorrect
        """
        self.df: pd.DataFrame = df
        self._validate()

    def _validate(self) -> None:
        """
        Validate that the DataFrame contains all required columns with correct types.

        :raises ValueError: If required columns are missing or have incorrect data types
        """
        if not all(col in self.df.columns for col in HOLE_COLLARS_SCHEMA.keys()):
            raise ValueError("Could not find all required columns")

        if not self.is_schema_valid(self.df, HOLE_COLLARS_SCHEMA):
            raise ValueError("Data is of incorrect type in collars table")

    def is_schema_valid(self, df: pd.DataFrame, schema: dict[str, str]) -> bool:
        """
        Check if DataFrame columns match the expected schema types.

        :param df: DataFrame to validate
        :param schema: Dictionary mapping column names to expected type strings ('int', 'float', 'str')

        :return: True if all columns match their expected types, False otherwise
        """
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
        """
        Get the names of columns that are not part of the core schema.

        :return: List of attribute column names
        """
        return [col for col in self.df.columns if col not in HOLE_COLLARS_SCHEMA.keys()]

    def get_attributes_df(self) -> pd.DataFrame:
        """
        Get a DataFrame containing only the attribute columns.

        :return: DataFrame with only the non-schema (attribute) columns
        """
        return self.df[self.get_attribute_column_names()]
