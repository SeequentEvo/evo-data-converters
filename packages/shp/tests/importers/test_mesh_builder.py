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

from datetime import date
from pathlib import Path

import pytest
import shapefile
from evo.data_converters.shp.importer.implementation.local_data import LocalDataClient
from evo.data_converters.shp.importer.implementation.mesh_builder import MeshBuilder
from utils import shapefile_field_to_evo_type


@pytest.fixture
def parquet_path(tmp_path: Path) -> Path:
    return tmp_path / "parquet"


@pytest.fixture
def data_client(parquet_path: Path) -> LocalDataClient:
    return LocalDataClient(parquet_path)


@pytest.fixture
def triangle_strip(tmp_path: Path) -> tuple[shapefile.Reader, int, int, int]:
    """
    Get a basic shapefile with all possible field types.

    :return: (reader, num_fields, num_triangles, num_unique_vertices)
    """
    shp_path = tmp_path / "test_triangle_strip"

    shapefile
    with shapefile.Writer(shp_path, shapeType=31) as w:
        w.field("TEXT", shapefile.FieldType.C)
        w.field("BOOL", shapefile.FieldType.L)
        w.field("DATE", shapefile.FieldType.D)
        w.field("FLOAT", shapefile.FieldType.F)
        w.field("NUM", shapefile.FieldType.N)
        w.field("MEMO", shapefile.FieldType.M)

        w.multipatch(
            [
                [
                    [0, 0, 0],
                    [0, 0, 1],
                    [0, 1, 0],
                    [0, 1, 1],
                    [1, 2, 0],
                    [1, 2, 1],
                    [2, 2, 0],
                    [2, 2, 1],
                    [3, 1, 0],
                    [3, 1, 1],
                    [3, 0, 0],
                    [3, 0, 1],
                    [0, 0, 0],
                    [0, 0, 1],
                ],  # Triangle Strip
            ],
            [shapefile.TRIANGLE_STRIP],
        )

        w.record(TEXT="Shape1", BOOL=True, DATE=date(2012, 4, 1), FLOAT=27.6712498273, NUM=8, MEMO="a")

    return (shapefile.Reader(shp_path), 6, 12, 12)


@pytest.fixture
def triangle_fan(tmp_path: Path) -> tuple[shapefile.Reader, int, int, int]:
    """
    Get a basic shapefile with all possible field types.

    :return: (reader, num_fields, num_triangles, num_unique_vertices)
    """
    shp_path = tmp_path / "test_triangle_fan"

    shapefile
    with shapefile.Writer(shp_path, shapeType=31) as w:
        w.field("TEXT", shapefile.FieldType.C)
        w.field("BOOL", shapefile.FieldType.L)
        w.field("DATE", shapefile.FieldType.D)
        w.field("FLOAT", shapefile.FieldType.F)
        w.field("NUM", shapefile.FieldType.N)
        w.field("MEMO", shapefile.FieldType.M)

        w.multipatch(
            [
                [
                    [-5, -5, -2],
                    [-4.5, -4.5, 0],
                    [-6.5, -4.5, 0],
                    [-6.5, -6.5, 0],
                    [-4.5, -6.5, 0],
                    [-4.5, -4.5, 0],
                ]  # Triangle Fan
            ],
            [shapefile.TRIANGLE_FAN],
        )

        w.record(TEXT="Shape1", BOOL=True, DATE=date(2012, 4, 1), FLOAT=27.6712498273, NUM=8, MEMO="a")

    return (shapefile.Reader(shp_path), 6, 4, 5)


