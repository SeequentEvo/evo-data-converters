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

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import numpy as np
import pyarrow as pa
from evo_schemas.components import (
    CategoryAttribute_V1_0_1,
    CategoryAttribute_V1_1_0,
    ColorAttribute_V1_0_0,
    ColorAttribute_V1_1_0,
    ContinuousAttribute_V1_0_1,
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_0_1,
    DateTimeAttribute_V1_1_0,
    IntegerAttribute_V1_0_1,
    IntegerAttribute_V1_1_0,
    OneOfAttribute_V1_1_0,
    OneOfAttribute_V1_2_0,
    StringAttribute_V1_0_1,
    StringAttribute_V1_1_0,
    VectorAttribute_V1_0_0,
)
from omf.base import ProjectElementData
from omf.data import ColorData, DateTimeData, Legend, MappedData, ScalarData, StringData, Vector2Data, Vector3Data

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from ..importer.omf_attributes_to_evo import int_to_rgba

logger = evo.logging.getLogger("data_converters")

# Evo parquet files can contain null values. As OMF v1 doesn't allow using None
# as an attribute value they are replaced with the values below:
NULL_INTEGER_VALUE = -9223372036854775807  # minimum 64-bit signed integer
NULL_VALUE_COLOR = [0, 0, 0]
NULL_DATETIME = datetime(1, 1, 1, tzinfo=timezone.utc)


def stringify_attribute_description(attribute_go: OneOfAttribute_V1_1_0 | OneOfAttribute_V1_2_0) -> str:
    descriptions = []
    if attribute_go.attribute_description:
        descriptions.append(
            f"discipline: {attribute_go.attribute_description.discipline}, type: {attribute_go.attribute_description.type}"
        )
        if attribute_go.attribute_description.unit:
            descriptions.append(f"unit: {attribute_go.attribute_description.unit}")
        if attribute_go.attribute_description.scale:
            descriptions.append(f"scale: {attribute_go.attribute_description.scale}")
        if attribute_go.attribute_description.tags:
            descriptions.append(f"tags: {attribute_go.attribute_description.tags}")
    if hasattr(attribute_go, "nan_description") and attribute_go.nan_description:
        if attribute_go.nan_description.values:
            descriptions.append(f"NaN values: {attribute_go.nan_description.values}")

    description = ", ".join(descriptions)
    return description


def export_omf_attributes(
    object_id: UUID,
    object_version: Optional[str],
    attributes_go: Optional[OneOfAttribute_V1_1_0 | OneOfAttribute_V1_2_0],
    location: str,
    data_client: ObjectDataClient,
) -> list[ProjectElementData]:
    omf_attributes: list[ProjectElementData] = []

    if not attributes_go:
        return omf_attributes

    for attribute_go in attributes_go:
        omf_attribute = export_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)
        if omf_attribute:
            omf_attributes.append(omf_attribute)

    return omf_attributes


def export_continuous_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: ContinuousAttribute_V1_0_1 | ContinuousAttribute_V1_1_0,
    location: str,
    data_client: ObjectDataClient,
) -> ScalarData:
    values_table = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.values.as_dict()))

    values = np.array(values_table[0])

    # Convert nan_description values to NaN
    # NOTE: Numpy will also convert any None values in the array to NaN
    if attribute_go.nan_description.values:
        nan_indices = np.isin(values, attribute_go.nan_description.values)
        values[nan_indices] = np.nan

    description = stringify_attribute_description(attribute_go)

    return ScalarData(name=attribute_go.name, location=location, array=values, description=description)


def export_integer_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: IntegerAttribute_V1_0_1 | IntegerAttribute_V1_1_0,
    location: str,
    data_client: ObjectDataClient,
) -> ScalarData:
    values_table = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.values.as_dict()))
    values = np.array(values_table[0].fill_null(NULL_INTEGER_VALUE), np.int64)

    # NOTE: Values matching the nan_description values are just passed through
    description = stringify_attribute_description(attribute_go)

    return ScalarData(name=attribute_go.name, location=location, array=values, description=description)


