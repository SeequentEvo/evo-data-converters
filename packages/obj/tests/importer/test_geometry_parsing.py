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

import math
from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from evo_schemas.components import (
    Crs_V1_0_1_EpsgCode,
)
from evo_schemas.objects import TriangleMesh_V2_2_0

from evo.data_converters.common import (
    create_evo_object_service_and_data_client,
)
from evo.data_converters.common.test_tools import EvoDataConvertersTestCase
from evo.data_converters.obj.importer.implementation.base import UnsupportedOBJError
from evo.data_converters.obj.importer.obj_to_evo import convert_obj
from evo.objects.utils.tables import KnownTableFormat

# Specify the simple_shapes.obj in terms of its faces, as different parsers format the faces and vertices
# in different orders, but the total set of vertices and faces should always be there.
simple_shape_faces = pd.DataFrame(
    columns=["object", "n0", "n1", "n2"],
    data=[
        # ---- Cube ----
        ("Cube", (174.79, -41.29, -0.5), (175.29, -41.29, -0.5), (175.29, -40.79, -0.5)),
        ("Cube", (174.79, -41.29, -0.5), (175.29, -40.79, -0.5), (174.79, -40.79, -0.5)),
        ("Cube", (174.79, -41.29, 0.5), (174.79, -40.79, 0.5), (175.29, -40.79, 0.5)),
        ("Cube", (174.79, -41.29, 0.5), (175.29, -40.79, 0.5), (175.29, -41.29, 0.5)),
        ("Cube", (174.79, -41.29, -0.5), (174.79, -41.29, 0.5), (175.29, -41.29, 0.5)),
        ("Cube", (174.79, -41.29, -0.5), (175.29, -41.29, 0.5), (175.29, -41.29, -0.5)),
        ("Cube", (175.29, -41.29, -0.5), (175.29, -41.29, 0.5), (175.29, -40.79, 0.5)),
        ("Cube", (175.29, -41.29, -0.5), (175.29, -40.79, 0.5), (175.29, -40.79, -0.5)),
        ("Cube", (175.29, -40.79, -0.5), (175.29, -40.79, 0.5), (174.79, -40.79, 0.5)),
        ("Cube", (175.29, -40.79, -0.5), (174.79, -40.79, 0.5), (174.79, -40.79, -0.5)),
        ("Cube", (174.79, -40.79, -0.5), (174.79, -40.79, 0.5), (174.79, -41.29, 0.5)),
        ("Cube", (174.79, -40.79, -0.5), (174.79, -41.29, 0.5), (174.79, -41.29, -0.5)),
        # ---- Pyramid ----
        ("Pyramid", (174.79, -41.29, 1.0), (175.29, -41.29, 1.0), (175.04, -40.79, 1.0)),
        ("Pyramid", (174.79, -41.29, 1.0), (175.04, -40.79, 1.0), (174.54, -40.79, 1.0)),
        ("Pyramid", (174.79, -41.29, 1.0), (175.29, -41.29, 1.0), (174.915, -41.045, 2.0)),
        ("Pyramid", (175.29, -41.29, 1.0), (175.04, -40.79, 1.0), (174.915, -41.045, 2.0)),
        ("Pyramid", (175.04, -40.79, 1.0), (174.54, -40.79, 1.0), (174.915, -41.045, 2.0)),
        ("Pyramid", (174.54, -40.79, 1.0), (174.79, -41.29, 1.0), (174.915, -41.045, 2.0)),
    ],
)


