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

from types import SimpleNamespace

import pytest

import evo.data_converters.duf.common.deswik_types as dw
from evo.data_converters.duf.importer.utils import AttributeSpec, AttributeType, value_from_xproperties
from evo.data_converters.duf.xprops import _set_xprops_csharp_value


def _entity_with_value(value):
    xproperties = dw.XProperties()
    _set_xprops_csharp_value(xproperties, "attr", [value])
    return SimpleNamespace(XProperties=xproperties)


@pytest.mark.parametrize("attr_type", [AttributeType.Integer, AttributeType.Double, AttributeType.Boolean])
def test_dotnet_datetime_in_other_attribute_type_becomes_null(attr_type):
    entity = _entity_with_value(dw.DateTime(2024, 5, 6))

    assert value_from_xproperties(entity, "attr", attr_type) is None


def test_dotnet_datetime_is_kept_for_datetime_attribute():
    entity = _entity_with_value(dw.DateTime(2024, 5, 6))

    assert value_from_xproperties(entity, "attr", AttributeType.DateTime) is not None


@pytest.mark.parametrize(
    "value, expected",
    [
        (dw.DateTime(2024, 5, 6, 7, 8, 9), "2024-05-06T07:08:09+00:00"),
        (dw.DateTime(2024, 5, 6, 7, 8, 9, 123).AddTicks(4570), "2024-05-06T07:08:09.123457+00:00"),
        (dw.DateTime.MaxValue, "9999-12-31T23:59:59.999999+00:00"),  # sub-microsecond ticks are truncated
        (None, "1970-01-01T00:00:00+00:00"),  # null placeholder
    ],
)
def test_dotnet_datetime_is_published_as_date_time_attribute(value, expected):
    saved = []

    def save_table(table):
        saved.append(table)
        return {"data": "0" * 64, "length": table.num_rows, "data_type": "timestamp"}

    data_client = SimpleNamespace(save_table=save_table)
    spec = AttributeSpec(name="d", evo_name="d", attr_type=AttributeType.DateTime)

    spec.to_go(data_client, [dw.DateTime(2024, 5, 6, 7, 8, 9), value])

    assert saved[0].to_pydict()["n0"][1].isoformat() == expected
