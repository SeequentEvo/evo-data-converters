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
from collections import defaultdict
from os import path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from evo_schemas.components import BoundingBox_V1_0_1
from evo_schemas.objects import TriangleMesh_V2_1_0

from evo.data_converters.common import crs_from_epsg_code
import evo.data_converters.duf.common.deswik_types as dw
from evo.data_converters.duf.importer import convert_duf_polyface
from evo.data_converters.duf.importer.duf_polyface_to_evo import indices_from_polyface, combine_duf_polyfaces
from utils import extract_single_attr_value, extract_attr_values


@pytest.fixture(scope="module")
def polyface_obj(simple_objects):
    return simple_objects.get_objects_of_type(dw.Polyface)[0][1]


def test_should_convert_duf_polyface_geometry(polyface_obj, data_client):
    epsg_code = 32650
    triangle_mesh_go = convert_duf_polyface(polyface_obj, data_client, epsg_code)

    expected_triangle_mesh_go = TriangleMesh_V2_1_0(
        name="FACELAYER-dwPolyface-1c14ef99-e5e3-4388-bbe6-6120344712b1",  # layer name - type - object guid
        uuid=None,
        coordinate_reference_system=crs_from_epsg_code(epsg_code),
        bounding_box=triangle_mesh_go.bounding_box,  # Tested later
        triangles=triangle_mesh_go.triangles,  # Tested later
    )
    assert triangle_mesh_go == expected_triangle_mesh_go

    expected_bounding_box = BoundingBox_V1_0_1(
        min_x=0.0,
        max_x=10.0,
        min_y=0.0,
        max_y=10.0,
        min_z=0.0,
        max_z=0.0,
    )
    assert triangle_mesh_go.bounding_box == expected_bounding_box

    vertices_parquet_file = path.join(str(data_client.cache_location), triangle_mesh_go.triangles.vertices.data)
    indices_parquet_file = path.join(str(data_client.cache_location), triangle_mesh_go.triangles.indices.data)

    vertices = pq.read_table(vertices_parquet_file)
    indices = pq.read_table(indices_parquet_file)

    expected_vertices = np.array([[0.0, 0.0, 0.0], [0, 10.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]])
    np.testing.assert_allclose(vertices.to_pandas(), expected_vertices)

    expected_indices = np.array(
        [
            [1, 0, 2],
            [2, 3, 1],
        ]
    )
    np.testing.assert_equal(indices.to_pandas(), expected_indices)


def test_combining_duf_polyface_geometry(multiple_objects, data_client):
    epsg_code = 32650

    # Two are from the same layer. We don't always get them in the same order, so group by layer and take the largest
    polyface_objs = [obj for _, obj in multiple_objects.get_objects_of_type(dw.Polyface)]
    by_layer = defaultdict(list)
    for pf in polyface_objs:
        by_layer[pf.Layer].append(pf)
    polyface_objs = max(by_layer.values(), key=len)
    assert len(polyface_objs) == 2
    polyface_objs = sorted(polyface_objs, key=lambda pf: pf.VertexList[0].Y)  # Ensure consistent order

    triangle_mesh_go = combine_duf_polyfaces(polyface_objs, data_client, epsg_code)

    expected_triangle_mesh_go = TriangleMesh_V2_1_0(
        name="FACELAYER - polyfaces",
        uuid=None,
        coordinate_reference_system=crs_from_epsg_code(epsg_code),
        parts=triangle_mesh_go.parts,  # Tested later
        bounding_box=triangle_mesh_go.bounding_box,  # Tested later
        triangles=triangle_mesh_go.triangles,  # Tested later
    )
    assert triangle_mesh_go == expected_triangle_mesh_go

    expected_bounding_box = BoundingBox_V1_0_1(
        min_x=0.0,
        max_x=10.0,
        min_y=0.0,
        max_y=30.0,
        min_z=0.0,
        max_z=0.0,
    )
    assert triangle_mesh_go.bounding_box == expected_bounding_box

    assert triangle_mesh_go.parts is not None
    assert triangle_mesh_go.parts.chunks.length == 2  # One per polyface
    assert triangle_mesh_go.parts.chunks.width == 2  # Offset, count
    assert triangle_mesh_go.parts.chunks.data_type == "uint64"

    chunks_parquet_file = path.join(str(data_client.cache_location), triangle_mesh_go.parts.chunks.data)
    vertices_parquet_file = path.join(str(data_client.cache_location), triangle_mesh_go.triangles.vertices.data)
    indices_parquet_file = path.join(str(data_client.cache_location), triangle_mesh_go.triangles.indices.data)

    chunks = pq.read_table(chunks_parquet_file)
    vertices = pq.read_table(vertices_parquet_file)
    indices = pq.read_table(indices_parquet_file)

    # Two chunks, each with 2 triangles
    expected_chunks = np.array(
        [
            [0, 2],
            [2, 2],
        ]
    )
    np.testing.assert_equal(chunks.to_pandas(), expected_chunks)

    # Two polyfaces, each with two triangles, the second polyface has its vertices offset by 20 in Y
    expected_vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 10.0, 0.0],
            [10.0, 0.0, 0.0],
            [10.0, 10.0, 0.0],
            [0.0, 20.0, 0.0],
            [0.0, 30.0, 0.0],
            [10.0, 20.0, 0.0],
            [10.0, 30.0, 0.0],
        ]
    )
    np.testing.assert_allclose(vertices.to_pandas(), expected_vertices)

    # The second polyface has its indices offset by 4 (the number of indices in the first polyface)
    expected_indices = np.array(
        [
            [1, 0, 2],
            [2, 3, 1],
            [5, 4, 6],
            [6, 7, 5],
        ]
    )
    np.testing.assert_equal(indices.to_pandas(), expected_indices)


