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

from pathlib import Path

import pytest
from evo.data_converters.shp.importer.implementation.local_data import LocalDataClient
from evo.data_converters.shp.importer.implementation.triangles_builder import TrianglesBuilder


@pytest.fixture
def parquet_path(tmp_path: Path) -> Path:
    return tmp_path / "parquet"


@pytest.fixture
def data_client(parquet_path: Path) -> LocalDataClient:
    return LocalDataClient(parquet_path)


@pytest.fixture
def sample_triangles() -> tuple[list[tuple[int, int, int]], int]:
    """
    Get a basic set of triangles with no data.

    :return: (points, expected_num_vertices)
    """
    return ([(0, 0, 0), (1, 1, 1), (2, 0, 0), (1, 1, 1), (2, 0, 0), (3, 1, 1)], 4)


@pytest.fixture
def sample_triangles_with_data() -> tuple[list[tuple[int, int, int]], list[float], list[float | None]]:
    """
    Get a basic set of triangles with point data (including None).

    :return: (points, points_data, expected_num_vertices)
    """
    triangles = [(0, 0, 0), (1, 1, 1), (2, 0, 0), (-5, -5, -7), (-2, 0, 0), (-10, -2, -4)]
    data = [1.1, 2.2, None, 4.4, 5.5, 6.6]
    return (triangles, data, 6)


def test_triangles_no_data(
    sample_triangles: tuple[list[tuple[int, int, int]], list[float]], data_client: LocalDataClient
):
    triangles, expected_num_vertices = sample_triangles

    triangles_builder = TrianglesBuilder(data_client)

    for i in range(0, len(triangles), 3):
        triangles_builder.add_triangle(triangles[i : i + 3], [None, None, None])

    go_triangles = triangles_builder.build()

    assert go_triangles.vertices.length == expected_num_vertices
    assert go_triangles.vertices.attributes is None
    assert go_triangles.indices.length == 2
    assert go_triangles.indices.attributes is None


def test_triangles_with_data(
    sample_triangles_with_data: tuple[list[tuple[int, int, int]], list[float], list[float | None]],
    data_client: LocalDataClient,
):
    triangles, data, expected_num_vertices = sample_triangles_with_data

    triangles_builder = TrianglesBuilder(data_client)

    for i in range(0, len(triangles), 3):
        triangles_builder.add_triangle(triangles[i : i + 3], data[i : i + 3])

    go_triangles = triangles_builder.build()

    assert go_triangles.vertices.length == expected_num_vertices
    assert len(go_triangles.vertices.attributes) == 1
    assert go_triangles.vertices.attributes[0].name == "Measurements"
    assert go_triangles.vertices.attributes[0].values.length == expected_num_vertices
    assert go_triangles.indices.length == 2
    assert go_triangles.indices.attributes is None


def test_parquet_output(
    sample_triangles_with_data: tuple[list[tuple[int, int, int]], list[float], list[float | None]],
    data_client: LocalDataClient,
    parquet_path: Path,
):
    triangles, data, _ = sample_triangles_with_data

    triangles_builder = TrianglesBuilder(data_client)

    for i in range(0, len(triangles), 3):
        triangles_builder.add_triangle(triangles[i : i + 3], data[i : i + 3])

    go_triangles = triangles_builder.build()

    expected = []
    expected.append(parquet_path / f"{go_triangles.vertices.data}")
    if go_triangles.vertices.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in go_triangles.vertices.attributes]

        expected.append(parquet_path / f"{go_triangles.indices.data}")
    if go_triangles.indices.attributes is not None:
        expected += [parquet_path / f"{attr.key}.parquet" for attr in go_triangles.indices.attributes]

    assert all(Path(file).exists for file in expected)