def export_category_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: CategoryAttribute_V1_0_1 | CategoryAttribute_V1_1_0,
    location: str,
    data_client: ObjectDataClient,
) -> MappedData:
    key_value_table = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.table.as_dict()))
    values_table = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.values.as_dict()))

    # Convert nulls to -1
    values = np.array(values_table[0].fill_null(-1), dtype=int)

    # Convert nan_description values to -1
    if attribute_go.nan_description.values:
        nan_indices = np.isin(values, attribute_go.nan_description.values)
        values[nan_indices] = -1

    description = stringify_attribute_description(attribute_go)

    table_keys = key_value_table["key"]
    table_values = key_value_table["value"]

    legend = Legend(name=attribute_go.name, description="", values=table_values.to_pylist())

    # Category attribute values are keys in the category attribute table. Convert them to indices.
    indices_array = [table_keys.index(key).as_py() if key != -1 else -1 for key in values]

    return MappedData(
        name=attribute_go.name, location=location, legends=[legend], array=indices_array, description=description
    )


def export_color_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: ColorAttribute_V1_0_0 | ColorAttribute_V1_1_0,
    location: str,
    data_client: ObjectDataClient,
) -> ColorData:
    rgba_int_colors = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.values.as_dict()))

    # Convert 0xAABBGGRR unsigned integers to rgba components and drop the alpha component
    rgb_colors = [
        int_to_rgba(color)[:3] if color is not None else NULL_VALUE_COLOR for color in rgba_int_colors[0].to_pylist()
    ]

    description = stringify_attribute_description(attribute_go)

    return ColorData(name=attribute_go.name, location=location, array=rgb_colors, description=description)


def export_string_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: StringAttribute_V1_0_1 | StringAttribute_V1_1_0,
    location: str,
    data_client: ObjectDataClient,
) -> StringData:
    strings_table = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.values.as_dict()))

    strings: list[str] = []
    for string in strings_table[0].to_pylist():
        # None is not allowed so replace them with empty strings
        if string is None:
            string = ""
        strings.append(string)

    description = stringify_attribute_description(attribute_go)

    return StringData(name=attribute_go.name, location=location, array=strings, description=description)


def export_vector_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: VectorAttribute_V1_0_0,
    location: str,
    data_client: ObjectDataClient,
) -> Optional[Vector2Data | Vector3Data]:
    vectors_table = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.values.as_dict()))

    vectors = np.asarray(vectors_table)

    # Convert nan_description values to NaN
    if attribute_go.nan_description.values:
        nan_indices = np.isin(vectors, attribute_go.nan_description.values)
        vectors[nan_indices] = np.nan

    description = stringify_attribute_description(attribute_go)

    dimensions = vectors.shape[1]

    if dimensions == 2:
        return Vector2Data(name=attribute_go.name, location=location, array=vectors, description=description)
    elif dimensions == 3:
        return Vector3Data(name=attribute_go.name, location=location, array=vectors, description=description)

    logger.warning(f"Skipping vector attribute with {dimensions} dimensions")
    return None


def export_datetime_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: DateTimeAttribute_V1_1_0 | DateTimeAttribute_V1_0_1,
    location: str,
    data_client: ObjectDataClient,
) -> DateTimeData:
    datetimes_table = asyncio.run(data_client.download_table(object_id, object_version, attribute_go.values.as_dict()))

    timestamps = datetimes_table[0].fill_null(pa.scalar(NULL_DATETIME))

    # NOTE: Values matching the nan_description values are just passed through
    description = stringify_attribute_description(attribute_go)

    return DateTimeData(
        name=attribute_go.name, location=location, array=timestamps.to_pylist(), description=description
    )


def export_attribute_to_omf(
    object_id: UUID,
    object_version: Optional[str],
    attribute_go: OneOfAttribute_V1_1_0,
    location: str,
    data_client: ObjectDataClient,
) -> Optional[ProjectElementData]:
    match attribute_go:
        case ColorAttribute_V1_0_0() | ColorAttribute_V1_1_0():
            return export_color_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)
        case CategoryAttribute_V1_0_1() | CategoryAttribute_V1_1_0():
            return export_category_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)
        case ContinuousAttribute_V1_0_1() | ContinuousAttribute_V1_1_0():
            return export_continuous_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)
        case IntegerAttribute_V1_1_0() | IntegerAttribute_V1_0_1():
            return export_integer_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)
        case DateTimeAttribute_V1_1_0() | DateTimeAttribute_V1_0_1():
            return export_datetime_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)
        case StringAttribute_V1_0_1() | StringAttribute_V1_1_0():
            return export_string_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)
        case VectorAttribute_V1_0_0():
            return export_vector_attribute_to_omf(object_id, object_version, attribute_go, location, data_client)

    logger.warning(f"Skipping unsupported attribute type '{attribute_go.__class__.__name__}'")
    return None
