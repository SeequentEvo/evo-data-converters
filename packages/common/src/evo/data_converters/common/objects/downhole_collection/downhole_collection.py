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
    Intermediary data structure for a downhole collection.

    Acts as the bridge between source file formats (AGS, GEF, etc.) and the target
    Evo Geoscience Object representation.

    The collection separates collar information (stored once per hole) from measurement
    data (stored once per measurement). Supports multiple measurement tables of different
    types (distance-based or interval-based) via the MeasurementTableAdapter interface.
    """

    def __init__(
        self,
        *,
        collars: HoleCollars,
        name: str,
        measurements: list[MeasurementTableAdapter] | list[pd.DataFrame] | None = None,
        column_mapping: ColumnMapping | None = None,
        uuid: str | None = None,
        coordinate_reference_system: int | str | None = None,
        description: str | None = None,
        extensions: dict[str, typing.Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """
        Create a downhole collection intermediary object.

        Initialises the collection with collar information and optional measurement data.
        Measurement data can be provided as either pre-constructed MeasurementTableAdapter
        objects or as pandas DataFrames (which will be automatically converted to the
        appropriate adapter type using the provided column mapping).

        :param collars: HoleCollars object containing spatial and metadata for each hole
        :param name: Name identifier for this downhole collection
        :param measurements: Optional list of measurement tables (as adapters or DataFrames)
        :param column_mapping: Column mapping configuration for converting DataFrames to adapters
        :param uuid: Optional unique identifier for the collection
        :param coordinate_reference_system: Optional CRS identifier (EPSG code or WKT string)
        :param description: Optional textual description of the collection
        :param extensions: Optional dictionary of custom extension data
        :param tags: Optional key-value pairs for tagging/categorizing the collection
        """
        super().__init__(
            name=name,
            uuid=uuid,
            description=description,
            extensions=extensions,
            tags=tags,
            coordinate_reference_system=coordinate_reference_system,
        )
        self.collars: HoleCollars = collars
        self.measurements: list[MeasurementTableAdapter] = []
        if measurements:
            for m in measurements:
                self.add_measurement_table(m, column_mapping)

    def add_measurement_table(
        self, input: pd.DataFrame | MeasurementTableAdapter, column_mapping: ColumnMapping | None = None
    ) -> None:
        """
        Add a measurement table to the collection.

        Accepts either a pre-constructed MeasurementTableAdapter or a pandas DataFrame.
        If a DataFrame is provided, it will be automatically converted to the appropriate
        adapter type (DistanceTable or IntervalTable) based on the column mapping and
        available columns.

        :param input: Either a MeasurementTableAdapter or DataFrame to add
        :param column_mapping: Column mapping configuration (required if input is a DataFrame)
        """
        if isinstance(input, pd.DataFrame):
            adapter: MeasurementTableAdapter = MeasurementTableFactory.create(input, column_mapping or ColumnMapping())
        else:
            adapter = input
        self.measurements.append(adapter)

    def get_measurement_tables(
        self, filter: list[type[MeasurementTableAdapter]] | None = None
    ) -> list[MeasurementTableAdapter]:
        """
        Get all or a filtered subset of measurement table adapters.

        Returns measurement tables from the collection. Optionally filters to return
        only tables of specific types (e.g., only DistanceTable or only IntervalTable).

        :param filter: Optional list of MeasurementTableAdapter subclass types to filter by.
                        If None, returns all measurement tables.

        :return: List of measurement table adapters matching the filter (or all if no filter)
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
        """
        Calculate the 3D bounding box from collar coordinates.

        Computes the minimum and maximum X, Y, and Z coordinates from all collar
        positions to define the spatial extent of the downhole collection.

        :return: List of 6 floats [min_x, max_x, min_y, max_y, min_z, max_z]
        """
        return [
            self.collars.df["x"].min(),
            self.collars.df["x"].max(),
            self.collars.df["y"].min(),
            self.collars.df["y"].max(),
            self.collars.df["z"].min(),
            self.collars.df["z"].max(),
        ]
