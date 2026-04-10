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

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Any

import numpy as np
import pandas as pd

from evo.common.interfaces import IContext
from evo.objects import SchemaVersion
from evo.objects.utils.table_formats import FLOAT_ARRAY_3, KnownTableFormat, DOWNHOLE_COLLECTION_LOCATION_HOLES

from evo.objects.typed._data import DataTable, DataTableAndAttributes
from evo.objects.typed._model import DataLocation, SchemaLocation, SchemaModel
from evo.objects.typed.attributes import Attributes
from evo.objects.typed.spatial import BaseSpatialObject, BaseSpatialObjectData
from evo.objects.typed.types import BoundingBox

__all__ = [
    "DownholeCollection",
    "DownholeCollectionData",
]

from scipy.linalg._decomp_interpolative import NDArray

_X = "x"
_Y = "y"
_Z = "z"
_COORDINATE_COLUMNS = [_X, _Y, _Z]


type HolePath = pd.DataFrame
type HoleProperties = pd.DataFrame
type HoleAttributes = pd.DataFrame


@dataclass(kw_only=True, frozen=True)
class DownholeCollectionData(BaseSpatialObjectData):
    """Data class for creating a new DownholeCollection

    :param name: The name of the object.
    :param holes: A list of DataFrames representing the paths of the holes. One DataFrame per hole.
            Mandatory columns: depth, dip, azimuth. Extra columns are treated as attributes.
    :param properties: DataFrame for the properties of the holes. The ith row corresponds to the ith element of `holes`.
            Mandatory columns: id, final, target, current, x, y, z
    :param attributes: DataFrame for the attributes of the holes. The ith row corresponds to the ith element of `holes`.
    :param coordinate_reference_system: Optional EPSG code or WKT string for the coordinate reference system.
    :param description: Optional description of the object.
    :param tags: Optional dictionary of tags for the object.
    :param extensions: Optional dictionary of extensions for the object.
    """

    holes: list[HolePath]

    # Schema defined hole properties: id, final, target, current, x, y, z
    properties: HoleProperties

    # Data-specific attributes
    attributes: HoleAttributes | None

    def __post_init__(self):
        assert self.attributes is None or len(self.holes) == len(self.attributes)

    def compute_bounding_box(self) -> BoundingBox:
        bboxes = []

        for i, hole in enumerate(self.holes):
            collar = tuple(self.properties.loc[i, _COORDINATE_COLUMNS])
            bboxes.append(self._compute_hole_bounding_box(hole, collar))

        return self._combine_bounding_boxes(bboxes)

    @staticmethod
    def _compute_bounding_box_np(
            # TODO Is there a common place for type hints?
            depths: NDArray[np.float64],
            dips: NDArray[np.float64],
            azimuths: NDArray[np.float64],
            offset: tuple[float, float, float] = (0., 0., 0.),
    ) -> BoundingBox:

        if not np.all(depths[:-1] <= depths[1:]):
            raise ValueError("depths must be sorted")

        if len(depths) != len(dips) or len(depths) != len(azimuths):
            raise ValueError("depths, dips, and azimuths must have same length")

        # TODO - Test with NaNs in these values
        # Process NaNs
        depths = depths[~np.isnan(depths)]
        dips[np.isnan(dips)] = 90
        azimuths[np.isnan(azimuths)] = 0

        dips_rad = np.deg2rad(dips)
        azimuths_rad = np.deg2rad(azimuths)

        # Prepend 0 so `step` has the same shape as `dips` and `azimuths`, and so the first depth gets treated as the
        # first step. The depth column might already start with 0, in which case the first step will be length 0, which
        # is a no-op as far as the following calculation is concerned.
        step = np.diff(depths, prepend=0.0)

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

        return BoundingBox(
            min_x=x0 + offset[0],
            max_x=x1 + offset[0],
            min_y=y0 + offset[1],
            max_y=y1 + offset[1],
            min_z=z0 + offset[2],
            max_z=z1 + offset[2],
        )

    # TODO - Consider unit tests
    @staticmethod
    def _compute_hole_bounding_box(
        depths_dips_azimuths_table: pd.DataFrame,
        collar: tuple[float, float, float],
    ) -> BoundingBox:
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
        #  - We shouldn't be merging a bunch of tables. We only want the main "geometry" depth table
        #  - Do the units need to be taken into account? The elements of the columns are `pint.Quantity`. It's not
        #     clear how these values correspond to the other units of the published object.

        df = depths_dips_azimuths_table.dropna(subset=["depth"])

        box = DownholeCollectionData._compute_bounding_box_np(
            df["depth"].astype(float).to_numpy(),
            df["dip"].astype(float).to_numpy(),
            df["azimuth"].astype(float).to_numpy(),
            offset=collar,
        )

        return box
    # TODO - Consider moving this to `types.py`, as `BoundingBox.from_path()`.

    # TODO move this to the BoundingBox definition
    @staticmethod
    def _combine_bounding_boxes(bboxes: list[BoundingBox]):
        if not bboxes:
            raise ValueError("bboxes list is empty")

        return BoundingBox(
            min_x=min(b.min_x for b in bboxes),
            max_x=max(b.max_x for b in bboxes),
            min_y=min(b.min_y for b in bboxes),
            max_y=max(b.max_y for b in bboxes),
            min_z=min(b.min_z for b in bboxes),
            max_z=max(b.max_z for b in bboxes),
        )


