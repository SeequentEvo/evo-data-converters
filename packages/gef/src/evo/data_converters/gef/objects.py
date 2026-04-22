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

import typing
import uuid
from dataclasses import dataclass
from typing import Annotated, ClassVar, Any, TypedDict

import numpy as np
import pandas as pd

from evo.common.interfaces import IContext
from evo.common.utils import NoFeedback
from evo.objects import SchemaVersion
from evo.objects.utils.table_formats import FLOAT_ARRAY_1, FLOAT_ARRAY_3, KnownTableFormat, \
    DOWNHOLE_COLLECTION_LOCATION_HOLES, DATE_TIME_ARRAY
from evo_schemas.elements.unit_length import UnitLength_V1_0_1_UnitCategories
from evo_schemas.elements.unit import Unit_V1_0_1

from evo.objects.typed._data import DataTable
from evo.objects.typed._utils import get_data_client
from evo.objects.typed._model import DataLocation, SchemaLocation, SchemaModel, SchemaList, SchemaBuilder
from evo.objects.typed.attributes import _infer_attribute_type_from_series, Attribute, UnSupportedDataTypeError, _attribute_table_formats
from evo.objects.typed.spatial import BaseSpatialObject, BaseSpatialObjectData
from evo.objects.typed.types import BoundingBox
from evo.objects.typed.exceptions import ObjectValidationError

__all__ = [
    "DownholeCollection",
    "DownholeCollectionData",
]

from scipy.linalg._decomp_interpolative import NDArray

_X = "x"
_Y = "y"
_Z = "z"
_COORDINATE_COLUMNS = [_X, _Y, _Z]


# type PathGeometry = pd.DataFrame
type HolePath = pd.DataFrame
type HoleChunks = pd.DataFrame
type HoleProperties = pd.DataFrame
type HoleAttributes = pd.DataFrame
type Depths = pd.DataFrame


# The below are minimal copies from evo-python-sdk. The copies were done to facilitate an experimental change to
# support units without having to deal with contributing the change upstream. The intention is to push the change
# upstream to evo-python-sdk later.


assert "date_time" not in _attribute_table_formats
_attribute_table_formats["date_time"] = [DATE_TIME_ARRAY]


def _infer_attribute_type_from_series(series: pd.Series) -> str:
    """Infer the attribute type from a Pandas Series.

    :param series: The Pandas Series to infer the attribute type from.

    :return: The inferred attribute type.
    """
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    elif pd.api.types.is_float_dtype(series):
        return "scalar"
    elif pd.api.types.is_bool_dtype(series):
        return "bool"
    elif isinstance(series.dtype, pd.CategoricalDtype):
        return "category"
    elif pd.api.types.is_string_dtype(series):
        return "string"
    elif (inferred_type := pd.api.types.infer_dtype(series, skipna=True)) in ['date', 'datetime', 'datetime64']:
        return "date_time"
    else:
        raise UnSupportedDataTypeError(f"Unsupported dtype for attribute: {series.dtype}")


class Attributes(SchemaList[Attribute]):
    """A collection of Geoscience Object Attributes"""

    _schema_path: str | None = None
    """The full JMESPath to this attributes list within the parent object schema."""

    @classmethod
    async def _data_to_schema(
        cls,
        data: Any,
        context: IContext,
    ) -> list[dict[str, Any]]:
        """Convert a DataFrame to a list of attribute dictionaries for object creation.

        :param df: The DataFrame with columns to convert to attributes, or None.
        :param context: The context used for data upload operations.
        :param fb: Optional feedback object to report progress.
        :return: A list of attribute dictionaries suitable for the object document.
        """
        result: list[dict[str, Any]] = []
        if data is not None:
            await cls._upload_attributes_to_list(result, data, context)
        return result

    @staticmethod
    async def _upload_attributes_to_list(
        attributes_list: list[dict[str, Any]],
        df: pd.DataFrame,
        context: IContext,
        fb = NoFeedback,
    ) -> None:
        """Upload DataFrame columns as attributes and append to the attributes list.

        This is a static operation that doesn't require a model instance.

        :param attributes_list: The list in the document to append attribute dicts to.
        :param df: The DataFrame with columns to upload as attributes.
        :param context: The context used for data upload operations.
        :param fb: Optional feedback object to report progress.
        """
        data_client = get_data_client(context)

        for col in df.columns:
            series = df[col]
            attribute_type = _infer_attribute_type_from_series(series)

            attr_doc: dict[str, Any] = {
                "name": str(col),
                "key": str(uuid.uuid4()),
                "attribute_type": attribute_type,
            }

            if attribute_type == "date_time":
                # TODO - Do I need to do something with the time zone?
                series = pd.to_datetime(series, utc=True).dt.as_unit("us")

                # TODO - This should be handled in _upload_attribute_values
                attr_doc["nan_description"] = {"values": []}

            col_df = pd.DataFrame({"col": series})

            # col_df = df[[col]]
            await Attribute._upload_attribute_values(attr_doc, col_df, attribute_type, data_client)

            # TODO - Is there a better way to do this?
            #  One awkward thing is that not all the attribute descriptions have all the same fields.
            attr_desc = df.attrs.get("attribute_descriptions", {}).get(col)
            if attr_desc is not None:
                if attr_desc.unit is not None:
                    attr_doc["attribute_description"] = attr_desc.to_schema()

            attributes_list.append(attr_doc)


