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
from contextlib import ExitStack

import numpy as np
import pyarrow as pa
import pyassimp
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.elements import IndexArray2_V1_0_1
from typing_extensions import override

from .base import INDICES_SCHEMA, PARTS_SCHEMA, VERTICES_SCHEMA, InvalidOBJError, ObjImporterBase


class AssimpObjImporter(ObjImporterBase):
    """
    This implementation of the importer uses the Assimp library, which typically needs to be installed
    to the system separately to the Python bindings.

    Performance of this implementation is not particularly high on large meshes, but a lot of common
    software uses the Assimp library to produce OBJ files, so this implementation may be more compatible
    with files produced using such applications.
    """

    scene: pyassimp.structs.Scene
    stack: ExitStack

    @override
    def _parse_file(self) -> None:
        """
        Opens and validates the OBJ file, creating a native representation of it.
        """
        if ".obj" not in str(self.obj_file).lower():
            # this is a crutch because we can't otherwise block loading other file types with Assimp
            raise InvalidOBJError("Input file is not OBJ")

        # manually use the contextmanager with ExitStack, as we're not in context ourselves.
        self.stack = ExitStack()

        try:
            self.scene = self.stack.enter_context(
                pyassimp.load(
                    str(self.obj_file), processing=pyassimp.postprocess.aiProcess_Triangulate, file_type="obj"
                )
            )
        except pyassimp.AssimpError as e:
            raise InvalidOBJError(f"Load error: {e}")
        if self.scene.mNumMeshes == 0:
            raise InvalidOBJError("Input file contains no OBJ geometry (or is wrong format)")

    def __del__(self) -> None:
        if hasattr(self, "stack"):
            self.stack.close()

    @override
    async def create_tables(
        self, publish_parquet: bool = False
    ) -> tuple[Triangles_V1_2_0_Vertices, Triangles_V1_2_0_Indices, EmbeddedTriangulatedMesh_V2_1_0_Parts]:
        """
        Creates the triangles and indices tables, optionally publishing the tables to Evo as it goes.

        :param publish_parquet: Set `True` to upload Parquet tables to Evo as they're produced
        :return: Tuple of the vertices GO, Indices GO, chunks array GO
        """
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

            # We need to offset the face vertex indices based on how many vertices we've accumulated on previous parts
            faces_array = np.asarray(mesh.faces) + np.sum([len(v) for v in vertices_tables])
            index_table = pa.Table.from_pydict(
                {"n0": faces_array[:, 0], "n1": faces_array[:, 1], "n2": faces_array[:, 2]}, schema=INDICES_SCHEMA
            )
            del faces_array

            # very short, one-row table
            part_table = pa.Table.from_pydict(
                {"offset": [np.sum([len(v) for v in indices_tables])], "count": [len(index_table)]}, schema=PARTS_SCHEMA
            )
            parts_tables.append(part_table)
            vertices_tables.append(vertex_table)
            indices_tables.append(index_table)

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
