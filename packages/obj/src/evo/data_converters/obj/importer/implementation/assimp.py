import asyncio

from contextlib import ExitStack
from typing import Tuple, Any
from typing_extensions import override

import pyassimp

import pyarrow as pa
import numpy as np

from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
)
from evo_schemas.elements import IndexArray2_V1_0_1

from .base import ObjImporterBase, VERTICES_SCHEMA, INDICES_SCHEMA, PARTS_SCHEMA


class AssimpObjImporter(ObjImporterBase):
    scene: Any  # FIXME
    stack: ExitStack

    @override
    def _parse_file(self) -> None:
        """
        Opens and validates the OBJ file, creating a native representation of it.
        """
        # manually use the contextmanager with ExitStack, as we're not in context ourselves.
        self.stack = ExitStack()
        self.scene = self.stack.enter_context(
            # pyassimp.load(str(self.obj_file), processing=pyassimp.postprocess.aiProcess_Triangulate)
            pyassimp.load(str(self.obj_file))
        )

    def __del__(self) -> None:
        self.stack.close()

    @override
    async def create_tables(
        self, publish_parquet: bool = False
    ) -> Tuple[Triangles_V1_2_0_Vertices, Triangles_V1_2_0_Indices, EmbeddedTriangulatedMesh_V2_1_0_Parts]:
        """
        Creates the triangles and indices tables, optionally publishing the tables to Evo as it goes.

        :param publish_parquet: Set `True` to upload Parquet tables to Evo as they're produced
        :return: Tuple of the vertices GO, Indices GO, chunks array GO
        """
        vertex_count_accum = 0
        vertices_tables = []
        indices_tables = []
        parts_tables = []

        for index, mesh in enumerate(self.scene.meshes):
            vertices_array = np.asarray(mesh.vertices)

            vertex_table = pa.Table.from_pydict(
                {"x": vertices_array[:, 0], "y": vertices_array[:, 1], "z": vertices_array[:, 2]},
                schema=VERTICES_SCHEMA,
            )
            del vertices_array
            vertices_tables.append(vertex_table)

            # We need to offset the face indices because the vertices will be concatenated
            faces_array = np.asarray(mesh.faces) + vertex_count_accum
            index_table = pa.Table.from_pydict(
                {"n0": faces_array[:, 0], "n1": faces_array[:, 1], "n2": faces_array[:, 2]}, schema=INDICES_SCHEMA
            )
            del faces_array
            indices_tables.append(index_table)

            # very short, one-row table
            part_table = pa.Table.from_pydict(
                {"offset": [vertex_count_accum], "count": [len(vertex_table)]}, schema=PARTS_SCHEMA
            )
            parts_tables.append(part_table)

            vertex_count_accum += len(vertex_table)

        vertices_table = pa.concat_tables(vertices_tables)
        indices_table = pa.concat_tables(indices_tables)
        parts_table = pa.concat_tables(parts_tables)

        if publish_parquet:
            # Publish the tables in parallel
            vertices_table_obj, indices_table_obj, parts_table_obj = await asyncio.gather(
                self.data_client.upload_table(vertices_table),
                self.data_client.upload_table(indices_table),
                self.data_client.upload_table(parts_table),
            )
        else:
            vertices_table_obj = self.data_client.save_table(vertices_table)
            indices_table_obj = self.data_client.save_table(indices_table)
            parts_table_obj = self.data_client.save_table(parts_table)

        vertices_go = Triangles_V1_2_0_Vertices(
            **vertices_table_obj,
            attributes=None,
        )

        indices_go = Triangles_V1_2_0_Indices(
            **indices_table_obj,
            attributes=None,
        )

        chunks_go = IndexArray2_V1_0_1(**parts_table_obj)
        parts_go = EmbeddedTriangulatedMesh_V2_1_0_Parts(attributes=None, chunks=chunks_go, triangle_indices=None)

        return (vertices_go, indices_go, parts_go)

    @override
    def _get_bounding_box(self) -> BoundingBox_V1_0_1:
        """
        Generates the bounding box GeoObject of the vertices of the imported file.

        :return: Bounding Box GeoObject with coordinates of the boundaries
        """
        box = pyassimp.helper.get_bounding_box(self.scene)
        return BoundingBox_V1_0_1(
            min_x=box[0][0],
            max_x=box[1][0],
            min_y=box[0][1],
            max_y=box[1][1],
            min_z=box[0][2],
            max_z=box[1][2],
        )