class DataTableAndAttributes(SchemaModel):
    """A dataset representing a table of data along with associated attributes.

    Subclasses should redefine the _table property to provide additional details about the data table like:
    1. the location of it within the schema using SchemaLocation
    2. the data columns that are expected in the table, which is done by creating a subclass of DataTable,
    3. the table format used for storing the data, which can also be done by creating a subclass of DataTable.

    e.g.,
    class LocationTable(DataTable):
        table_format: ClassVar[KnownTableFormat] = FLOAT_ARRAY_3
        data_columns: ClassVar[list[str]] = ["x", "y", "z"]


    class Locations(DataTableAndAttributes):
        _table: Annotated[LocationTable, SchemaLocation("coordinates")]
    """

    attributes: Annotated[Attributes, SchemaLocation("attributes")]
    _table: DataTable

    @classmethod
    def _split_dataframe(cls, data: pd.DataFrame, data_columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        """Validate and split a DataFrame into table data and attribute data."""

        missing = set(data_columns) - set(data.columns)
        if missing:
            raise ObjectValidationError(f"Input DataFrame must have {data_columns} columns. Missing: {missing}")

        table_df = data[data_columns]
        attr_cols = [col for col in data.columns if col not in data_columns]
        attr_df = data[attr_cols] if attr_cols else None
        return table_df, attr_df

    @classmethod
    async def _data_to_schema(cls, data: Any, context: IContext) -> Any:
        if not isinstance(data, pd.DataFrame):
            raise ObjectValidationError(f"Input data must be a pandas DataFrame, but got {type(data)}")

        # Lookup the metadata of the _table sub-model, as sub-classes may redefine it
        table_metadata = cls._sub_models["_table"]
        table_type = table_metadata.model_type
        table_df, attr_df = cls._split_dataframe(data, table_type.data_columns)

        builder = SchemaBuilder(cls, context)
        await builder.set_sub_model_value("_table", table_df)
        await builder.set_sub_model_value("attributes", attr_df)
        return builder.document


# Everything below this was not copy/pasted


@dataclass
class DistanceCollection:
    name: str
    holes: HoleChunks
    distance_table: Depths
    collection_type: str = "distance"


@dataclass
class AttributeDescription:
    discipline: str = ""
    type: str = ""
    unit: Unit_V1_0_1 | None = None
    scale: str | None = None
    extensions: dict[str, typing.Any] | None = None
    tags: dict[str, str] | None = None

    def to_schema(self):
        result = {
            "discipline": self.discipline,
            "type": self.type,
        }
        if self.unit:
            result["unit"] = self.unit
        if self.scale:
            result["scale"] = self.scale
        if self.extensions:
            result["extensions"] = self.extensions
        if self.tags:
            result["tags"] = self.tags
        return result


class ColumnMapping(TypedDict):
    depth: str
    dip: str
    azimuth: str


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

    # TODO - Remove if unneeded
    column_mappings: list[ColumnMapping | None] = None

    path: HolePath
    holes: HoleChunks

    # Schema defined hole properties: hole_id, final, target, current, x, y, z
    properties: HoleProperties

    # Data-specific attributes
    attributes: HoleAttributes | None

    collections: list[DistanceCollection]

    def __post_init__(self):
        assert self.attributes is None or len(self.holes) == len(self.attributes)

    def compute_bounding_box(self) -> BoundingBox:
        bboxes = []

        for i in range(len(self.holes)):
            offset = self.holes.iat[i, 1]
            count = self.holes.iat[i, 2]
            collar = tuple(self.properties.loc[i, _COORDINATE_COLUMNS])
            path_table = self.path[offset: offset + count]
            column_mapping = None if not self.column_mappings else self.column_mappings[i]
            bboxes.append(self._compute_hole_bounding_box(path_table, collar, column_mapping))

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
        column_mapping: ColumnMapping | None,
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

        df = depths_dips_azimuths_table.dropna(subset=["distance"])

        if column_mapping is None:
            column_mapping = {"distance": "distance", "dip": "dip", "azimuth": "azimuth"}

        box = DownholeCollectionData._compute_bounding_box_np(
            df[column_mapping["distance"]].astype(float).to_numpy(),
            df[column_mapping["dip"]].astype(float).to_numpy(),
            df[column_mapping["azimuth"]].astype(float).to_numpy(),
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


class HoleChunksTable(DataTable):
    table_format: ClassVar[KnownTableFormat] = DOWNHOLE_COLLECTION_LOCATION_HOLES
    data_columns: ClassVar[list[str]] = ["hole_index", "offset", "count"]


# TODO this could be a generic model
class CategoryData(SchemaModel):
    @classmethod
    def _extract_category_table(cls, data: HoleAttributes):
        return data[["hole_id"]].astype(np.str_)

    @classmethod
    async def _data_to_schema(cls, data: HoleAttributes, context: IContext) -> Any:
        category_table = cls._extract_category_table(data)

        from evo.objects.typed._utils import get_data_client

        data_client = get_data_client(context)
        return await data_client.upload_category_dataframe(category_table)


class PathTable(DataTable):
    table_format: ClassVar[KnownTableFormat] = FLOAT_ARRAY_3
    data_columns: ClassVar[list[str]] = ["distance", "azimuth", "dip"]


class DownholePath(DataTableAndAttributes):
    _table: Annotated[PathTable, SchemaLocation(""), DataLocation("")]


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
    path: Annotated[DownholePath, SchemaLocation("path"), DataLocation("path")]
    holes: Annotated[HoleChunksTable, SchemaLocation("holes"), DataLocation("holes")]
    distances: Annotated[DistancesTable, SchemaLocation("distances"), DataLocation("properties")]
    coordinates: Annotated[CollarCoordinates, SchemaLocation("coordinates"), DataLocation("properties")]
    attributes: Annotated[Attributes, SchemaLocation("attributes"), DataLocation("attributes")]


class ColumnLengthUnits(SchemaModel):
    @classmethod
    async def _data_to_schema(cls, data: Depths, context: IContext) -> Any:
        attr_desc = data.attrs.get("attribute_descriptions", {}).get("distance")
        if attr_desc is None:
            return None
        else:
            return attr_desc.unit


class _Distances(DataTable):
    table_format: ClassVar[KnownTableFormat] = FLOAT_ARRAY_1
    data_columns: ClassVar[list[str]] = ["distance"]


class DistanceTableDistances(DataTableAndAttributes):
    _table: Annotated[_Distances, SchemaLocation("values"), DataLocation("")]
    unit: Annotated[ColumnLengthUnits, SchemaLocation("unit"), DataLocation("")]

    @classmethod
    async def _data_to_schema(cls, data: pd.DataFrame, context: IContext) -> Any:
        # TODO - Is there a better way to do this?
        result = await super()._data_to_schema(data, context)
        builder = SchemaBuilder(cls, context)
        await builder.set_sub_model_value("unit", data)
        result.update(**builder.document)
        return result


class DistanceTable(SchemaModel):
    name: Annotated[str, SchemaLocation("name"), DataLocation("name")]
    collection_type: Annotated[str, SchemaLocation("collection_type"), DataLocation("collection_type")]
    distance: Annotated[DistanceTableDistances, SchemaLocation("distance"), DataLocation("distance_table")]


class DownholeDistanceTable(DistanceTable):
    holes: Annotated[HoleChunksTable, SchemaLocation("holes"), DataLocation("holes")]


class DownholeCollectionTables(SchemaModel):
    @classmethod
    async def _data_to_schema(cls, data: list[DistanceCollection], context: IContext) -> Any:
        results = []
        for distance_collection in data:
            results.append(await DownholeDistanceTable._data_to_schema(distance_collection, context))
        return results



class DownholeCollection(BaseSpatialObject):
    """A GeoscienceObject representing a collection of downholes."""

    _data_class = DownholeCollectionData
    sub_classification = "downhole-collection"
    creation_schema_version = SchemaVersion(major=1, minor=3, patch=1)

    location: Annotated[DownholeLocation, SchemaLocation("location"), DataLocation("")]

    # There isn't currently a workflow that requires the `collections` part of the schema. But it is a required field
    # so it has been hard-coded to an empty list (see `DownholeCollections` above).
    collections: Annotated[DownholeCollectionTables, SchemaLocation("collections"), DataLocation("collections")]

    # TODO - Do these need to be handled?
    # ignoring:
    # distance_unit
    # desurvey

    @classmethod
    async def _data_to_schema(cls, data: DownholeCollectionData, context: IContext) -> dict[str, Any]:
        object_dict = await super()._data_to_schema(data, context)
        # TODO - What's the best way to do a constant?
        object_dict["type"] = "downhole"
        return object_dict
