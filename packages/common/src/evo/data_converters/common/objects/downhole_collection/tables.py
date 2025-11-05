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
import sys
from abc import ABC, abstractmethod

from .column_mapping import ColumnMapping

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class MeasurementTableAdapter(ABC):
    """Base class for different measurement table types"""

    def __init__(self, df: pd.DataFrame, column_mapping: ColumnMapping) -> None:
        self.df: pd.DataFrame = df
        self.mapping: ColumnMapping = column_mapping
        self._validate()

    def _validate(self) -> None:
        """Ensure required columns are present"""
        if not self._find_column(self.mapping.HOLE_INDEX_COLUMNS):
            raise ValueError(f"No hole index column found. Expected one of: {self.mapping.HOLE_INDEX_COLUMNS}")

    def get_hole_index_column(self) -> str:
        """Get the column name that relates each measurement to a downhole"""
        col: str | None = self._find_column(self.mapping.HOLE_INDEX_COLUMNS)
        if not col:
            raise ValueError("No hole index column found")
        return col

    @abstractmethod
    def get_primary_column(self) -> str:
        """Return the name of the primary measurement column"""
        pass

    def _find_column(self, possible_names: list[str]) -> str | None:
        """Find first matching column name in dataframe"""
        df_columns_lower: dict[str, str] = {col.lower(): col for col in self.df.columns}
        for name in possible_names:
            if name.lower() in df_columns_lower:
                return df_columns_lower[name.lower()]
        return None

    def get_attribute_columns(self) -> list[str]:
        """Return all columns except the primary measurement column(s)"""
        primary: list[str] = [self.get_hole_index_column()] + self.get_primary_columns()
        return [col for col in self.df.columns if col not in primary]

    @abstractmethod
    def get_primary_columns(self) -> list[str]:
        """Return list of primary measurement columns"""
        pass


class DistanceTable(MeasurementTableAdapter):
    """For measurements at specific depths/distances"""

    @override
    def _validate(self) -> None:
        super()._validate()
        if not self._find_column(self.mapping.DEPTH_COLUMNS):
            raise ValueError(f"No depth column found. Expected one of: {self.mapping.DEPTH_COLUMNS}")

    def get_depth_column(self) -> str:
        """Get the actual depth column name"""
        col: str | None = self._find_column(self.mapping.DEPTH_COLUMNS)
        if not col:
            raise ValueError("No depth column found")
        return col

    @override
    def get_primary_column(self) -> str:
        return self.get_depth_column()

    @override
    def get_primary_columns(self) -> list[str]:
        return [self.get_depth_column()]

    def get_depth_values(self) -> pd.Series:
        """Convenience method to get depth values"""
        return self.df[self.get_depth_column()]


class IntervalTable(MeasurementTableAdapter):
    """For measurements over depth intervals"""

    @override
    def _validate(self) -> None:
        super()._validate()
        from_col: str | None = self._find_column(self.mapping.FROM_COLUMNS)
        to_col: str | None = self._find_column(self.mapping.TO_COLUMNS)

        if not from_col or not to_col:
            raise ValueError(
                f"Missing interval columns. Expected: FROM: {self.mapping.FROM_COLUMNS}, TO: {self.mapping.TO_COLUMNS}"
            )

    def get_from_column(self) -> str:
        col: str | None = self._find_column(self.mapping.FROM_COLUMNS)
        if not col:
            raise ValueError("No 'from' column found.")
        return col

    def get_to_column(self) -> str:
        col: str | None = self._find_column(self.mapping.TO_COLUMNS)
        if not col:
            raise ValueError("No 'to' column found.")
        return col

    @override
    def get_primary_column(self) -> str:
        return self.get_from_column()

    @override
    def get_primary_columns(self) -> list[str]:
        return [self.get_from_column(), self.get_to_column()]

    def get_intervals(self) -> pd.DataFrame:
        """Get dataframe with standardized interval columns"""
        return self.df[[self.get_from_column(), self.get_to_column()]]


class MeasurementTableFactory:
    """Factory to detect and create appropriate measurement table adapter"""

    @staticmethod
    def create(df: pd.DataFrame, column_mapping: ColumnMapping) -> MeasurementTableAdapter:
        df_columns_lower: set[str] = set(col.lower() for col in df.columns)

        # Check for interval measurement
        has_from: bool = any(col.lower() in df_columns_lower for col in column_mapping.FROM_COLUMNS)
        has_to: bool = any(col.lower() in df_columns_lower for col in column_mapping.TO_COLUMNS)

        if has_from and has_to:
            return IntervalTable(df, column_mapping)

        # Check for distance measurement
        has_depth = any(col.lower() in df_columns_lower for col in column_mapping.DEPTH_COLUMNS)

        if has_depth:
            return DistanceTable(df, column_mapping)

        raise ValueError(
            f"Cannot determine measurement type. Expected either depth column {column_mapping.DEPTH_COLUMNS} or interval columns {column_mapping.FROM_COLUMNS}/{column_mapping.TO_COLUMNS}"
        )
