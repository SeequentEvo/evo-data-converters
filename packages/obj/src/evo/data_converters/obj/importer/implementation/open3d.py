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

from typing import Tuple
from typing_extensions import override

import open3d

import pyarrow as pa
import numpy as np

from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
)
from evo_schemas.elements import IndexArray2_V1_0_1

from .base import ObjImporterBase, VERTICES_SCHEMA, INDICES_SCHEMA, PARTS_SCHEMA, InvalidOBJError


class Open3dObjImporter(ObjImporterBase):
    """
    An importer for OBJ files using the Open3D library.

    There is no overwhelming reason to choose this library over TinyOBJ, though
    some manipulation operations are easier to perform with Open3D if you were to
    subclass this implementation.
    """

    model: open3d.cpu.pybind.visualization.rendering.TriangleMeshModel
    cached_bbox: BoundingBox_V1_0_1

    @override
    def _parse_file(self) -> None:
        """
        Opens and validates the OBJ file, creating a native representation of it.
        """
        if ".obj" not in str(self.obj_file).lower():
            # this is a crutch because we can't otherwise block loading other file types with O3D
            raise InvalidOBJError("Input file is not OBJ")
        self.model = open3d.io.read_triangle_model(self.obj_file)
        if not self.model or len(self.model.meshes) == 0:
            raise InvalidOBJError("Input file contains no OBJ geometry (or is wrong format)")

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

        for i, mesh in enumerate(self.model.meshes):
            vertices_array = np.asarray(mesh.mesh.vertices)
            vertex_table = pa.Table.from_pydict(
                {"x": vertices_array[:, 0], "y": vertices_array[:, 1], "z": vertices_array[:, 2]},
                schema=VERTICES_SCHEMA,
            )
            del vertices_array
            vertices_tables.append(vertex_table)

            # We need to offset the face indices because the vertices will be concatenated
            faces_array = np.asarray(mesh.mesh.triangles) + vertex_count_accum
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

        self._check_tables(vertices_table, indices_table, parts_table)

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

        self.cached_bbox = BoundingBox_V1_0_1(
            min_x=np.amin(vertices_table["x"]),
            max_x=np.amax(vertices_table["x"]),
            min_y=np.amin(vertices_table["y"]),
            max_y=np.amax(vertices_table["y"]),
            min_z=np.amin(vertices_table["z"]),
            max_z=np.amax(vertices_table["z"]),
        )

        return (vertices_go, indices_go, parts_go)

    @override
    def _get_bounding_box(self) -> BoundingBox_V1_0_1:
        """
        Generates the bounding box GeoObject of the vertices in the world scene.

        :return: Bounding Box GeoObject with coordinates of the boundaries
        """
        return self.cached_bbox
