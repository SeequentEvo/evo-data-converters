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

from datetime import datetime, timezone
from os import path
from typing import Any, TypeAlias

import pyarrow.parquet as pq
import pytest
from evo.objects.utils import ObjectDataClient
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_1_0,
    IntegerAttribute_V1_1_0,
    NanCategorical_V1_0_1,
    NanContinuous_V1_0_1,
    StringAttribute_V1_1_0,
    OneOfAttribute_V1_2_0_Item,
)
from evo_schemas.elements import (
    DateTimeArray_V1_0_1,
    FloatArray1_V1_0_1,
    IntegerArray1_V1_0_1,
    StringArray_V1_0_1,
)

from evo.data_converters.duf.importer.duf_attributes_to_evo import (
    convert_duf_single_value_attributes,
    convert_duf_single_value_attribute,
)

Array_T: TypeAlias = DateTimeArray_V1_0_1 | FloatArray1_V1_0_1 | IntegerArray1_V1_0_1 | StringArray_V1_0_1
NaN_T: TypeAlias = NanCategorical_V1_0_1 | NanContinuous_V1_0_1


params = [
    pytest.param(
        "party time",
        datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        None,
        DateTimeAttribute_V1_1_0,
        DateTimeArray_V1_0_1,
        "timestamp",
        NanCategorical_V1_0_1,
        id="datetime",
    ),
    pytest.param(
        "later party time",
        datetime(2999, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat(),
        datetime(2999, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        DateTimeAttribute_V1_1_0,
        DateTimeArray_V1_0_1,
        "timestamp",
        NanCategorical_V1_0_1,
        id="datetime_str",
    ),
    pytest.param(
        "integer", 12345, None, IntegerAttribute_V1_1_0, IntegerArray1_V1_0_1, "int64", NanCategorical_V1_0_1, id="int"
    ),
    pytest.param(
        "floating",
        123.45,
        None,
        ContinuousAttribute_V1_1_0,
        FloatArray1_V1_0_1,
        "float64",
        NanContinuous_V1_0_1,
        id="float",
    ),
    pytest.param("string", "stringy thing", None, StringAttribute_V1_1_0, StringArray_V1_0_1, "string", None, id="str"),
]


@pytest.mark.parametrize("key, attr, expected_value, attr_cls, attr_array_cls, array_data_type, nan_cls", params)
def test_convert_sv_attr(
    data_client: ObjectDataClient,
    key: str,
    attr: Any,
    expected_value: Any,
    attr_cls: type[OneOfAttribute_V1_2_0_Item],
    attr_array_cls: type[Array_T],
    array_data_type: str,
    nan_cls: type[NaN_T] | None,
) -> None:
    attribute_go = convert_duf_single_value_attribute(("party time", attr), data_client)

    assert isinstance(attribute_go, attr_cls)

    kwargs = {
        "name": "party time",
        "key": "party time",
        "values": attr_array_cls(data=attribute_go.values.data, data_type=array_data_type, length=1),
    }
    if nan_cls is not None:
        kwargs["nan_description"] = nan_cls(values=[])

    expected_attribute = attr_cls(**kwargs)
    assert expected_attribute == attribute_go

    parquet_file = path.join(str(data_client.cache_location), attribute_go.values.data)
    table = pq.read_table(parquet_file)

    expected_value = attr if expected_value is None else expected_value

    assert [expected_value] == table.column("n0").to_pylist()


def test_convert_list_of_sv_attrs(
    data_client: ObjectDataClient,
):
    attrs_to_pass = []
    expected_attrs = []
    expected_values = []

    for param in params:
        key, attr, expected_value, attr_cls, attr_array_cls, array_data_type, nan_cls = param.values
        attrs_to_pass.append((key, attr))

        expected_value = param.values[2]
        expected_value = attr if expected_value is None else expected_value
        expected_values.append(expected_value)

        kwargs = {
            "name": key,
            "key": key,
            "values": attr_array_cls(data=None, data_type=array_data_type, length=1),
        }
        if nan_cls is not None:
            kwargs["nan_description"] = nan_cls(values=[])
        expected_attrs.append(attr_cls(**kwargs))

    result = convert_duf_single_value_attributes(attrs_to_pass, data_client)

    assert len(result) == len(expected_attrs)

    for attribute_go, expected_attr, expected_value in zip(result, expected_attrs, expected_values):
        assert isinstance(attribute_go, type(expected_attr))

        expected_attr.values.data = attribute_go.values.data  # Unknown before creation so update now
        assert attribute_go == expected_attr

        parquet_file = path.join(str(data_client.cache_location), attribute_go.values.data)
        table = pq.read_table(parquet_file)

        assert [expected_value] == table.column("n0").to_pylist()
