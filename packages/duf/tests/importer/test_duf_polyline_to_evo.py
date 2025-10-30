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
from evo_schemas.objects import LineSegments_V2_1_0

from evo.data_converters.common import crs_from_epsg_code
import evo.data_converters.duf.common.deswik_types as dw
from evo.data_converters.duf.importer import convert_duf_polyline
from evo.data_converters.duf.importer.duf_polyline_to_evo import combine_duf_polylines
from utils import extract_single_attr_value, extract_attr_values


@pytest.fixture(scope="module")
def polyline_obj(simple_objects):
    return simple_objects.get_objects_of_type(dw.Polyline)[0][1]


def test_should_convert_duf_polyline_geometry(polyline_obj, data_client):
    epsg_code = 32650
    line_segments_go = convert_duf_polyline(polyline_obj, data_client, epsg_code)

    expected_line_segments_go = LineSegments_V2_1_0(
        name="0-dwPolyline-f83a4e34-0428-431c-aed7-c554febcbc4a",  # layer name - type - object guid
        uuid=None,
        coordinate_reference_system=crs_from_epsg_code(epsg_code),
        bounding_box=line_segments_go.bounding_box,  # Tested later
        segments=line_segments_go.segments,  # Tested later
    )
    assert line_segments_go == expected_line_segments_go

    expected_bounding_box = BoundingBox_V1_0_1(
        min_x=2.0,
        max_x=5.0,
        min_y=2.0,
        max_y=5.0,
        min_z=2.0,
        max_z=5.0,
    )
    assert line_segments_go.bounding_box == expected_bounding_box

    vertices_parquet_file = path.join(str(data_client.cache_location), line_segments_go.segments.vertices.data)
    indices_parquet_file = path.join(str(data_client.cache_location), line_segments_go.segments.indices.data)

    vertices = pq.read_table(vertices_parquet_file)
    indices = pq.read_table(indices_parquet_file)

    expected_vertices = np.array([[2.0, 2.0, 2.0], [2.0, 4.0, 5.0], [5.0, 5.0, 5.0]])
    np.testing.assert_allclose(vertices.to_pandas(), expected_vertices)

    expected_indices = np.array(
        [
            [0, 1],
            [1, 2],
        ]
    )
    np.testing.assert_equal(indices.to_pandas(), expected_indices)


def test_combining_duf_polyline_geometry(multiple_objects, data_client):
    epsg_code = 32650

    # Two are from the same layer. We don't always get them in the same order, so group by layer and take the largest
    polyline_objs = [obj for _, obj in multiple_objects.get_objects_of_type(dw.Polyline)]
    by_layer = defaultdict(list)
    for pl in polyline_objs:
        by_layer[pl.Layer].append(pl)
    polyline_objs = max(by_layer.values(), key=len)
    assert len(polyline_objs) == 2
    polyline_objs = sorted(polyline_objs, key=lambda pl: pl.VertexList[0].X)  # Ensure consistent order

    line_segments_go = combine_duf_polylines(polyline_objs, data_client, epsg_code)

    expected_line_segments_go = LineSegments_V2_1_0(
        name="LINELAYER - polylines",
        uuid=None,
        coordinate_reference_system=crs_from_epsg_code(epsg_code),
        parts=line_segments_go.parts,  # Tested later
        bounding_box=line_segments_go.bounding_box,  # Tested later
        segments=line_segments_go.segments,  # Tested later
    )
    assert line_segments_go == expected_line_segments_go

    expected_bounding_box = BoundingBox_V1_0_1(
        min_x=2.0,
        max_x=15.0,
        min_y=2.0,
        max_y=5.0,
        min_z=2.0,
        max_z=5.0,
    )
    assert line_segments_go.bounding_box == expected_bounding_box

    assert line_segments_go.parts is not None
    assert line_segments_go.parts.chunks.length == 2  # One per polyline
    assert line_segments_go.parts.chunks.width == 2  # Offset, count
    assert line_segments_go.parts.chunks.data_type == "uint64"

    chunks_parquet_file = path.join(str(data_client.cache_location), line_segments_go.parts.chunks.data)
    vertices_parquet_file = path.join(str(data_client.cache_location), line_segments_go.segments.vertices.data)
    indices_parquet_file = path.join(str(data_client.cache_location), line_segments_go.segments.indices.data)

    chunks = pq.read_table(chunks_parquet_file)
    vertices = pq.read_table(vertices_parquet_file)
    indices = pq.read_table(indices_parquet_file)

    # Two chunks, each with 2 segments
    expected_chunks = np.array(
        [
            [0, 2],
            [2, 2],
        ]
    )
    np.testing.assert_equal(chunks.to_pandas(), expected_chunks)

    # Two polylines, each with two segments, the second polyline has its vertices offset by 10 in X
    expected_vertices = np.array(
        [
            [2.0, 2.0, 2.0],
            [2.0, 4.0, 5.0],
            [5.0, 5.0, 5.0],
            [12.0, 2.0, 2.0],
            [12.0, 4.0, 5.0],
            [15.0, 5.0, 5.0],
        ]
    )
    np.testing.assert_allclose(vertices.to_pandas(), expected_vertices)

    # The second polyline has its indices offset by 3 (the number of indices in the first polyline)
    expected_indices = np.array(
        [
            [0, 1],
            [1, 2],
            [3, 4],
            [4, 5],
        ]
    )
    np.testing.assert_equal(indices.to_pandas(), expected_indices)