class TestObjGeometryParsing(EvoDataConvertersTestCase):
    implementation: str = "trimesh"

    def setUp(self) -> None:
        EvoDataConvertersTestCase.setUp(self)
        _, data_client = create_evo_object_service_and_data_client(self.workspace_metadata)
        self.data_client = data_client

    async def _make_geoobject(self, filename: str = "simple_shapes.obj") -> TriangleMesh_V2_2_0:
        obj_file = Path(__file__).parent.parent / "data" / "simple_shapes" / filename

        (triangle_mesh,) = await convert_obj(
            filepath=obj_file,
            evo_workspace_metadata=self.workspace_metadata,
            epsg_code=4326,
            publish_objects=False,
            implementation=self.implementation,
        )

        return triangle_mesh

    def _get_dataframe_for_table(self, table_info: dict) -> pd.DataFrame:
        if not isinstance(table_info, dict):
            table_info = table_info.as_dict()
        return KnownTableFormat.load_table(table_info, self.data_client.cache_location).to_pandas()

    async def test_geoobject_complete(self) -> None:
        triangle_mesh = await self._make_geoobject()

        assert isinstance(triangle_mesh, TriangleMesh_V2_2_0), "GeoObject is TriangleMesh_V2_2_0"

        assert triangle_mesh.name == "simple_shapes.obj"
        assert triangle_mesh.description is None
        assert triangle_mesh.tags == {
            "Source": "simple_shapes.obj (via Evo Data Converters)",
            "Stage": "Experimental",
            "InputType": "OBJ",
        }
        assert triangle_mesh.coordinate_reference_system == Crs_V1_0_1_EpsgCode(epsg_code=4326)

        assert math.isclose(triangle_mesh.bounding_box.min_x, 174.54, rel_tol=0.01)
        assert math.isclose(triangle_mesh.bounding_box.max_x, 175.29, rel_tol=0.01)
        assert math.isclose(triangle_mesh.bounding_box.min_y, -41.29, rel_tol=0.01)
        assert math.isclose(triangle_mesh.bounding_box.max_y, -40.79, rel_tol=0.01)
        assert math.isclose(triangle_mesh.bounding_box.min_z, -0.5, rel_tol=0.01)
        assert math.isclose(triangle_mesh.bounding_box.max_z, 2.0, rel_tol=0.01)

        # We're not using edges
        assert triangle_mesh.edges is None

        assert triangle_mesh.triangles.indices is not None
        assert triangle_mesh.triangles.vertices is not None
        assert triangle_mesh.parts.chunks is not None

        # We're not using triangle_indices
        assert triangle_mesh.parts.triangle_indices is None

    async def test_correct_vertices(self) -> None:
        triangle_mesh = await self._make_geoobject()
        vertices = self._get_dataframe_for_table(triangle_mesh.triangles.vertices).drop_duplicates()

        # Extract the unique set of vertices from the faces and make sure all those vertices exist in the table
        correct_vertices = pd.Series(simple_shape_faces[["n0", "n1", "n2"]].values.ravel()).drop_duplicates()
        matches: list[bool] = []
        for vertex in correct_vertices:
            found = False
            for _, vertex2 in vertices.iterrows():
                if np.allclose(vertex, vertex2):
                    found = True
                    break
            matches.append(found)

        intersection = correct_vertices[matches]
        assert len(intersection) == len(vertices)
        assert len(correct_vertices) == len(vertices)

    def _make_face_vertices_sets(self, vertices: pd.DataFrame, faces: pd.DataFrame) -> pd.Series:
        """
        Zips a faces frame of n0/n1/n2 vertices references to a vertices frame by row reference,
        making a new Series that contains all the triples of x/y/z coordinates.
        """
        face_rows = []
        for _, face in faces.iterrows():
            face_rows.append(
                (
                    tuple(vertices.iloc[face["n0"]][["x", "y", "z"]].values),
                    tuple(vertices.iloc[face["n1"]][["x", "y", "z"]].values),
                    tuple(vertices.iloc[face["n2"]][["x", "y", "z"]].values),
                )
            )
        return pd.Series(face_rows)

    def _compare_face_sets(self, faces1: pd.Series, faces2: pd.Series) -> bool:
        """
        Helper that takes two Series where each element is a face triple of x/y/z tuples
        returning True if the two Series are equivalent (with fuzzy float comparison).
        """
        matches = []
        for face1 in faces1:
            found = False
            for face2 in faces2:
                if np.allclose(np.sort(face1, axis=0), np.sort(face2, axis=0), atol=1e-3):
                    found = True
                    break
            matches.append(found)

        intersection = faces1[matches]
        return len(intersection) == len(faces2) == len(faces1)

    async def test_correct_faces(self) -> None:
        triangle_mesh = await self._make_geoobject()
        faces = self._get_dataframe_for_table(triangle_mesh.triangles.indices)
        vertices = self._get_dataframe_for_table(triangle_mesh.triangles.vertices)
        assert len(faces) == len(simple_shape_faces), "Check number of faces is correct"

        face_vertex_sets = self._make_face_vertices_sets(vertices, faces)

        # Produce an equivalent set of the correct faces
        correct_face_vertex_sets = simple_shape_faces[["n0", "n1", "n2"]].apply(lambda r: tuple(r), axis=1)

        assert self._compare_face_sets(face_vertex_sets, correct_face_vertex_sets), (
            "Check all faces have the right triple of vertices"
        )

    async def test_correct_parts(self) -> None:
        triangle_mesh = await self._make_geoobject()
        chunks = self._get_dataframe_for_table(triangle_mesh.parts.chunks)
        faces = self._get_dataframe_for_table(triangle_mesh.triangles.indices)
        vertices = self._get_dataframe_for_table(triangle_mesh.triangles.vertices)

        assert len(chunks) == 2, "Cube and Pyramid should form two chunks"

        # We now need to slice up the triangles table chunk by chunk to ensure they have the right vertices
        for _, chunk in chunks.iterrows():
            chunk_indices = faces.iloc[chunk["offset"] : chunk["offset"] + chunk["count"]]
            assert len(chunk_indices) == chunk["count"]

            if len(chunk_indices) == 12:
                # This should match the cube faces
                cube_vertex_sets = self._make_face_vertices_sets(vertices, chunk_indices)
                correct_cube_vertex_sets = simple_shape_faces[simple_shape_faces["object"] == "Cube"][
                    ["n0", "n1", "n2"]
                ].apply(lambda r: tuple(r), axis=1)
                assert self._compare_face_sets(cube_vertex_sets, correct_cube_vertex_sets), (
                    "Check the Cube part has the right vertices"
                )
            else:
                # This should match the pyramid faces
                pyramid_vertex_sets = self._make_face_vertices_sets(vertices, chunk_indices)
                correct_pyramid_vertex_sets = simple_shape_faces[simple_shape_faces["object"] == "Pyramid"][
                    ["n0", "n1", "n2"]
                ].apply(lambda r: tuple(r), axis=1)
                assert self._compare_face_sets(pyramid_vertex_sets, correct_pyramid_vertex_sets), (
                    "Check the Pyramid part has the right vertices"
                )

    async def test_quad_triangulation(self) -> None:
        """
        It's difficult to correctly assert the conversion to triangles from quads, but we'll do some rudimentary tests.
        """
        try:
            triangle_mesh = await self._make_geoobject(filename="simple_shapes_quad.obj")
        except UnsupportedOBJError:
            pytest.skip(f"{self.implementation} doesn't support triangulation")

        # Perform the same vertices check as test_correct_vertices() as at least the vertices shouldn't have moved
        vertices = self._get_dataframe_for_table(triangle_mesh.triangles.vertices).drop_duplicates()

        correct_vertices = pd.Series(simple_shape_faces[["n0", "n1", "n2"]].values.ravel()).drop_duplicates()
        matches: list[bool] = []
        for vertex in correct_vertices:
            found = False
            for _, vertex2 in vertices.iterrows():
                if np.allclose(vertex, vertex2):
                    found = True
                    break
            matches.append(found)

        intersection = correct_vertices[matches]
        assert len(intersection) == len(vertices)
        assert len(correct_vertices) == len(vertices)


@pytest.mark.skipif(find_spec("tinyobjloader") is None, reason="tinyobj not installed")
class TestObjGeometryParsingTinyObj(TestObjGeometryParsing):
    implementation = "tinyobj"
