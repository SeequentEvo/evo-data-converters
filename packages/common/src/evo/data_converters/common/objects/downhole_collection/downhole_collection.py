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


from ..base_properties import BaseSpatialDataProperties
from .column_mapping import ColumnMapping
from .hole_collars import HoleCollars
from .tables import MeasurementTableFactory, MeasurementTableAdapter

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class DownholeCollection(BaseSpatialDataProperties):
    """
    Intermediary data structure for a Downhole Collection.

    Acts as the go-between for source files (AGS, GEF) and a target Evo Geoscience Object.

    Separates collar information (stored once per hole) from measurement data (stored once per measurement). Supports multiple measurement tables via the MeasurementTableAdapter.
    """

    def __init__(
        self,
        *,
        collars: HoleCollars,
        name: str,
        measurements: list[MeasurementTableAdapter] | list[pd.DataFrame] | None = None,
        column_mapping: ColumnMapping | None = None,
        nan_values_by_attribute: dict[str, list[typing.Any]] | None = None,
        uuid: str | None = None,
        coordinate_reference_system: int | str | None = None,
        description: str | None = None,
        extensions: dict[str, typing.Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            name=name,
            uuid=uuid,
            description=description,
            extensions=extensions,
            tags=tags,
            coordinate_reference_system=coordinate_reference_system,
        )
        """
        Create a Downhole Collection intermediary object from a name and Hole Collars.

        Optionally pass a list of dataframes to construct measurement table adapters from, or
        pass the adapters as a list.
        """
        self.collars: HoleCollars = collars
        self.measurements: list[MeasurementTableAdapter] = []
        if measurements:
            for m in measurements:
                self.add_measurement_table(m, column_mapping)
        self.nan_values_by_attribute: dict[str, list[typing.Any]] = nan_values_by_attribute or {}

    def add_measurement_table(
        self, input: pd.DataFrame | MeasurementTableAdapter, column_mapping: ColumnMapping | None = None
    ) -> None:
        """Add a measurement table adapter"""
        if isinstance(input, pd.DataFrame):
            adapter: MeasurementTableAdapter = MeasurementTableFactory.create(input, column_mapping or ColumnMapping())
        else:
            adapter = input
        self.measurements.append(adapter)

    def get_measurement_tables(
        self, filter: list[type[MeasurementTableAdapter]] | None = None
    ) -> list[MeasurementTableAdapter]:
        """
        Get all or a subset of measurement table adapters
        """
        if filter is None:
            return self.measurements.copy()

        results: list[MeasurementTableAdapter] = []
        for m in self.measurements:
            if any(isinstance(m, cls) for cls in filter):
                results.append(m)
        return results

    @override
    def get_bounding_box(self) -> list[float]:
        return [
            self.collars.df["x"].min(),
            self.collars.df["x"].max(),
            self.collars.df["y"].min(),
            self.collars.df["y"].max(),
            self.collars.df["z"].min(),
            self.collars.df["z"].max(),
        ]
