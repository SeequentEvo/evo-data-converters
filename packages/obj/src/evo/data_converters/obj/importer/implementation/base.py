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

from abc import abstractmethod
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Crs_V1_0_1,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Triangles_V1_2_0,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.objects import TriangleMesh_V2_2_0

from evo.objects.utils.data import ObjectDataClient

VERTICES_SCHEMA = pa.schema([pa.field("x", pa.float64()), pa.field("y", pa.float64()), pa.field("z", pa.float64())])
INDICES_SCHEMA = pa.schema([pa.field("n0", pa.uint64()), pa.field("n1", pa.uint64()), pa.field("n2", pa.uint64())])
PARTS_SCHEMA = pa.schema([pa.field("offset", pa.uint64()), pa.field("count", pa.uint64())])


class ObjImporterBase:
    """
    Abstract base implementation of an importer.
    """

    obj_file: str | Path
    data_client: ObjectDataClient
    crs: Crs_V1_0_1

    def __init__(self, obj_file: str | Path, crs: Crs_V1_0_1, data_client: ObjectDataClient):
        """
        Construct an importer implementation adapter.

        :param obj_file The path to the OBJ file to open, which may be next to a corresponding MTL file
        :param crs the intended coordinate reference system object matching this mesh
        :param data_client an instance of ObjectDataClient for saving and uploading Parquet tables
        """
        self.obj_file = obj_file
        self.data_client = data_client
        self.crs = crs

    def convert_file(self) -> TriangleMesh_V2_2_0:
        """
        Performs a conversion to an unpublished TriangleMesh GeoObject

        :return: The GeoObject representation of the mesh
        """
        self._parse_file()
        (vertices_go, indices_go, parts_go) = self.create_tables()

        triangles_go = Triangles_V1_2_0(vertices=vertices_go, indices=indices_go)

        triangle_mesh_go = TriangleMesh_V2_2_0(
            name=Path(self.obj_file).name,
            uuid=None,
            bounding_box=self._get_bounding_box(),
            coordinate_reference_system=self.crs,
            triangles=triangles_go,
            parts=parts_go,
        )

        return triangle_mesh_go

    @abstractmethod
    def _parse_file(self) -> None:
        """
        Opens and validates the OBJ file, creating a native representation of it.
        """
        pass

    @abstractmethod
    def create_tables(
        self,
    ) -> tuple[Triangles_V1_2_0_Vertices, Triangles_V1_2_0_Indices, EmbeddedTriangulatedMesh_V2_1_0_Parts]:
        """
        Creates the triangles and indices tables.

        :return: Tuple of the vertices GO, Indices GO, chunks array GO
        """
        pass

    @abstractmethod
    def _get_bounding_box(self) -> BoundingBox_V1_0_1:
        """
        Generates the bounding box GeoObject of the vertices in the world scene.

        :return: Bounding Box GeoObject with coordinates of the boundaries
        """
        pass

    @staticmethod
    def _check_tables(vertices_table: pa.Table, indices_table: pa.Table, faces_table: pa.Table) -> None:
        """
        Validates that the passed tables are valid and raises exceptions if they aren't.

        :param vertices_table The PyArrow vertices table
        :param indices_table The PyArrow faces table
        :param parts_table The PyArrow parts table
        """
        for col in ["n0", "n1", "n2"]:
            min_max = pc.min_max(indices_table[col])
            if min_max["min"].as_py() < 0 or min_max["max"].as_py() >= len(vertices_table):
                raise InvalidOBJError(f"Invalid OBJ file: {col} face index is out of range")


class UnsupportedOBJError(Exception):
    pass


class InvalidOBJError(Exception):
    pass
