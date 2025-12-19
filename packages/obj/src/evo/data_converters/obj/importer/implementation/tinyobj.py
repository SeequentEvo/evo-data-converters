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

import gc

import numpy as np
import pyarrow as pa
import tinyobjloader
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.elements import IndexArray2_V1_0_1
from typing_extensions import override

from .base import INDICES_SCHEMA, PARTS_SCHEMA, VERTICES_SCHEMA, InvalidOBJError, ObjImporterBase


class TinyobjObjImporter(ObjImporterBase):
    """
    An OBJ importer implementation using the TinyOBJ library.

    This implementation is by far the most memory-efficient and fastest for large meshes,
    though currently the binding to use it isn't stable. This implementation may become the preferred
    one when a stable v2.0 of the Python binding is released.
    """

    reader: tinyobjloader.ObjReader

    @override
    def _parse_file(self) -> None:
        """
        Opens and validates the OBJ file, creating a native representation of it.
        """
        self.reader = tinyobjloader.ObjReader()
        config = tinyobjloader.ObjReaderConfig()
        config.triangulate = True
        ret = self.reader.ParseFromFile(str(self.obj_file), option=config)
        if not ret:
            raise InvalidOBJError(f"Failed to parse {self.obj_file}")
        if not self.reader.Valid() or len(self.reader.GetShapes()) == 0:
            raise InvalidOBJError("Input file contains no OBJ geometry (or is wrong format)")

    @override
    def create_tables(
        self,
    ) -> tuple[Triangles_V1_2_0_Vertices, Triangles_V1_2_0_Indices, EmbeddedTriangulatedMesh_V2_1_0_Parts]:
        """
        Creates the triangles and indices tables, optionally publishing the tables to Evo as it goes.

        :return: Tuple of the vertices GO, Indices GO, chunks array GO
        """
        attrib = self.reader.GetAttrib()
        vertices_array = attrib.numpy_vertices().reshape(-1, 3)
        vertices_table = pa.Table.from_pydict(
            {"x": vertices_array[:, 0], "y": vertices_array[:, 1], "z": vertices_array[:, 2]}, schema=VERTICES_SCHEMA
        )
        del vertices_array

        shapes = self.reader.GetShapes()
        indices_tables = []
        parts_tables = []
        for shape in shapes:
            # This is a workaround for a struct packing issue, see index_t for details
            # index_t is vertex_index, normal_index, texcoord_index
            # we extract only vertex_index, then we group them back into triples of vertices
            faces_array = shape.mesh.numpy_indices().reshape(-1, 3)[:, 0].reshape(-1, 3)
            index_table = pa.Table.from_pydict(
                {"n0": faces_array[:, 0], "n1": faces_array[:, 1], "n2": faces_array[:, 2]}, schema=INDICES_SCHEMA
            )
            del faces_array

            # very short, one-row table
            part_table = pa.Table.from_pydict(
                {"offset": [np.sum([len(v) for v in indices_tables])], "count": [len(index_table)]}, schema=PARTS_SCHEMA
            )
            indices_tables.append(index_table)
            parts_tables.append(part_table)

        # Release memory that we don't need prior to the Parquet transform
        del attrib
        del shapes
        gc.collect()

        parts_table = pa.concat_tables(parts_tables)
        indices_table = pa.concat_tables(indices_tables)

        self._check_tables(vertices_table, indices_table, parts_table)

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
        attrib = self.reader.GetAttrib()
        vertices = attrib.numpy_vertices().reshape(-1, 3)
        return BoundingBox_V1_0_1(
            min_x=vertices[:, 0].min(),
            max_x=vertices[:, 0].max(),
            min_y=vertices[:, 1].min(),
            max_y=vertices[:, 1].max(),
            min_z=vertices[:, 2].min(),
            max_z=vertices[:, 2].max(),
        )