@pytest.fixture
def shapefile_with_point_data(tmp_path: Path) -> shapefile.Reader:
    """
    Get a basic shapefile with all possible field types.

    :return: (filepath, num_fields, num_parts, num_triangles, num_unique_vertices)
    """
    shp_path = tmp_path / "test_point_data"

    shapefile
    with shapefile.Writer(shp_path, shapeType=31) as w:
        w.field("TEXT", shapefile.FieldType.C)

        w.multipatch(
            [
                [
                    [-5, -5, -2, 1],
                    [-4.5, -4.5, 0, 2],
                    [-6.5, -4.5, 0, 3],
                    [-6.5, -6.5, 0, 4],
                    [-4.5, -6.5, 0, 5],
                    [-4.5, -4.5, 0, 6],
                ]  # Triangle Fan
            ],
            [shapefile.TRIANGLE_FAN],
        )

        w.record(TEXT="Shape1")

    return shapefile.Reader(shp_path)


def test_add_triangle_strip(triangle_strip: tuple[shapefile.Reader, int, int, int], data_client: LocalDataClient):
    reader, expected_field_num, expected_triangle_num, expected_vertex_num = triangle_strip
    fields = reader.fields[1:]
    mesh_builder = MeshBuilder(data_client=data_client, fields=fields)

    for sr in reader.iterShapeRecords():
        mesh_builder.add_shape_record(sr)

    mesh = mesh_builder.build()

    assert mesh.parts.chunks.length == reader.numShapes
    assert len(mesh.parts.attributes) == expected_field_num
    assert mesh.triangles.vertices.length == expected_vertex_num
    assert mesh.triangles.vertices.attributes is None
    assert mesh.triangles.indices.length == expected_triangle_num

    for field in fields:
        attrs = [attr for attr in mesh.parts.attributes if attr.name == field.name]
        assert len(attrs) == 1

        attr = attrs[0]

        assert attr.attribute_type == shapefile_field_to_evo_type(field.field_type)


def test_add_triangle_fan(triangle_fan: tuple[shapefile.Reader, int, int, int], data_client: LocalDataClient):
    reader, expected_field_num, expected_triangle_num, expected_vertex_num = triangle_fan
    # Skip DeletionFlag field
    fields = reader.fields[1:]
    mesh_builder = MeshBuilder(data_client=data_client, fields=fields)

    for sr in reader.iterShapeRecords():
        mesh_builder.add_shape_record(sr)

    mesh = mesh_builder.build()

    assert mesh.parts.chunks.length == reader.numShapes
    assert len(mesh.parts.attributes) == expected_field_num
    assert mesh.triangles.vertices.length == expected_vertex_num
    assert mesh.triangles.vertices.attributes is None
    assert mesh.triangles.indices.length == expected_triangle_num

    for field in fields:
        attrs = [attr for attr in mesh.parts.attributes if attr.name == field.name]
        assert len(attrs) == 1

        attr = attrs[0]

        assert attr.attribute_type == shapefile_field_to_evo_type(field.field_type)


def test_vertex_data(shapefile_with_point_data: shapefile.Reader, data_client: LocalDataClient):
    reader = shapefile_with_point_data
    fields = reader.fields[1:]
    mesh_builder = MeshBuilder(data_client=data_client, fields=fields)

    for sr in reader.iterShapeRecords():
        mesh_builder.add_shape_record(sr)

    mesh = mesh_builder.build()

    assert len(mesh.triangles.vertices.attributes) == 1
    assert mesh.triangles.vertices.attributes[0].attribute_type == "scalar"


def test_parquet_output(triangle_strip: Path, data_client: LocalDataClient, parquet_path: Path):
    reader, _, _, _ = triangle_strip

    fields = reader.fields[1:]
    mesh_builder = MeshBuilder(data_client=data_client, fields=fields)

    for sr in reader.iterShapeRecords():
        mesh_builder.add_shape_record(sr)

    mesh = mesh_builder.build()

    expected = []
    expected.append(parquet_path / f"{mesh.parts.chunks.data}")
    if mesh.parts.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in mesh.parts.attributes]

    expected.append(parquet_path / f"{mesh.triangles.vertices.data}")
    if mesh.triangles.vertices.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in mesh.triangles.vertices.attributes]

    expected.append(parquet_path / f"{mesh.triangles.indices.data}")
    if mesh.triangles.indices.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in mesh.triangles.indices.attributes]

    assert all(Path(file).exists for file in expected)
