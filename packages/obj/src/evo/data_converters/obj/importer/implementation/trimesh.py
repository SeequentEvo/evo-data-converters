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


import numpy as np
import pyarrow as pa
import trimesh
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.elements import IndexArray2_V1_0_1
from typing_extensions import override

from .base import INDICES_SCHEMA, PARTS_SCHEMA, VERTICES_SCHEMA, InvalidOBJError, ObjImporterBase


class TrimeshObjImporter(ObjImporterBase):
    """
    An OBJ importer using the Trimesh pure-python Library.

    This implementation is fairly complete and handles parts and textures well,
    though Evo doesn't currently support textures. Due to the re-sorting of vertices and
    general in-memory manipulation, Trimesh can be inefficient/slow on very large
    meshes over 2 million triangles.

    Notes on performance:

    Trimesh does a pretty good job, but at scale it performs worse than some other libraries.
    - A lot of time is spent during the initial file parsing, particularly if textures are enabled
    - Memory use is generally peaky and high
    """

    scene: trimesh.Scene

    @override
    def _parse_file(self) -> None:
        """
        Opens and validates the OBJ file, creating a native representation of it.
        """
        try:
            self.scene = trimesh.load_scene(
                self.obj_file,
                split_object=True,
                file_type="obj",
                # in future when we need texture data this will need to change, in the meantime not
                # loading textures to PIL saves quite a bit of memory:
                skip_materials=True,
            )
            if len(self.scene.geometry) == 0:
                raise InvalidOBJError("Input file contains no OBJ geometry (or is wrong format)")
        except IndexError as e:
            # this typically means bad indices
            raise InvalidOBJError(f"Invalid OBJ flie: Indexing error (probably invalid faces in file): {e}")

    @override
    def create_tables(
        self,
    ) -> tuple[Triangles_V1_2_0_Vertices, Triangles_V1_2_0_Indices, EmbeddedTriangulatedMesh_V2_1_0_Parts]:
        """
        Creates the triangles and indices tables, optionally publishing the tables to Evo as it goes.

        :return: Tuple of the vertices GO, Indices GO, chunks array GO
        """
        vertices_tables = []
        indices_tables = []
        parts_tables = []

        for node_name in self.scene.graph.nodes_geometry:
            # Shift the mesh into world frame
            transform, geom_name = self.scene.graph.get(node_name)
            mesh = self.scene.geometry[geom_name].copy()
            mesh.apply_transform(transform)

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
            vertices_tables.append(vertex_table)
            indices_tables.append(index_table)
            parts_tables.append(part_table)

        vertices_table = pa.concat_tables(vertices_tables)
        indices_table = pa.concat_tables(indices_tables)
        parts_table = pa.concat_tables(parts_tables)

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
        Generates the bounding box GeoObject of the vertices in the world scene.

        :return: Bounding Box GeoObject with coordinates of the boundaries
        """
        bounds = self.scene.bounds
        return BoundingBox_V1_0_1(
            min_x=bounds[0][0],
            max_x=bounds[1][0],
            min_y=bounds[0][1],
            max_y=bounds[1][1],
            min_z=bounds[0][2],
            max_z=bounds[1][2],
        )
