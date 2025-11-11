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
import typing
from abc import ABC, abstractmethod

from .column_mapping import ColumnMapping

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class MeasurementTableAdapter(ABC):
    """
    Abstract base class for different measurement table types.

    Provides a common interface for working with measurement data that can be organised
    either as point measurements at specific depths (DistanceTable) or as measurements
    over depth intervals (IntervalTable). Handles column mapping, validation, and
    NaN value tracking.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        column_mapping: ColumnMapping,
        nan_values_by_column: dict[str, list[typing.Any]] | None = None,
    ) -> None:
        """
        Initialise the measurement table adapter.

        :param df: DataFrame containing measurement data
        :param column_mapping: Column mapping configuration for locating required columns
        :param nan_values_by_column: Optional mapping of column names to lists of NaN sentinel values
        """
        self.df: pd.DataFrame = df
        self.mapping: ColumnMapping = column_mapping
        self.nan_values_by_column: dict[str, list[typing.Any]] = nan_values_by_column or {}
        self._validate()
        self._prepare_dataframe()

    def _validate(self) -> None:
        """
        Validate that required columns are present in the DataFrame.

        :raises ValueError: If the hole index column is not found
        """
        if not self._find_column(self.mapping.HOLE_INDEX_COLUMNS):
            raise ValueError(f"No hole index column found. Expected one of: {self.mapping.HOLE_INDEX_COLUMNS}")

    def _prepare_dataframe(self) -> None:
        """
        Prepare the DataFrame for use (e.g. sorting columns).
        """
        pass

    def get_hole_index_column(self) -> str:
        """
        Get the column name that relates each measurement to a downhole.

        :return: The name of the hole index column

        :raises ValueError: If no hole index column is found
        """
        col: str | None = self._find_column(self.mapping.HOLE_INDEX_COLUMNS)
        if not col:
            raise ValueError("No hole index column found")
        return col

    @typing.overload
    def get_nan_values(self, column: None = None) -> dict[str, list[typing.Any]]: ...

    @typing.overload
    def get_nan_values(self, column: str) -> list[typing.Any]: ...

    def get_nan_values(self, column: str | None = None) -> dict[str, list[typing.Any]] | list[typing.Any]:
        """
        Get NaN sentinel values for columns.

        :param column: Specific column name, or None to get all columns

        :return: If column is None, returns dict mapping column names to lists of sentinel values.
                 If column is specified, returns list of sentinel values for that column (empty if none).
        """
        if column is None:
            return self.nan_values_by_column

        return self.nan_values_by_column.get(column, [])

    @abstractmethod
    def get_primary_column(self) -> str:
        """
        Return the name of the primary measurement column.

        :return: Name of the primary column (depth for distance tables, from for interval tables)
        """
        pass

    def _find_column(self, possible_names: list[str]) -> str | None:
        """
        Find the first matching column name in the DataFrame (case-insensitive).

        :param possible_names: List of possible column names to search for

        :return: The actual column name found in the DataFrame, or None if not found
        """
        df_columns_lower: dict[str, str] = {col.lower(): col for col in self.df.columns}
        for name in possible_names:
            if name.lower() in df_columns_lower:
                return df_columns_lower[name.lower()]
        return None

    def get_attribute_columns(self) -> list[str]:
        """
        Return all columns except the primary measurement columns.

        Attribute columns are those that contain additional data beyond the core
        measurement columns (hole index, depth/intervals).

        :return: List of attribute column names
        """
        primary: list[str] = [self.get_hole_index_column()] + self.get_primary_columns()
        return [col for col in self.df.columns if col not in primary]

    @abstractmethod
    def get_primary_columns(self) -> list[str]:
        """
        Return list of all primary measurement columns.

        :return: List of primary column names that define the measurement structure
        """
        pass


class DistanceTable(MeasurementTableAdapter):
    """Measurement table adapter for point measurements at specific depths/distances"""

    @override
    def _validate(self) -> None:
        """
        Validate that required columns are present.

        :raises ValueError: If hole index or depth column is not found
        """
        super()._validate()
        if not self._find_column(self.mapping.DEPTH_COLUMNS):
            raise ValueError(f"No depth column found. Expected one of: {self.mapping.DEPTH_COLUMNS}")

    @override
    def _prepare_dataframe(self) -> None:
        """
        Sort the DataFrame by hole index and depth in ascending order.

        This ensures that hole chunks are contiguous and measurements are ordered
        by increasing depth within each hole.
        """
        self.df.sort_values(
            by=[self.get_hole_index_column(), self.get_depth_column()], ascending=True, axis=0, inplace=True
        )

    def get_depth_column(self) -> str:
        """
        Get the name of the depth/distance column.

        :return: The actual depth column name found in the DataFrame

        :raises ValueError: If no depth column is found
        """
        col: str | None = self._find_column(self.mapping.DEPTH_COLUMNS)
        if not col:
            raise ValueError("No depth column found")
        return col

    @override
    def get_primary_column(self) -> str:
        """
        Return the name of the primary measurement column (depth).

        :return: Name of the depth column
        """
        return self.get_depth_column()

    @override
    def get_primary_columns(self) -> list[str]:
        """
        Return list of primary measurement columns (depth only for distance tables).

        :return: List containing only the depth column name
        """
        return [self.get_depth_column()]

    def get_depth_values(self) -> pd.Series:
        """
        Get the depth values as a pandas Series.

        :return: Series containing all depth values from the depth column
        """
        return self.df[self.get_depth_column()]


class IntervalTable(MeasurementTableAdapter):
    """Measurement table adapter for measurements over depth intervals"""

    @override
    def _validate(self) -> None:
        """
        Validate that required columns are present.

        :raises ValueError: If hole index, from column, or to column is not found
        """
        super()._validate()
        from_col: str | None = self._find_column(self.mapping.FROM_COLUMNS)
        to_col: str | None = self._find_column(self.mapping.TO_COLUMNS)

        if not from_col or not to_col:
            raise ValueError(
                f"Missing interval columns. Expected: FROM: {self.mapping.FROM_COLUMNS}, TO: {self.mapping.TO_COLUMNS}"
            )

    @override
    def _prepare_dataframe(self) -> None:
        """
        Sort the DataFrame by hole index and from depth in ascending order.

        This ensures that hole chunks are contiguous and intervals are ordered
        by increasing start depth within each hole.
        """
        self.df.sort_values(
            by=[self.get_hole_index_column(), self.get_from_column()], ascending=True, axis=0, inplace=True
        )

    def get_from_column(self) -> str:
        """
        Get the name of the interval start depth column.

        :return: The actual from column name found in the DataFrame

        :raises ValueError: If no from column is found
        """
        col: str | None = self._find_column(self.mapping.FROM_COLUMNS)
        if not col:
            raise ValueError("No 'from' column found.")
        return col

    def get_to_column(self) -> str:
        """
        Get the name of the interval end depth column.

        :return: The actual to column name found in the DataFrame

        :raises ValueError: If no to column is found
        """
        col: str | None = self._find_column(self.mapping.TO_COLUMNS)
        if not col:
            raise ValueError("No 'to' column found.")
        return col

    @override
    def get_primary_column(self) -> str:
        """
        Return the name of the primary measurement column (from depth).

        :return: Name of the from column
        """
        return self.get_from_column()

    @override
    def get_primary_columns(self) -> list[str]:
        """
        Return list of primary measurement columns (from and to depths).

        :return: List containing the from and to column names
        """
        return [self.get_from_column(), self.get_to_column()]

    def get_intervals(self) -> pd.DataFrame:
        """
        Get a DataFrame containing only the interval columns with standardized names.

        :return: DataFrame with from and to columns defining the intervals
        """
        return self.df[[self.get_from_column(), self.get_to_column()]]


class MeasurementTableFactory:
    """
    Factory for detecting and creating the appropriate measurement table adapter.

    Automatically determines whether the DataFrame contains distance-based or
    interval-based measurements based on the presence of specific columns, and
    creates the corresponding adapter type.
    """

    @staticmethod
    def create(
        df: pd.DataFrame, column_mapping: ColumnMapping, nan_values_by_column: dict[str, typing.Any] | None = None
    ) -> MeasurementTableAdapter:
        """
        Create the appropriate measurement table adapter based on DataFrame columns.

        Checks for the presence of interval columns (from/to) or depth columns to
        determine the correct adapter type.

        :param df: DataFrame containing measurement data
        :param column_mapping: Column mapping configuration for locating required columns
        :param nan_values_by_column: Optional mapping of column names to lists of NaN sentinel values

        :return: Either an IntervalTable or DistanceTable adapter

        :raises ValueError: If the measurement type cannot be determined from available columns
        """
        df_columns_lower: set[str] = set(col.lower() for col in df.columns)

        # Check for interval measurement
        has_from: bool = any(col.lower() in df_columns_lower for col in column_mapping.FROM_COLUMNS)
        has_to: bool = any(col.lower() in df_columns_lower for col in column_mapping.TO_COLUMNS)

        if has_from and has_to:
            return IntervalTable(df, column_mapping, nan_values_by_column)

        # Check for distance measurement
        has_depth = any(col.lower() in df_columns_lower for col in column_mapping.DEPTH_COLUMNS)

        if has_depth:
            return DistanceTable(df, column_mapping, nan_values_by_column)

        raise ValueError(
            f"Cannot determine measurement type. Expected either depth column {column_mapping.DEPTH_COLUMNS} or interval columns {column_mapping.FROM_COLUMNS}/{column_mapping.TO_COLUMNS}"
        )
