#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import pytest

import evo.data_converters.duf.common.deswik_types as dw
from evo.data_converters.duf.importer.utils import AttributeSpec, AttributeType


def _published_datetimes(data_client, values):
    spec = AttributeSpec(name="d", evo_name="d", attr_type=AttributeType.DateTime)
    attr_go = spec.to_go(data_client, values)
    return [value.isoformat() for value in data_client.load_table(attr_go.values).column(0).to_pylist()]


@pytest.mark.parametrize(
    "value, expected",
    [
        (dw.DateTime(2024, 5, 6, 7, 8, 9), "2024-05-06T07:08:09+00:00"),
        (dw.DateTime(2024, 5, 6, 7, 8, 9, 123).AddTicks(4570), "2024-05-06T07:08:09.123457+00:00"),
        (dw.DateTime.MaxValue, "9999-12-31T23:59:59.999999+00:00"),  # sub-microsecond ticks are truncated
        ("2041-10-21 08:16:39", "2041-10-21T08:16:39+00:00"),
        ("2026-09-25 14:10:34Z", "2026-09-25T14:10:34+00:00"),
        (None, "1970-01-01T00:00:00+00:00"),  # null placeholder
    ],
)
def test_datetime_value_is_published_as_date_time_attribute(data_client, value, expected):
    assert _published_datetimes(data_client, [dw.DateTime(2024, 5, 6, 7, 8, 9), value])[1] == expected
