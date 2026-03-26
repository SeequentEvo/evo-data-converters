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
from evo.data_converters.shp.importer.shp_to_evo import convert_shp
from evo_schemas.objects.triangle_mesh import TriangleMesh_V2_2_0
from pyproj import CRS
from utils import shapefile_field_to_evo_type


@pytest.fixture
def sample_shp(tmp_path: Path) -> tuple[Path, list[tuple[str, shapefile.FieldType]], int, int, int]:
    """
    Get a basic shapefile with all possible field types.

    :return: (filepath, expected_fields, num_shapes, num_triangles, num_unique_vertices)
    """
    shp_path = tmp_path / "test_shapefile"
    fields = [
        ("TEXT", shapefile.FieldType.C),
        ("BOOL", shapefile.FieldType.L),
        ("DATE", shapefile.FieldType.D),
        ("FLOAT", shapefile.FieldType.F),
        ("NUM", shapefile.FieldType.N),
        ("MEMO", shapefile.FieldType.M),
    ]
    with shapefile.Writer(shp_path, shapeType=31) as w:
        for name, type in fields:
            w.field(name, type)

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
                [
                    [-5, -5, -2],
                    [-4.5, -4.5, 0],
                    [-6.5, -4.5, 0],
                    [-6.5, -6.5, 0],
                    [-4.5, -6.5, 0],
                    [-4.5, -4.5, 0],
                ],  # Triangle Fan
            ],
            [shapefile.TRIANGLE_STRIP, shapefile.TRIANGLE_FAN],
        )

        w.record(TEXT="Shape1", BOOL=True, DATE=date(2012, 4, 1), FLOAT=27.6712498273, NUM=8, MEMO="a")

        w.multipatch(
            [
                [[10, 9, 8, 3.6], [10, 8, 8, 4.7], [10, 9, 7, 5.8]]  # Simple Triangle Strip with data.
            ],
            [shapefile.TRIANGLE_STRIP],
        )

        w.record(TEXT="Shape2", BOOL=False, DATE=date(1970, 1, 1), FLOAT=27.6712498273, NUM=104, MEMO="b")

    return (shp_path, fields, 2, 17, 20)


@pytest.fixture
def prj(tmp_path: Path) -> tuple[Path, str]:
    """
    Get a prj in non-normalized WKT format, along with the expected result in WKT 2.

    :return: (prj_file_path, expected_prj)
    """
    prj_path = tmp_path / "test_shapefile.prj"
    with open(prj_path, "w") as prj:
        wkt = 'GEOGCS["WGS 84",'
        wkt += 'DATUM["WGS_1984",'
        wkt += 'SPHEROID["WGS 84",6378137,298.257223563]]'
        wkt += ',PRIMEM["Greenwich",0],'
        wkt += 'UNIT["degree",0.0174532925199433]]'
        prj.write(wkt)
    return (prj_path, CRS.from_wkt(wkt).to_wkt(version="WKT2_2019"))


@pytest.fixture
def parquet_path(tmp_path: Path) -> Path:
    return tmp_path / "parquet"


def test_convert_basic_shp(sample_shp: tuple[Path, int, int, int, int], parquet_path: Path):
    path, expected_fields, expected_shape_num, expected_triangle_num, expected_vertex_num = sample_shp
    triangle_meshes = convert_shp(
        path, None, upload_path=parquet_path, publish_objects=False, overwrite_existing_objects=True
    )

    assert len(triangle_meshes) == 1

    triangle_mesh: TriangleMesh_V2_2_0 = triangle_meshes[0]

    # Evo object description
    assert triangle_mesh.name == path.stem
    assert triangle_mesh.schema == "/objects/triangle-mesh/2.2.0/triangle-mesh.schema.json"
    assert triangle_mesh.coordinate_reference_system == "unspecified"

    # Check number of parts, triangles, etc. match up
    assert triangle_mesh.parts.chunks.length == expected_shape_num
    assert len(triangle_mesh.parts.attributes) == len(expected_fields)
    assert triangle_mesh.triangles.indices.length == expected_triangle_num
    assert triangle_mesh.triangles.vertices.length == expected_vertex_num
    for name, type in expected_fields:
        attrs = [attr for attr in triangle_mesh.parts.attributes if attr.name == name]
        assert len(attrs) == 1

        attr = attrs[0]
        assert attr.name == name
        assert attr.attribute_type == shapefile_field_to_evo_type(type)
        assert attr.values.length == expected_shape_num

    # Bounding Box
    assert triangle_mesh.bounding_box.min_x == -6.5
    assert triangle_mesh.bounding_box.min_y == -6.5
    assert triangle_mesh.bounding_box.min_z == -2
    assert triangle_mesh.bounding_box.max_x == 10
    assert triangle_mesh.bounding_box.max_y == 9
    assert triangle_mesh.bounding_box.max_z == 8


def test_custom_tags(sample_shp: Path, parquet_path: Path):
    path, _, _, _, _ = sample_shp

    tags = {"Source": "Test", "Type": "Shapefile", "Custom Tag": "Here!"}
    expected_tags = {"Stage": "Experimental", "InputType": "SHP", **(tags)}

    triangle_meshes = convert_shp(
        path, None, tags=tags, upload_path=parquet_path, publish_objects=False, overwrite_existing_objects=True
    )

    assert len(triangle_meshes) == 1

    triangle_mesh: TriangleMesh_V2_2_0 = triangle_meshes[0]

    assert triangle_mesh.tags == expected_tags


def test_prj(sample_shp: Path, prj: Path, parquet_path: Path):
    path, _, _, _, _ = sample_shp
    prj_file, expected_prj = prj

    triangle_meshes = convert_shp(
        path, filepath_prj=prj_file, upload_path=parquet_path, publish_objects=False, overwrite_existing_objects=True
    )

    assert len(triangle_meshes) == 1

    triangle_mesh: TriangleMesh_V2_2_0 = triangle_meshes[0]

    assert triangle_mesh.coordinate_reference_system.ogc_wkt == expected_prj


def test_parquet_output(sample_shp: Path, parquet_path: Path):
    path, _, _, _, _ = sample_shp

    triangle_meshes = convert_shp(
        path, None, upload_path=parquet_path, publish_objects=False, overwrite_existing_objects=True
    )

    assert len(triangle_meshes) == 1

    triangle_mesh: TriangleMesh_V2_2_0 = triangle_meshes[0]

    expected = []
    expected.append(parquet_path / f"{triangle_mesh.parts.chunks.data}")
    if triangle_mesh.parts.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in triangle_mesh.parts.attributes]

    expected.append(parquet_path / f"{triangle_mesh.triangles.vertices.data}")
    if triangle_mesh.triangles.vertices.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in triangle_mesh.triangles.vertices.attributes]

    expected.append(parquet_path / f"{triangle_mesh.triangles.indices.data}")
    if triangle_mesh.triangles.indices.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in triangle_mesh.triangles.indices.attributes]

    assert all(Path(file).exists for file in expected)
