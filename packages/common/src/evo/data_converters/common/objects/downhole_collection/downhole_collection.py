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

import sys
import typing

import numpy as np
from numpy.typing import NDArray
import pandas as pd

from ..base_properties import BaseSpatialDataProperties
from .column_mapping import ColumnMapping
from .hole_collars import HoleCollars
from .tables import MeasurementTable, create_measurement_table, DistanceTable

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
    types (distance-based or interval-based) via the MeasurementTable interface.
    """

    def __init__(
        self,
        *,
        collars: HoleCollars,
        name: str,
        measurements: list[MeasurementTable] | list[pd.DataFrame] | None = None,
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
        Measurement data can be provided as either pre-constructed MeasurementTable
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
        self.measurements: list[MeasurementTable] = []
        if measurements:
            for m in measurements:
                self.add_measurement_table(m, column_mapping)

    def add_measurement_table(
        self, measurements: pd.DataFrame | MeasurementTable, column_mapping: ColumnMapping | None = None
    ) -> None:
        """
        Add a measurement table to the collection.

        Accepts measurements as either a pre-constructed MeasurementTable or a pandas DataFrame.
        If a DataFrame is provided, it will be automatically converted to the appropriate
        type (DistanceTable or IntervalTable) based on the column mapping and
        available columns.

        :param measurements: Either a MeasurementTable or DataFrame to add
        :param column_mapping: Column mapping configuration (required if input is a DataFrame)
        """
        if isinstance(measurements, pd.DataFrame):
            table: MeasurementTable = create_measurement_table(measurements, column_mapping or ColumnMapping())
        elif isinstance(measurements, MeasurementTable):
            table = measurements
        else:
            raise ValueError("measurements must be a pandas DataFrame or MeasurementTable")

        self.measurements.append(table)

    def get_measurement_tables(
        self, filter_to_table_type: list[type[MeasurementTable]] | None = None
    ) -> list[MeasurementTable]:
        """
        Get all or a filtered subset of measurement table adapters.

        Returns measurement tables from the collection. Optionally filters to return
        only tables of specific types (e.g., only DistanceTable or only IntervalTable).

        :param filter_to_table_type: Optional list of MeasurementTable subclass types to filter to.
                        If None, returns all measurement tables.

        :return: List of measurement table adapters matching the filter (or all if no filter)
        """
        if filter_to_table_type is None:
            return self.measurements.copy()

        results = [m for m in self.measurements if isinstance(m, tuple(filter_to_table_type))]
        return results

    def _compute_hole_bounding_box(
        self,
        collar_x: float,
        collar_y: float,
        collar_z: float,
        depths: pd.Series,
        dips: pd.Series,
        azimuths: pd.Series,
    ):
        """
        Compute 3D bounding box for a deviated hole given collar XYZ and
        depth / dip / azimuth data.

        Conventions
        -----------
        - depths: measured depth along the hole (m), positive downward.
        - dips: inclination FROM VERTICAL (degrees).
            0° = vertical down, 90° = horizontal.
        - azimuths: degrees clockwise from North.
        - Coordinates: X = Easting, Y = Northing, Z = elevation (up).
        """

        # TODO - list of things that need resolving
        #  - Don't drop rows unless the depth is nan
        #  - I'm not sure whether prepending 0 to steps is the right thing to do. Also concatenating the collars.
        #  - We shouldn't be merging a bunch of tables. We only want the main "geometry" depth table
        #  - Do the units need to be taken into account? The elements of the columns are `pint.Quantity`. It's not
        #     clear how these values correspond to the other units of the published object.
        #  - Tests for `compute_bounding_box`

        df = pd.DataFrame(
            {
                "depth": depths,
                "dip": dips,
                "azimuth": azimuths,
            }
        ).dropna(subset=["depth", "dip", "azimuth"])

        box = self.compute_bounding_box(
            df["depth"].astype(float).to_numpy(),
            df["dip"].astype(float).to_numpy(),
            df["azimuth"].astype(float).to_numpy(),
            offset=(collar_x, collar_y, collar_z)
        )
        return dict(zip(["xmin", "xmax", "ymin", "ymax", "zmin", "zmax"], box))

    @staticmethod
    def compute_bounding_box(
            # TODO Is there a common place for type hints?
            depths: NDArray[np.float64],
            dips: NDArray[np.float64],
            azimuths: NDArray[np.float64],
            offset: tuple[float, float, float] = (0., 0., 0.),
    ) -> tuple[float, float, float, float, float, float]:  # xmin, xmax, ymin, ymax, zmin, zmax

        if not np.all(depths[:-1] <= depths[1:]):
            raise ValueError("depths must be sorted")

        dips_rad = np.deg2rad(dips)
        azimuths_rad = np.deg2rad(azimuths)

        # Step lengths along the hole (assume collar at MD = 0,
        # first survey value applies from 0 -> depth[0])
        # TODO not sure if I need to prepend 0
        step = np.diff(depths, prepend=0.0)

        # Dip from vertical:
        #   vertical (down) component = step * sin(dip)
        #   horizontal component      = step * cos(dip)
        dz_down = step * np.sin(dips_rad)
        horiz = step * np.cos(dips_rad)

        # Horizontal into N/E (0° = North, 90° = East)
        dN = horiz * np.cos(azimuths_rad)
        dE = horiz * np.sin(azimuths_rad)

        # Convert to XYZ increments (Z up)
        dX = dE
        dY = dN
        dZ = -dz_down

        x = np.cumsum(dX)
        y = np.cumsum(dY)
        z = np.cumsum(dZ)

        def ensure_zero(a, b):
            return min(a, 0), max(b, 0)

        x0, x1 = ensure_zero(x.min(), x.max())
        y0, y1 = ensure_zero(y.min(), y.max())
        z0, z1 = ensure_zero(z.min(), z.max())

        return x0 + offset[0], x1 + offset[0], y0 + offset[1], y1 + offset[1], z0 + offset[2], z1 + offset[2]


    def _combine_bounding_boxes(self, bboxes: list[dict[str, float]]):
        """
        Given a list of bbox dicts like:
            {"xmin": ..., "xmax": ..., "ymin": ..., "ymax": ..., "zmin": ..., "zmax": ...}
        return a single bbox of 6 floats that encloses them all.
        """

        if not bboxes:
            raise ValueError("bboxes list is empty")

        return [
            min(b["xmin"] for b in bboxes),
            max(b["xmax"] for b in bboxes),
            min(b["ymin"] for b in bboxes),
            max(b["ymax"] for b in bboxes),
            min(b["zmin"] for b in bboxes),
            max(b["zmax"] for b in bboxes),
        ]

    @override
    def get_bounding_box(self) -> list[float]:
        """
        Calculate the 3D bounding box from collar coordinates.

        Computes the minimum and maximum X, Y, and Z coordinates from all collar
        positions to define the spatial extent of the downhole collection.

        :return: List of 6 floats [min_x, max_x, min_y, max_y, min_z, max_z]
        """

        collars_df = self.collars.df
        measurement_tables = self.get_measurement_tables(filter_to_table_type=[DistanceTable])
        bboxes = []

        for mt in measurement_tables:
            mt._prepare_dataframe()
            for hole_index, hole_id, x, y, z in zip(
                collars_df["hole_index"], collars_df["hole_id"], collars_df["x"], collars_df["y"], collars_df["z"]
            ):
                depths = mt.get_depth_values(filter_to_hole_index=hole_index)
                dips = mt.get_dip_values(filter_to_hole_index=hole_index)
                azimuths = mt.get_azimuth_values(filter_to_hole_index=hole_index)
                bbox = self._compute_hole_bounding_box(
                    collar_x=x,
                    collar_y=y,
                    collar_z=z,
                    depths=depths,
                    dips=dips,
                    azimuths=azimuths,
                )
                bboxes.append(bbox)

        return self._combine_bounding_boxes(bboxes=bboxes) if bboxes else []
