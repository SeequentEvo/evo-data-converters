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

import vtk
import vtkmodules
import vtk.util.numpy_support as ns

import pyarrow as pa

from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
)
from evo_schemas.elements import IndexArray2_V1_0_1

from .base import ObjImporterBase, VERTICES_SCHEMA, INDICES_SCHEMA, PARTS_SCHEMA, UnsupportedOBJError, InvalidOBJError


class VtkObjImporter(ObjImporterBase):
    """
    An implementation of OBJ import using the VTK library.

    There is no compelling reason to use this implementation except that it's also used for the
    VTK converter, so is already available. In future if performance improves it may become a
    recommended option.
    """

    reader: vtkmodules.vtkIOCore.vtkAbstractPolyDataReader

    @override
    def _parse_file(self) -> None:
        """
        Opens and validates the OBJ file, creating a native representation of it.
        """

        def error_handler(caller, event) -> None:
            raise InvalidOBJError(f"Parse error {event}")

        self.reader = vtk.vtkOBJReader()
        self.reader.AddObserver("ErrorEvent", error_handler)
        self.reader.AddObserver("WarningEvent", error_handler)
        self.reader.SetFileName(str(self.obj_file))
        self.reader.Update()
        if self.reader.GetOutput() is None or self.reader.GetOutput().GetNumberOfPoints() == 0:
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
        polydata = self.reader.GetOutput()

        # We don't currently implement triangulation in VTK
        if polydata.polys.max_cell_size > 3:
            raise UnsupportedOBJError("VTK importer only supports triangular OBJ meshes")

        vtk_points = polydata.GetPoints()
        vertices = ns.vtk_to_numpy(vtk_points.GetData())

        vertices_table = pa.Table.from_pydict(
            {"x": vertices[:, 0], "y": vertices[:, 1], "z": vertices[:, 2]},
            schema=VERTICES_SCHEMA,
        )

        vtk_cells = polydata.GetPolys()
        cell_array = ns.vtk_to_numpy(vtk_cells.GetData())

        triangles = cell_array.reshape(-1, 4)[:, 1:]

        indices_table = pa.Table.from_pydict(
            {"n0": triangles[:, 0], "n1": triangles[:, 1], "n2": triangles[:, 2]}, schema=INDICES_SCHEMA
        )

        # not supporting multiple parts yet
        parts_table = pa.Table.from_pydict({"offset": [0], "count": [len(vertices_table)]}, schema=PARTS_SCHEMA)

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
        Generates the bounding box GeoObject of the vertices in the world scene.

        :return: Bounding Box GeoObject with coordinates of the boundaries
        """
        polydata = self.reader.GetOutput()
        bounds = polydata.GetBounds()
        return BoundingBox_V1_0_1(
            min_x=bounds[0],
            max_x=bounds[1],
            min_y=bounds[2],
            max_y=bounds[3],
            min_z=bounds[4],
            max_z=bounds[5],
        )
