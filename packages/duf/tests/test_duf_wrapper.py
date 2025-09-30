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
from evo.data_converters.duf.common.consts import EMPTY_DUF
from evo.data_converters.duf.utils import call_private
from packages.duf.tests.consts import BOAT_DUF


@pytest.fixture(scope="function")
def duf():
    return dw.Duf(EMPTY_DUF)


@pytest.fixture(scope="function")
def boat_duf():
    return dw.Duf(BOAT_DUF)


def test_cant_create_layer_with_duplicate_name(boat_duf):
    """
    This test is only valid for layers which existed before loading.

    This will not fail (as of this commit):
    >>> duf.NewLayer('new_layer')
    >>> duf.NewLayer('new_layer')
    """
    assert boat_duf.LayerExists("0")

    with pytest.raises(dw.ArgumentException):
        boat_duf.NewLayer("0")

    boat_duf.NewLayer("new_layer")

    assert boat_duf.LayerExists("new_layer")
    with pytest.raises(dw.ArgumentException):
        boat_duf.NewLayer("new_layer")


def test_missing_file():
    with pytest.raises(dw.ArgumentException):
        duf = dw.Duf("not_a_real_file.duf")  # noqa: F841


def test_not_primary_guard(duf):
    simple_entity = dw.SimpleEntity(duf._duf, dw.Guid.NewGuid())
    with pytest.raises(dw.InvalidOperationException):
        simple_entity.Entity


def test_not_layer_guards(duf):
    layer = duf.NewLayer("new_layer")
    new_polyline = duf.NewPolyline(layer)
    with pytest.raises(dw.ArgumentException):
        dw.SimpleLayer(duf._duf, new_polyline.Guid)


def test_not_polyline_guards(duf):
    layer = duf.NewLayer("new_layer")
    with pytest.raises(dw.ArgumentException):
        new_layer = duf.NewLayer("another layer")
        dw.SimplePolyline(duf._duf, new_layer.Guid, layer.Guid)

    polyline = duf.NewPolyline(layer)
    call_private(polyline, "SetGuid", dw.Guid.NewGuid())
    with pytest.raises(dw.InvalidOperationException):
        polyline.SetVertices3D([])


def test_polyline_wrong_sized_input(duf):
    layer = duf.NewLayer("new_layer")
    polyline = duf.NewPolyline(layer)
    with pytest.raises(dw.ArgumentException):
        polyline.SetVertices3D([1.1, 2.2, 3.3, 4.4])  # Not a multiple of 3


def test_not_polyface_guards(duf):
    layer = duf.NewLayer("new_layer")
    with pytest.raises(dw.ArgumentException):
        new_layer = duf.NewLayer("another layer")
        dw.SimplePolyface(duf._duf, new_layer.Guid, layer.Guid)

    polyface = duf.NewPolyface(layer)
    call_private(polyface, "SetGuid", dw.Guid.NewGuid())
    with pytest.raises(dw.InvalidOperationException):
        polyface.SetVertices3D([], [])


def test_polyface_wrong_sized_input(duf):
    layer = duf.NewLayer("new_layer")
    polyface = duf.NewPolyface(layer)
    with pytest.raises(dw.ArgumentException):
        polyface.SetVertices3D([1.1, 2.2, 3.3, 4.4], [])  # Vertices not a multiple of 3
    with pytest.raises(dw.ArgumentException):
        polyface.SetVertices3D([], [1])  # Indices not a multiple of 3


def test_bad_attribute_type_guard(duf):
    layer = duf.NewLayer("new_layer")
    with pytest.raises(dw.ArgumentException):
        layer.AddAttribute("what", "ever")


def test_add_figure_with_non_layer_guard(duf):
    with pytest.raises(dw.ArgumentException):
        duf.NewPolyline(dw.Guid.NewGuid())


def test_get_attributes(boat_duf):
    expected_attrs = [
        "Part",
        "Date",
        "Doub",
        "Int",
        "Choice",
    ]

    layer = boat_duf.GetLayer("POLYLINE 1")
    attributes = list(layer.GetAttributes())

    for expected_attr_name, attr in zip(expected_attrs, attributes, strict=True):
        assert expected_attr_name == attr.Name
