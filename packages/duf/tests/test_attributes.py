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
import numpy
import pyarrow

from evo.data_converters.duf.common.attributes import EvoAttributes


def _make_evo_attributes(fetched_values, lookup_table, nan_description) -> EvoAttributes:
    return EvoAttributes(
        name="name",
        type="type",
        description="description",
        fetched_table=fetched_values,
        lookup_table=lookup_table,
        nan_description=nan_description,
    )


def test_multiple_nan_description_lookup_table_category():
    attrs = _make_evo_attributes(
        fetched_values=pyarrow.table({"values": [0, 1, 2, -1, 3, -1, 2, 1, 0]}),
        lookup_table=pyarrow.table({"key": [1, 2, 3], "value": ["a", "b", "c"]}),
        nan_description=[0, -1],
    )

    assert numpy.array_equal(attrs.nan_mask, [True, False, False, True, False, True, False, False, True])
    assert numpy.array_equal(attrs.values[~attrs.nan_mask], ["a", "b", "c", "b", "a"])


def test_nan_description_numeric():
    attrs = _make_evo_attributes(
        fetched_values=pyarrow.table({"values": [0.1, 1.1, 2.1, -1.1, 3.1, -1.1, 2.1, 1.1, 0.1]}),
        lookup_table=None,
        nan_description=[-1.1],
    )

    assert numpy.array_equal(attrs.nan_mask, [False, False, False, True, False, True, False, False, False])


def test_empty_nan_description():
    attrs = _make_evo_attributes(
        fetched_values=pyarrow.table({"values": [0.1, 1.1, 2.1, -1.1, 3.1, -1.1, 2.1, 1.1, 0.1]}),
        lookup_table=None,
        nan_description=[],
    )

    assert not numpy.any(attrs.nan_mask)


def test_none_nan_description():
    attrs = _make_evo_attributes(
        fetched_values=pyarrow.table({"values": [0.1, 1.1, 2.1, -1.1, 3.1, -1.1, 2.1, 1.1, 0.1]}),
        lookup_table=None,
        nan_description=None,
    )

    assert attrs.nan_mask is None
