from abc import abstractmethod
from pathlib import Path
from typing import Tuple

import pyarrow as pa

from evo_schemas.objects import TriangleMesh_V2_2_0
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Triangles_V1_2_0,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Crs_V1_0_1,
)

VERTICES_SCHEMA = pa.schema([pa.field("x", pa.float64()), pa.field("y", pa.float64()), pa.field("z", pa.float64())])
INDICES_SCHEMA = pa.schema([pa.field("n0", pa.uint64()), pa.field("n1", pa.uint64()), pa.field("n2", pa.uint64())])
PARTS_SCHEMA = pa.schema([pa.field("offset", pa.uint64()), pa.field("count", pa.uint64())])


class ObjImporterBase:
    obj_file: str | Path
    data_client: ObjectDataClient
    crs: Crs_V1_0_1

    def __init__(self, obj_file: str | Path, crs: Crs_V1_0_1, data_client: ObjectDataClient):
        self.obj_file = obj_file
        self.data_client = data_client
        self.crs = crs

    async def convert_file(self, publish_parquet: bool = False) -> TriangleMesh_V2_2_0:
        """
        Performs a conversion to an unpublished TriangleMesh GeoObject

        :param publish_parquet Set `True` to upload Parquet tables to Evo as they're produced
        :return: The GeoObject representation of the mesh
        """
        self._parse_file()
        (vertices_go, indices_go, parts_go) = await self.create_tables(publish_parquet)

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
    async def create_tables(
        self, publish_parquet: bool = False
    ) -> Tuple[Triangles_V1_2_0_Vertices, Triangles_V1_2_0_Indices, EmbeddedTriangulatedMesh_V2_1_0_Parts]:
        """
        Creates the triangles and indices tables, optionally publishing the tables to Evo as it goes.

        :param publish_parquet: Set `True` to upload Parquet tables to Evo as they're produced
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


class UnsupportedOBJError(Exception):
    pass
