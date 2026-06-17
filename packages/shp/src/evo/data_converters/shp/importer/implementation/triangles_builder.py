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

import pyarrow as pa
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0,
    NanContinuous_V1_0_1,
    Triangles_V1_2_0,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.elements import (
    FloatArray1_V1_0_1,
)


class TrianglesBuilder:
    """
    Builds a Triangles geoscience object from lists of triangles and their data.
    """

    class _Vertex_Data:
        """Stores the data and index in the vertices array of this vertex."""

        def __init__(self, index: int, data: float):
            self.index = index
            self.data = data

    def __init__(self, data_client: ObjectDataClient):
        """
        Initializes the Triangles builder.

        :param data_client: Object data client for uploading parquet files (real or stub).
        """
        self.vertices = {}
        self.triangles = []
        self.data_client = data_client

    def add_triangle(self, triangle_vertices: list[tuple[float, float, float]], vertex_data: list[float | None]):
        """
        Adds a triangle and it's vertex data to the builder.

        :param triangle_vertices: The (x, y, z) formatted vertices of the triangle. len(triangle_vertices) == 3.
        :param vertex_data: The data for each vertex (Data values can be None). len(vertex_data) == len(triangle_vertices)
        """
        assert len(triangle_vertices) == len(vertex_data), "Not all vertices have data."

        triangle = []
        for i in range(len(triangle_vertices)):
            index = self._add_or_get_vertex(triangle_vertices[i], vertex_data[i]).index
            triangle.append(index)
        self.triangles.append(tuple(triangle))

    def get_num_triangles(self) -> int:
        """Get the number of triangles added to the builder so far."""
        return int(len(self.triangles) / 3)

    def build(self) -> Triangles_V1_2_0:
        """
        Builds a Triangles geoscience object from the triangles added so far.
        """
        n0, n1, n2 = zip(*self.triangles)
        schema = pa.schema([("n0", pa.uint64()), ("n1", pa.uint64()), ("n2", pa.uint64())])
        table = pa.table({"n0": n0, "n1": n1, "n2": n2}, schema=schema)
        triangle_hash = self._create_parquet_file(table)
        indices = Triangles_V1_2_0_Indices(
            attributes=None, data=triangle_hash, length=len(self.triangles), data_type="uint64"
        )

        x = []
        y = []
        z = []
        vertex_data_list = []
        vertex_nan = float("nan")
        has_vertex_data = False
        for vertex, vertex_data in self.vertices.items():
            x.append(vertex[0])
            y.append(vertex[1])
            z.append(vertex[2])
            if vertex_data.data is not None:
                vertex_data_list.append(vertex_data.data)
                has_vertex_data = True
            else:
                vertex_data_list.append(vertex_nan)

        schema = pa.schema([("x", pa.float64()), ("y", pa.float64()), ("z", pa.float64())])
        table = pa.table({"x": x, "y": y, "z": z}, schema=schema)
        vertex_hash = self._create_parquet_file(table)

        vertex_attributes = None

        if has_vertex_data:
            schema = pa.schema([("values", pa.float64())])
            table = pa.table({"values": vertex_data_list})
            vertex_data_hash = self._create_parquet_file(table)
            vertex_array = FloatArray1_V1_0_1(data=vertex_data_hash, length=len(vertex_data_list), data_type="float64")
            vertex_nan_continuous = NanContinuous_V1_0_1(values=[vertex_nan])
            vertex_attributes = [
                ContinuousAttribute_V1_1_0(
                    name="Measurements",
                    key=vertex_data_hash,
                    attribute_description=None,
                    nan_description=vertex_nan_continuous,
                    values=vertex_array,
                )
            ]

        vertices = Triangles_V1_2_0_Vertices(
            attributes=vertex_attributes, data=vertex_hash, length=len(self.vertices), data_type="float64"
        )

        triangle = Triangles_V1_2_0(vertices=vertices, indices=indices)
        return triangle

    def _add_or_get_vertex(self, vertex: tuple[float, float, float], m: float = None) -> _Vertex_Data:
        """
        Returns the data in the vertices array for the requested vertex, adding it if it doesn't already exist.

        :param vertex: The vertex to find or add. Only one instance of each vertex will ever be in the vertices list.
        :param m: The data for this vertex. If the vertex already exists, it's value is not updated. A vertex is always
        assumed to have the same value.

        :return: The vertex data (including it's index in the vertices array).
        """
        if vertex not in self.vertices:
            length = len(self.vertices)
            self.vertices[vertex] = self._Vertex_Data(length, m)
        return self.vertices[vertex]

    def _create_parquet_file(self, table: pa.table) -> str:
        """
        Writes a parquet file from the given table using the data client.

        :param table: The table to write.

        :return: The file hash of the written table.
        """
        saved_table_info = self.data_client.save_table(table)
        return saved_table_info["data"]
