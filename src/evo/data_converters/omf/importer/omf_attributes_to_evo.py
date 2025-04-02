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

import struct
from typing import Optional
from uuid import uuid4

import numpy as np
import numpy.typing as npt
import omf2
import pandas as pd
import pyarrow as pa
from evo_schemas.components import (
    BoolAttribute_V1_1_0,
    CategoryAttribute_V1_1_0,
    ColorAttribute_V1_1_0,
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_1_0,
    IntegerAttribute_V1_1_0,
    NanCategorical_V1_0_1,
    NanContinuous_V1_0_1,
    OneOfAttribute_V1_2_0,
    OneOfAttribute_V1_2_0_Item,
    StringAttribute_V1_1_0,
    VectorAttribute_V1_0_0,
)
from evo_schemas.elements import (
    BoolArray1_V1_0_1,
    ColorArray_V1_0_1,
    DateTimeArray_V1_0_1,
    FloatArray1_V1_0_1,
    FloatArrayMd_V1_0_1,
    IntegerArray1_V1_0_1,
    LookupTable_V1_0_1,
    StringArray_V1_0_1,
)
from pandas.api.types import is_datetime64_dtype

import evo.logging
from evo.objects.utils.data import ObjectDataClient

logger = evo.logging.getLogger("data_converters")


def convert_omf_attributes(
    element: omf2.Element,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
    attribute_location: omf2.Location,
) -> OneOfAttribute_V1_2_0:
    attributes_go = []

    for attribute in element.attributes():
        if attribute.location != attribute_location:
            continue

        attribute_go = convert_omf_attribute(attribute, reader, data_client)
        if attribute_go:
            attributes_go.append(attribute_go)

    return attributes_go


def rgba_to_int(rgba: npt.NDArray[np.int_]) -> np.uint32:
    r"""
    Convert RGBA components to 0xAABBGGRR format integer.
    """
    (color,) = struct.unpack("<I", bytes(rgba))
    return np.uint32(color)


def int_to_rgba(color: int) -> list[int]:
    r"""
    Convert color in 0xAABBGGRR integer format to RGBA components.
    """
    r = color & 0xFF
    g = (color >> 8) & 0xFF
    b = (color >> 16) & 0xFF
    a = (color >> 24) & 0xFF
    return [r, g, b, a]


def int_to_rgba_optional(color: Optional[int]) -> Optional[list[int]]:
    r"""
    Convert optional color in 0xAABBGGRR integer format to RGBA components.
    """
    if color is None:
        return None

    return int_to_rgba(color)


def convert_omf_number_attribute(
    attribute_name: str,
    attribute_data: omf2.AttributeDataNumber,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
) -> OneOfAttribute_V1_2_0_Item:
    numbers, null_mask = reader.array_numbers(attribute_data.values)
    match numbers.dtype:
        case np.float32 | np.float64:
            # No evo object schemas expect float32, so ensure the array is of
            # type float64.
            table = pa.Table.from_arrays([pa.array(numbers, type=pa.float64(), mask=null_mask)], names=["data"])
            array_args = data_client.save_table(table)
            array = FloatArray1_V1_0_1.from_dict(array_args)

            return ContinuousAttribute_V1_1_0(
                name=attribute_name,
                key=str(uuid4()),
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=array,
            )
        case np.int64:
            table = pa.Table.from_arrays([pa.array(numbers, mask=null_mask)], names=["data"])
            array_args = data_client.save_table(table)
            array = IntegerArray1_V1_0_1.from_dict(array_args)

            return IntegerAttribute_V1_1_0(
                name=attribute_name,
                key=str(uuid4()),
                nan_description=NanCategorical_V1_0_1(values=[]),
                values=array,
            )
        case dtype if dtype == np.dtype("datetime64[D]"):
            # Evo lacks a type to represent Dates, so convert them to strings.
            table = pa.Table.from_arrays(
                [pa.array(numbers, mask=null_mask)],
                schema=pa.schema(
                    [
                        ("data", pa.string()),
                    ]
                ),
            )
            array_args = data_client.save_table(table)
            array = StringArray_V1_0_1.from_dict(array_args)

            return StringAttribute_V1_1_0(
                name=attribute_name,
                key=str(uuid4()),
                values=array,
            )
        case dtype if is_datetime64_dtype(dtype):
            # Other datetimes can be represented with DateTimeAttribute.
            table = pa.Table.from_arrays(
                [pa.array(numbers, mask=null_mask)],
                schema=pa.schema(
                    [
                        ("data", pa.timestamp("us", tz="UTC")),
                    ]
                ),
            )
            array_args = data_client.save_table(table)
            array = DateTimeArray_V1_0_1.from_dict(array_args)

            return DateTimeAttribute_V1_1_0(
                name=attribute_name,
                key=str(uuid4()),
                nan_description=NanCategorical_V1_0_1(values=[]),
                values=array,
            )
        case _:
            raise AssertionError(f"unknown dtype {numbers.dtype}!")


