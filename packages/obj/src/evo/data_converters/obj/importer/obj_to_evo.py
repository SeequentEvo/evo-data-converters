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

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Literal

import trimesh
import pyarrow as pa
import numpy as np

from evo_schemas.components import BaseSpatialDataProperties_V1_0_1
from evo_schemas.objects import TriangleMesh_V2_2_0 as TriangleMeshGo
from evo_schemas.elements import IndexArray2_V1_0_1
from evo_schemas.components import BoundingBox_V1_0_1 as BoundingBoxGo
from evo_schemas.components import (
    Crs_V1_0_1_EpsgCode,
    Triangles_V1_2_0,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
)
from evo.objects.utils import ObjectDataClient

from trimesh import Scene

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.objects.data import ObjectMetadata

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


async def convert_obj(
    filepath: str,
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional[ServiceManagerWidget] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata | dict]:
    """Converts an OBJ file into Geoscience Objects.

    :param filepath: Path to the OBJ file. *Other adjacent files may also be read, eg. MTL file *
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :param publish_objects: (Optional) Set False to prevent publishing and instead return Geoscience models.
    :param overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the destiation path.

    One of evo_workspace_metadata or service_manager_widget is required.

    :return: List of Geoscience Objects and Block Models, or list of ObjectMetadata and Block Models if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """
    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )

    scene = parse_file_to_scene(filepath)
    triangle_mesh = scene_to_trianglemesh(data_client, scene)

    geoscience_objects = [triangle_mesh]

    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects


def parse_file_to_scene(path: str) -> Scene:
    """
    Converts an OBJ file (and any associated files) into a Trimesh Scene object
    :param path: Path to the file
    :return: Trimesh Scene
    """
    scene: trimesh.Scene = trimesh.load(path, force="scene", split_object=True)

    return scene


def scene_to_trianglemesh(data_client: ObjectDataClient, scene: Scene) -> TriangleMeshGo:
    tables = _get_tables(scene)

    vertices_go = Triangles_V1_2_0_Vertices(
        **data_client.save_table(tables["vertices"]),
        attributes=None,
    )
    indices_go = Triangles_V1_2_0_Indices(
        **data_client.save_table(tables["indices"]),
        attributes=None,
    )
    chunks_go = IndexArray2_V1_0_1(**data_client.save_table(tables["parts"]))
    parts_go = EmbeddedTriangulatedMesh_V2_1_0_Parts(attributes=None, chunks=chunks_go, triangle_indices=None)

    triangles_go = Triangles_V1_2_0(vertices=vertices_go, indices=indices_go)

    triangle_mesh_go = TriangleMeshGo(
        name="test mesh",  # FIXME
        uuid=None,
        bounding_box=_get_scene_bbox(scene),
        coordinate_reference_system=Crs_V1_0_1_EpsgCode(epsg_code=4326),  # FIXME
        triangles=triangles_go,
        parts=parts_go,
        # edges don't tend to be used?
    )

    return triangle_mesh_go


def _get_scene_bbox(scene: Scene) -> BoundingBoxGo:
    """
    Converts a Trimesh bounds into a BoundingBox Geoobject
    """
    bounds = scene.bounds
    return BoundingBoxGo(
        min_x=bounds[0][0],
        max_x=bounds[1][0],
        min_y=bounds[0][1],
        max_y=bounds[1][1],
        min_z=bounds[0][2],
        max_z=bounds[1][2],
    )


def _get_tables(scene: Scene) -> dict[Literal["vertices"] | Literal["indices"] | Literal["parts"], pa.Table]:
    vertices_schema = pa.schema([pa.field("x", pa.float64()), pa.field("y", pa.float64()), pa.field("z", pa.float64())])
    # "faces"
    indices_table = pa.schema([pa.field("n0", pa.uint64()), pa.field("n1", pa.uint64()), pa.field("n2", pa.uint64())])

    parts_schema = pa.schema([pa.field("offset", pa.uint64()), pa.field("count", pa.uint64())])

    parts = []
    vertex_count_accum = 0
    for node_name in scene.graph.nodes_geometry:
        # Shift the mesh into world frame
        transform, geom_name = scene.graph.get(node_name)
        mesh = scene.geometry[geom_name].copy()
        mesh.apply_transform(transform)

        vertices_array = np.asarray(mesh.vertices)

        vertex_table = pa.Table.from_pydict(
            {"x": vertices_array[:, 0], "y": vertices_array[:, 1], "z": vertices_array[:, 2]}, schema=vertices_schema
        )
        del vertices_array

        # We need to offset the face indices because the vertices will be concatenated
        faces_array = np.asarray(mesh.faces) + vertex_count_accum
        index_table = pa.Table.from_pydict(
            {"n0": faces_array[:, 0], "n1": faces_array[:, 1], "n2": faces_array[:, 2]}, schema=indices_table
        )
        del faces_array

        # very short, one-row table
        part_table = pa.Table.from_pydict(
            {"offset": [vertex_count_accum], "count": [len(vertex_table)]}, schema=parts_schema
        )

        parts.append({"vertices": vertex_table, "indices": index_table, "part": part_table})

        vertex_count_accum += len(vertex_table)

    return {
        "vertices": pa.concat_tables((p["vertices"] for p in parts)),
        "indices": pa.concat_tables((p["indices"] for p in parts)),
        "parts": pa.concat_tables((p["part"] for p in parts)),
    }