def test_polyline_obj_attrs(polyline_attrs_boat, data_client):
    polyline_objs = [obj for _, obj in polyline_attrs_boat.get_objects_of_type(dw.Polyline)]
    polyline_objs = sorted(polyline_objs, key=lambda pl: pl.VertexList[0].X)  # Ensure consistent order

    line_segments_gos = [convert_duf_polyline(pl, data_client, 12345) for pl in polyline_objs]
    all_attrs = [ls.parts.attributes for ls in line_segments_gos]
    for attrs in all_attrs:
        assert [attr.name for attr in attrs] == ["Part", "Date", "Doub", "Int", "Choice"]
        assert [attr.attribute_type for attr in attrs] == ["category", "date_time", "scalar", "integer", "category"]

    part_values = [extract_single_attr_value(attrs[0], data_client) for attrs in all_attrs]
    datetime_values = [extract_single_attr_value(attrs[1], data_client) for attrs in all_attrs]
    doub_values = [extract_single_attr_value(attrs[2], data_client) for attrs in all_attrs]
    int_values = [extract_single_attr_value(attrs[3], data_client) for attrs in all_attrs]
    choice_values = [extract_single_attr_value(attrs[4], data_client) for attrs in all_attrs]

    assert part_values == ["Hull", "Mast", "Mast", "Anchor"]
    assert datetime_values == [
        pd.Timestamp(year=2025, month=8, day=13, hour=0, minute=0, second=0, tz="UTC"),
        pd.Timestamp(year=2025, month=8, day=13, hour=0, minute=0, second=0, tz="UTC"),
        pd.Timestamp(year=2025, month=8, day=13, hour=0, minute=0, second=0, tz="UTC"),
        pd.Timestamp(year=2025, month=7, day=1, hour=12, minute=34, second=56, tz="UTC"),
    ]
    np.testing.assert_equal(doub_values, [np.nan, 1.1, 2.2, 2.2])
    np.testing.assert_equal(int_values, [np.nan, 5, 5, 7])
    assert choice_values == ["C", "A", "B", "C"]


def test_combine_polyline_attrs(polyline_attrs_boat, data_client):
    polyline_objs = [obj for _, obj in polyline_attrs_boat.get_objects_of_type(dw.Polyline)]
    polyline_objs = sorted(polyline_objs, key=lambda pl: pl.VertexList[0].X)  # Ensure consistent order

    line_segments_go = combine_duf_polylines(polyline_objs, data_client, 12345)
    attrs = line_segments_go.parts.attributes
    assert [attr.name for attr in attrs] == ["Part", "Date", "Doub", "Int", "Choice"]
    assert [attr.attribute_type for attr in attrs] == ["category", "date_time", "scalar", "integer", "category"]

    part_values, datetime_values, doub_values, int_values, choice_values = [
        extract_attr_values(attr, data_client) for attr in attrs
    ]

    pd.testing.assert_series_equal(
        part_values, pd.Series(["Hull", "Mast", "Mast", "Anchor"]), check_index=False, check_names=False
    )
    pd.testing.assert_series_equal(
        datetime_values,
        pd.Series(
            [
                pd.Timestamp(year=2025, month=8, day=13, hour=0, minute=0, second=0, tz="UTC"),
                pd.Timestamp(year=2025, month=8, day=13, hour=0, minute=0, second=0, tz="UTC"),
                pd.Timestamp(year=2025, month=8, day=13, hour=0, minute=0, second=0, tz="UTC"),
                pd.Timestamp(year=2025, month=7, day=1, hour=12, minute=34, second=56, tz="UTC"),
            ],
            dtype="datetime64[us, UTC]",
        ),
        check_names=False,
    )
    pd.testing.assert_series_equal(doub_values, pd.Series([np.nan, 1.1, 2.2, 2.2]), check_names=False)
    pd.testing.assert_series_equal(int_values, pd.Series([np.nan, 5, 5, 7]), check_names=False)
    pd.testing.assert_series_equal(choice_values, pd.Series(["C", "A", "B", "C"]), check_index=False, check_names=False)