def convert_omf_category_attribute(
    attribute_name: str,
    attribute_data: omf2.AttributeDataCategory,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
) -> CategoryAttribute_V1_1_0:
    indices, null_mask = reader.array_indices(attribute_data.values)

    names = reader.array_names(attribute_data.names)
    table_df = pd.DataFrame({"value": names}).reset_index(names="key")

    schema = pa.schema(
        [
            ("key", pa.int64()),
            ("value", pa.string()),
        ]
    )
    table = pa.Table.from_pandas(table_df, schema=schema)
    lookup_table_args = data_client.save_table(table)
    lookup_table_go = LookupTable_V1_0_1.from_dict(lookup_table_args)

    schema = pa.schema([("data", pa.int64())])
    table = pa.Table.from_arrays([pa.array(indices, mask=null_mask)], schema=schema)
    integer_array_args = data_client.save_table(table)
    integer_array_go = IntegerArray1_V1_0_1.from_dict(integer_array_args)

    return CategoryAttribute_V1_1_0(
        name=attribute_name,
        key=str(uuid4()),
        nan_description=NanCategorical_V1_0_1(values=[]),
        table=lookup_table_go,
        values=integer_array_go,
    )


def convert_omf_text_attribute(
    attribute_name: str,
    attribute_data: omf2.AttributeDataText,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
) -> StringAttribute_V1_1_0:
    schema_dtype = pa.string()
    schema = pa.schema(
        [
            ("data", schema_dtype),
        ]
    )
    table = pa.Table.from_arrays([pa.array(reader.array_text(attribute_data.values))], schema=schema)
    string_array_args = data_client.save_table(table)
    string_array = StringArray_V1_0_1.from_dict(string_array_args)

    return StringAttribute_V1_1_0(
        name=attribute_name,
        key=str(uuid4()),
        values=string_array,
    )


def convert_omf_boolean_attribute(
    attribute_name: str,
    attribute_data: omf2.AttributeDataBoolean,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
) -> BoolAttribute_V1_1_0:
    booleans, null_mask = reader.array_booleans(attribute_data.values)
    schema_dtype = pa.bool_()
    schema = pa.schema(
        [
            ("data", schema_dtype),
        ]
    )
    table = pa.Table.from_arrays([pa.array(booleans, mask=null_mask)], schema=schema)
    boolean_array_args = data_client.save_table(table)
    boolean_array = BoolArray1_V1_0_1.from_dict(boolean_array_args)

    return BoolAttribute_V1_1_0(
        name=attribute_name,
        key=str(uuid4()),
        values=boolean_array,
    )


def convert_omf_color_attribute(
    attribute_name: str,
    attribute_data: omf2.AttributeDataColor,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
) -> ColorAttribute_V1_1_0:
    schema_dtype = pa.uint32()
    schema = pa.schema(
        [
            ("data", schema_dtype),
        ]
    )

    # Convert RGBA colors to 0xAABBGGRR unsigned integers
    rgba_colors, null_mask = reader.array_color(attribute_data.values)
    uint32_colors = np.apply_along_axis(rgba_to_int, 1, rgba_colors)
    table = pa.Table.from_arrays([pa.array(uint32_colors, mask=null_mask)], schema=schema)

    color_array_args = data_client.save_table(table)
    color_array = ColorArray_V1_0_1.from_dict(color_array_args)

    return ColorAttribute_V1_1_0(
        name=attribute_name,
        key=str(uuid4()),
        values=color_array,
    )


def convert_omf_vector_attribute(
    attribute_name: str,
    attribute_data: omf2.AttributeDataVector,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
) -> VectorAttribute_V1_0_0:
    schema_dtype = pa.float64()

    vectors, null_vectors_mask = reader.array_vectors(attribute_data.values)

    dimensions = vectors.shape[1]

    if dimensions == 2:
        schema = pa.schema(
            [
                pa.field("x", schema_dtype),
                pa.field("y", schema_dtype),
            ]
        )
    elif dimensions == 3:
        schema = pa.schema(
            [
                pa.field("x", schema_dtype),
                pa.field("y", schema_dtype),
                pa.field("z", schema_dtype),
            ]
        )
    else:
        raise AssertionError(f"unexpected number of vector dimensions {dimensions}!")

    vectors_table = pa.Table.from_arrays(
        [pa.array(vectors[:, i], type=schema_dtype, mask=null_vectors_mask) for i in range(dimensions)],
        schema=schema,
    )

    float_array_md_args = data_client.save_table(vectors_table)
    float_array_md = FloatArrayMd_V1_0_1.from_dict(float_array_md_args)

    return VectorAttribute_V1_0_0(
        name=attribute_name,
        key=str(uuid4()),
        nan_description=NanContinuous_V1_0_1(values=[]),
        values=float_array_md,
    )


def convert_omf_attribute(
    attribute: omf2.Attribute, reader: omf2.Reader, data_client: ObjectDataClient
) -> Optional[OneOfAttribute_V1_2_0_Item]:
    attribute_data = attribute.get_data()

    match attribute_data:
        case omf2.AttributeDataNumber():
            return convert_omf_number_attribute(attribute.name, attribute_data, reader, data_client)
        case omf2.AttributeDataCategory():
            return convert_omf_category_attribute(attribute.name, attribute_data, reader, data_client)
        case omf2.AttributeDataText():
            return convert_omf_text_attribute(attribute.name, attribute_data, reader, data_client)
        case omf2.AttributeDataBoolean():
            return convert_omf_boolean_attribute(attribute.name, attribute_data, reader, data_client)
        case omf2.AttributeDataColor():
            return convert_omf_color_attribute(attribute.name, attribute_data, reader, data_client)
        case omf2.AttributeDataVector():
            return convert_omf_vector_attribute(attribute.name, attribute_data, reader, data_client)

    logger.warning(f"Skipping unsupported OMF attribute data type '{attribute_data.__class__.__name__}'")
    return None
