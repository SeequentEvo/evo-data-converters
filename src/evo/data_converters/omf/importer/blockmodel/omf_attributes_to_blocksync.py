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

from typing import Optional

import numpy as np
import omf2
import pyarrow as pa
from pandas.api.types import is_datetime64_dtype

import evo.logging

logger = evo.logging.getLogger("data_converters")

ILLEGAL_ATTRIBUTE_NAMES = ["i", "j", "k", "sidx", "start_si", "start_sj", "start_sk", "end_si", "end_sj", "end_sk"]


def convert_omf_blockmodel_attributes_to_columns(
    blockmodel: omf2.Element, reader: omf2.Reader, table: pa.Table, location: omf2.Location
) -> pa.Table:
    for attribute in blockmodel.attributes():
        if attribute.location != location:
            if location == omf2.Location.Subblocks and attribute.location == omf2.Location.Primitives:
                logger.warning(f"Skipping unsupported parent block model attribute '{attribute.name}'")
            continue

        attribute_table = convert_blockmodel_attribute(reader, attribute, table.column_names)
        if attribute_table:
            for column_name in attribute_table.column_names:
                table = table.append_column(column_name, attribute_table.column(column_name))

    return table


def _unique_attribute_name(attribute_name: str, used_column_names: list[str]) -> str:
    # If the name clashes with a reserved column name add 'data' prefix to distinguish it
    if attribute_name in ILLEGAL_ATTRIBUTE_NAMES:
        attribute_name = f"data_{attribute_name}"

    # Make sure the column name is unique by adding a unique suffix if it isn't
    unique_name = attribute_name
    unique_suffix = 1

    while unique_name in used_column_names:
        unique_name = f"{attribute_name}_{unique_suffix}"
        unique_suffix += 1

    return unique_name


def convert_blockmodel_attribute(
    reader: omf2.Reader, attribute: omf2.Attribute, used_column_names: list[str] = []
) -> Optional[pa.Table]:
    attribute_data = attribute.get_data()

    attribute_name = _unique_attribute_name(attribute.name, used_column_names)

    if isinstance(attribute_data, omf2.AttributeDataCategory):
        indices, null_mask = reader.array_indices(attribute_data.values)
        names = reader.array_names(attribute_data.names)
        index_names = [None if null_mask[i] else names[value] for i, value in enumerate(indices)]
        return pa.Table.from_arrays(
            [pa.array(index_names)],
            schema=pa.schema(
                [
                    (attribute_name, pa.string()),
                ]
            ),
        )

    elif isinstance(attribute_data, omf2.AttributeDataBoolean):
        booleans, null_mask = reader.array_booleans(attribute_data.values)
        return pa.Table.from_arrays(
            [pa.array(booleans, mask=null_mask)],
            schema=pa.schema(
                [
                    (attribute_name, pa.bool_()),
                ]
            ),
        )

    elif isinstance(attribute_data, omf2.AttributeDataNumber):
        numbers, null_mask = reader.array_numbers(attribute_data.values)
        match numbers.dtype:
            case dtype if dtype == np.dtype("datetime64[D]"):
                return pa.Table.from_arrays(
                    [pa.array(numbers, mask=null_mask)],
                    schema=pa.schema(
                        [
                            (attribute_name, pa.date32()),
                        ]
                    ),
                )

            case dtype if is_datetime64_dtype(dtype):
                return pa.Table.from_arrays(
                    [pa.array(numbers, mask=null_mask)],
                    schema=pa.schema(
                        [
                            (attribute_name, pa.timestamp("us", tz="UTC")),
                        ]
                    ),
                )
            case _:
                return pa.Table.from_arrays(
                    [pa.array(numbers, mask=null_mask)],
                    schema=pa.schema(
                        [
                            (attribute_name, pa.float64()),
                        ]
                    ),
                )

    else:
        logger.warning(f"Skipping unsupported OMF attribute data type: {attribute_data.__class__.__name__}")

    return None
