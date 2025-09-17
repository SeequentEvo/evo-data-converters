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

import asyncio
import os
from unittest import mock
from uuid import uuid4

from evo_schemas import LineSegments_V2_1_0, TriangleMesh_V2_1_0

from evo.data_converters.common import EvoObjectMetadata
from evo.data_converters.duf.exporter.evo_to_duf import (
    export_duf,
)
from evo.data_converters.duf.importer.duf_to_evo import convert_duf


def _check_both_or_neither_none(a, b) -> bool:
    assert (is_none := a is None) == (b is None)
    return not is_none


def _compare_evo_attributed_base(actual, expected):
    _check_both_or_neither_none(actual.parts, expected.parts)

    if actual.parts is not None:
        for line_attr, expected_line_attr in zip(actual.parts.attributes, expected.parts.attributes):
            assert type(line_attr) is type(expected_line_attr)
            assert line_attr.key == expected_line_attr.key
            assert line_attr.name == expected_line_attr.name
            assert line_attr.attribute_type == expected_line_attr.attribute_type


def _compare_evo_polylines(lines: list[LineSegments_V2_1_0], expected_lines: list[LineSegments_V2_1_0]):
    for line, expected_line in zip(lines, expected_lines, strict=True):
        assert (line.parts is None and expected_line.parts is None) or (
            line.parts.chunks.length == expected_line.parts.chunks.length
        )
        assert line.segments.indices.length == expected_line.segments.indices.length

        _compare_evo_attributed_base(line, expected_line)


def _compare_evo_triangle_meshes(meshes: list[TriangleMesh_V2_1_0], expected_meshes: list[TriangleMesh_V2_1_0]):
    for mesh, expected_mesh in zip(meshes, expected_meshes, strict=True):
        _compare_evo_attributed_base(mesh, expected_mesh)
        if mesh.parts is not None:
            assert mesh.parts.chunks.length == expected_mesh.parts.chunks.length

            if _check_both_or_neither_none(mesh.parts.triangle_indices, expected_mesh.parts.triangle_indices):
                assert mesh.parts.triangle_indices.length == expected_mesh.parts.triangle_indices.length

        _compare_evo_attributed_base(mesh, expected_mesh)


def _mock_convert_to_evo(filename: str, evo_metadata):
    return convert_duf(filepath=filename, evo_workspace_metadata=evo_metadata, epsg_code=32650)


def _mock_convert_to_duf(evo_objects, out_filename, evo_metadata):
    objects_downloaded = 0

    async def mock_download(*a, **kw):
        nonlocal objects_downloaded
        result = evo_objects[objects_downloaded]
        objects_downloaded += 1
        return result

    with mock.patch("evo.objects.client.ObjectAPIClient.download_object_by_id", new=mock_download):
        # The metadata won't actually be used, because the download is mocked
        metadata = [EvoObjectMetadata(uuid4()) for _ in evo_objects]
        asyncio.run(export_duf(out_filename, metadata, evo_metadata))


def test_convert_polyline(evo_metadata, polyline_attrs_boat_path, test_out_path):
    # Convert a DUF file to Evo and use the generated Parquet files to test the exporter

    initial_evo_objects = _mock_convert_to_evo(polyline_attrs_boat_path, evo_metadata)

    _mock_convert_to_duf(initial_evo_objects, test_out_path, evo_metadata)
    assert os.path.exists(test_out_path)

    final_evo_objects = _mock_convert_to_evo(test_out_path, evo_metadata)

    _compare_evo_polylines(initial_evo_objects, final_evo_objects)


def test_convert_triangle_mesh(evo_metadata, pit_mesh_attrs_path, test_out_path):
    initial_evo_objects = _mock_convert_to_evo(pit_mesh_attrs_path, evo_metadata)

    _mock_convert_to_duf(initial_evo_objects, test_out_path, evo_metadata)
    assert os.path.exists(test_out_path)

    final_evo_objects = _mock_convert_to_evo(test_out_path, evo_metadata)

    _compare_evo_triangle_meshes(initial_evo_objects, final_evo_objects)


def test_multiple_objects_same_name(evo_metadata, pit_mesh_attrs_path, test_out_path):
    initial_evo_objects = _mock_convert_to_evo(pit_mesh_attrs_path, evo_metadata)

    # 3 objects, all with the same name
    initial_evo_objects = initial_evo_objects + initial_evo_objects + initial_evo_objects

    _mock_convert_to_duf(initial_evo_objects, test_out_path, evo_metadata)
    final_evo_objects = _mock_convert_to_evo(test_out_path, evo_metadata)

    # It might not be in the end, due to round-tripping details, but somewhere the (#) should be in the name
    assert (")") not in final_evo_objects[0].name
    assert "(2)" in final_evo_objects[1].name
    assert "(3)" in final_evo_objects[2].name


# TODO More tests
# TODO Test Geoscience Objects with unhandled schema ids