class HoleChunks(DataTable):
    table_format: ClassVar[KnownTableFormat] = DOWNHOLE_COLLECTION_LOCATION_HOLES
    data_columns: ClassVar[list[str]] = ["hole_index", "offset", "count"]

    @classmethod
    def _extract_chunks_table(cls, data: list[HolePath]):
        counts = [len(hole) for hole in data]
        offsets = np.cumsum([0] + counts[:-1])
        return pd.DataFrame({
            "hole_index": list(range(len(data))),
            "offset": offsets,
            "count": counts
        }).astype({
            "hole_index": np.int32,
            "offset": np.uint64,
            "count": np.uint64,
        })

    @classmethod
    async def _data_to_schema(cls, data: list[HolePath], context: IContext) -> Any:
        chunks_table = cls._extract_chunks_table(data)
        return await super()._data_to_schema(chunks_table, context)


# TODO this could be a generic model
class CategoryData(SchemaModel):
    @classmethod
    def _extract_category_table(cls, data: HoleAttributes):
        return data[["id"]].astype(np.str_)

    @classmethod
    async def _data_to_schema(cls, data: HoleAttributes, context: IContext) -> Any:
        category_table = cls._extract_category_table(data)

        from evo.objects.typed._utils import get_data_client

        data_client = get_data_client(context)
        return await data_client.upload_category_dataframe(category_table)


class PathTable(DataTable):
    table_format: ClassVar[KnownTableFormat] = FLOAT_ARRAY_3
    data_columns: ClassVar[list[str]] = ["depth", "dip", "azimuth"]


class DownholePath(DataTableAndAttributes):
    _table: Annotated[PathTable, SchemaLocation(""), DataLocation("")]

    @classmethod
    async def _data_to_schema(cls, data: list[HolePath], context: IContext) -> Any:
        combined_df = pd.concat([hole for hole in data], ignore_index=True)
        return await super()._data_to_schema(combined_df, context)


class DistancesTable(DataTable):
    table_format: ClassVar[KnownTableFormat] = FLOAT_ARRAY_3
    data_columns: ClassVar[list[str]] = ["final", "target", "current"]

    @classmethod
    def _extract_distances(cls, data: HoleAttributes) -> pd.DataFrame:
        return data[["final", "target", "current"]].astype(np.float64)

    @classmethod
    async def _data_to_schema(cls, data: HoleAttributes, context: IContext) -> Any:
        distances_df = cls._extract_distances(data)
        return await super()._data_to_schema(distances_df, context)


class CollarCoordinates(DataTable):
    table_format: ClassVar[KnownTableFormat] = FLOAT_ARRAY_3
    data_columns: ClassVar[list[str]] = _COORDINATE_COLUMNS

    @classmethod
    def _extract_coordinates(cls, data: HoleAttributes):
        return data[["x", "y", "z"]].astype(np.float64)

    @classmethod
    async def _data_to_schema(cls, data: HoleAttributes, context: IContext) -> Any:
        distances_df = cls._extract_coordinates(data)
        return await super()._data_to_schema(distances_df, context)


class DownholeLocation(SchemaModel):
    hole_id: Annotated[CategoryData, SchemaLocation("hole_id"), DataLocation("properties")]
    path: Annotated[DownholePath, SchemaLocation("path"), DataLocation("holes")]
    distances: Annotated[DistancesTable, SchemaLocation("distances"), DataLocation("properties")]
    holes: Annotated[HoleChunks, SchemaLocation("holes"), DataLocation("holes")]
    coordinates: Annotated[CollarCoordinates, SchemaLocation("coordinates"), DataLocation("properties")]
    attributes: Annotated[Attributes, SchemaLocation("attributes"), DataLocation("attributes")]


class DownholeCollections(SchemaModel):
    @classmethod
    async def _data_to_schema(cls, data: Any, context: IContext) -> Any:
        return []


class DownholeCollection(BaseSpatialObject):
    """A GeoscienceObject representing a collection of downholes."""

    _data_class = DownholeCollectionData
    sub_classification = "downhole-collection"
    creation_schema_version = SchemaVersion(major=1, minor=3, patch=1)

    location: Annotated[DownholeLocation, SchemaLocation("location"), DataLocation("")]

    # There isn't currently a workflow that requires the `collections` part of the schema. But it is a required field
    # so it has been hard-coded to an empty list (see `DownholeCollections` above).
    collections: Annotated[DownholeCollections, SchemaLocation("collections")]

    # TODO - Do these need to be handled?
    # ignoring:
    # distance_unit
    # desurvey
