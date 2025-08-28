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

import pytest

import evo.data_converters.duf.common.deswik_types as dw


def test_cant_create_layer_with_duplicate_name():
    """
    This test is only valid for layers which existed before loading.

    This will not fail (as of this commit):
    >>> duf.NewLayer('new_layer')
    >>> duf.NewLayer('new_layer')
    """
    duf_file = r"data/polyline_attrs_boat.duf"

    duf = dw.Duf(duf_file)

    assert duf.LayerExists("0")

    with pytest.raises(dw.ArgumentException):
        duf.NewLayer("0")

    duf.NewLayer("new_layer")

    assert duf.LayerExists("new_layer")
    with pytest.raises(dw.ArgumentException):
        duf.NewLayer("new_layer")


def test_missing_file():
    with pytest.raises(dw.ArgumentException):
        duf = dw.Duf("not_a_real_file.duf")  # noqa: F841