class MockDwFaceList:
    def __init__(self, data):
        self.data = data

    @property
    def Count(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)


def _run_indices_from_polyface_test(data, expected):
    pf = MockDwFaceList(data)
    result = indices_from_polyface(pf)
    assert np.array_equal(expected, result)


def test_indices_from_polyface_two_tris():
    two_tris = [1, 2, 3, 1, -1] + [3, 4, 5, 3, -1]
    expected = np.array([[0, 1, 2], [2, 3, 4]])
    _run_indices_from_polyface_test(two_tris, expected)


def test_indices_from_polyface_two_tris_two_quads():
    two_tris_two_quads = [1, 2, 3, 1, -1] + [4, 5, 6, 7, -1] + [2, 3, 4, 2, -1] + [7, 8, 9, 10, -1]
    expected = np.array(
        [[0, 1, 2], [3, 4, 5], [1, 2, 3], [6, 7, 8]]
        + [[5, 6, 3], [8, 9, 6]]  # The extra triangle from the quads gets added to the end
    )
    _run_indices_from_polyface_test(two_tris_two_quads, expected)


def test_indices_from_polyface_negative_indices():
    negative_indices = [-1, 2, -3, 1, -1] + [3, -4, 5, -3, -1]
    expected = np.array([[0, 1, 2], [2, 3, 4]])
    _run_indices_from_polyface_test(negative_indices, expected)


def test_indices_from_polyface_0_index():
    indices_with_0 = [0, 1, 2, 0, -1] + [2, 3, 4, 2, -1]
    expected = np.array([[1, 2, 3]])

    if __debug__:
        with pytest.raises(AssertionError):
            _run_indices_from_polyface_test(indices_with_0, expected)
    else:
        # Test this branch by running Python with `-O`
        _run_indices_from_polyface_test(indices_with_0, expected)


def test_indices_from_polyface_incomplete():
    incomplete = [1, 2, 3, 1, -1] + [4, 5]
    expected = np.array([[0, 1, 2]])

    if __debug__:
        with pytest.raises(AssertionError):
            _run_indices_from_polyface_test(incomplete, expected)
    else:
        # Test this branch by running Python with `-O`
        _run_indices_from_polyface_test(incomplete, expected)


def test_polyface_obj_attrs(pit_mesh_attrs, data_client):
    polyface = [obj for _, obj in pit_mesh_attrs.get_objects_of_type(dw.Polyface)][0]

    triangle_mesh_go = convert_duf_polyface(polyface, data_client, 12345)
    attrs = triangle_mesh_go.parts.attributes
    assert [attr.name for attr in attrs] == ["String attr", "Double attr", "Integer attr", "DateTime attr", "Choice"]
    assert [attr.attribute_type for attr in attrs] == ["category", "scalar", "integer", "date_time", "category"]

    assert extract_single_attr_value(attrs[0], data_client) == "a string value"
    assert extract_single_attr_value(attrs[1], data_client) == 3.3
    assert extract_single_attr_value(attrs[2], data_client) == 33
    assert extract_single_attr_value(attrs[3], data_client) == pd.Timestamp(
        year=2025, month=8, day=15, hour=0, minute=0, second=0, tz="UTC"
    )
    assert extract_single_attr_value(attrs[4], data_client) == "Four"


def test_combine_polyface_attrs(simple_objects_with_attrs, data_client):
    polyface_objs = [obj for _, obj in simple_objects_with_attrs.get_objects_of_type(dw.Polyface)]
    polyface_objs = sorted(polyface_objs, key=lambda pl: pl.VertexList[0].Y)  # Ensure consistent order

    triangle_mesh_go = combine_duf_polyfaces(polyface_objs, data_client, 12345)
    attrs = triangle_mesh_go.parts.attributes
    assert [attr.name for attr in attrs] == ["integer", "string", "enum"]
    assert [attr.attribute_type for attr in attrs] == ["integer", "category", "category"]

    integer_values, string_values, enum_values = [extract_attr_values(attr, data_client) for attr in attrs]

    pd.testing.assert_series_equal(integer_values, pd.Series([np.nan, 1, np.nan]), check_names=False)
    pd.testing.assert_series_equal(string_values, pd.Series(["no", "yes", "yes"]), check_index=False, check_names=False)
    pd.testing.assert_series_equal(
        enum_values, pd.Series(["three", "two", "one"]), check_index=False, check_names=False
    )
