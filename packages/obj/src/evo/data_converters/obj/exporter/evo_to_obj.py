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

from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import numpy as np
import trimesh
from evo_schemas import schema_lookup
from evo_schemas.components import Crs_V1_0_1_EpsgCode
from evo_schemas.objects import TriangleMesh_V2_0_0, TriangleMesh_V2_1_0, TriangleMesh_V2_2_0
from trimesh.exchange.export import export_scene

import evo.logging
from evo.data_converters.common import (
    EvoObjectMetadata,
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.objects.client import ObjectAPIClient
from evo.objects.data import ObjectSchema
from evo.objects.utils.data import ObjectDataClient

from .part_utils import ChunkedData, IndexedData

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


class UnsupportedObjectError(Exception):
    pass


logger = evo.logging.getLogger("data_converters")


async def export_obj(
    filepath: str,
    objects: list[EvoObjectMetadata],
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional[ServiceManagerWidget] = None,
) -> None:
    """Export Evo Geoscience Objects to an OBJ file.

    :param filepath: Path of the OBJ file to create.
    :param objects: List of EvoObjectMetadata objects containing the UUID and version of the Evo objects to export.
    :param evo_workspace_metadata: Optional Evo Workspace metadata.
    :param service_manager_widget: Optional ServiceManagerWidget for use in notebooks.

    One of evo_workspace_metadata or service_manager_widget is required.

    :raise UnsupportedObjectError: If the type of object is not supported.
    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """

    service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata, service_manager_widget
    )

    scene = trimesh.Scene()
    for object_metadata in objects:
        mesh, obj_description = await _evo_object_to_trimesh(object_metadata, service_client, data_client)
        scene.add_geometry(mesh)

    # Header is a one line description
    header = "Evo Data Converters"
    if len(objects) == 1:
        header += f"; {obj_description}"

    export_scene(scene, filepath, file_type="obj", header=header)


async def _download_evo_object_by_id(
    service_client: ObjectAPIClient,
    object_id: UUID,
    version_id: Optional[str] = None,
) -> dict[str, Any]:
    downloaded_object = await service_client.download_object_by_id(object_id, version_id)
    result: dict[str, Any] = downloaded_object.as_dict()
    return result


async def _evo_object_to_trimesh(
    object_metadata: EvoObjectMetadata,
    service_client: ObjectAPIClient,
    data_client: ObjectDataClient,
) -> tuple[trimesh.Trimesh, str]:
    object_id = object_metadata.object_id
    version_id = object_metadata.version_id

    # Download object
    geoscience_object_dict = await _download_evo_object_by_id(service_client, object_id, version_id)

    # Check if this is a known geoscience object schema type
    schema = ObjectSchema.from_id(geoscience_object_dict["schema"])
    object_class = schema_lookup.get(str(schema))

    if not object_class:
        raise UnsupportedObjectError(f"Unknown Geoscience Object schema '{schema}'")

    geoscience_object = object_class.from_dict(geoscience_object_dict)

    # Convert to Trimesh
    if schema.classification == "objects/triangle-mesh" and schema.version.major == 2:
        mesh = await _triangle_mesh_to_trimesh(object_id, version_id, geoscience_object, data_client)
    else:
        raise UnsupportedObjectError(
            f"Exporting {geoscience_object.__class__.__name__} Geoscience Objects to OBJ is not supported"
        )

    description = f"Object ID={object_id}"

    crs = geoscience_object.coordinate_reference_system
    if isinstance(crs, Crs_V1_0_1_EpsgCode):
        description += f", EPSG={crs.epsg_code}"

    return mesh, description


async def _triangle_mesh_to_trimesh(
    object_id: UUID,
    version_id: Optional[str],
    triangle_mesh_go: TriangleMesh_V2_0_0 | TriangleMesh_V2_1_0 | TriangleMesh_V2_2_0,
    data_client: ObjectDataClient,
) -> trimesh.Trimesh:
    vertices_table = await data_client.download_table(
        object_id, version_id, triangle_mesh_go.triangles.vertices.as_dict()
    )
    vertices = np.asarray(vertices_table)

    triangles_table = await data_client.download_table(
        object_id, version_id, triangle_mesh_go.triangles.indices.as_dict()
    )
    triangles = np.asarray(triangles_table)

    if parts := triangle_mesh_go.parts:
        if parts.triangle_indices:
            # get triangle indices and convert into triangles before chunking
            triangle_indices_table = await data_client.download_table(
                object_id, version_id, parts.triangle_indices.as_dict()
            )
            triangle_indices = np.asarray(triangle_indices_table)

            indexed_data = IndexedData(data=triangles, indices=triangle_indices)
            triangles = indexed_data.unpack()

        chunks_table = await data_client.download_table(object_id, version_id, parts.chunks.as_dict())
        chunks = np.asarray(chunks_table)

        # can skip handling chunks if just one chunk of the current list of triangles
        # NOTE: this exporter doesn't currently use the attributes associated with chunks,
        # if it did this would need to change
        single_contiguous_chunk = False
        if len(chunks) == 1 and chunks[0][0] == 0:
            expected_triangle_count = len(triangles)
            if chunks[0][1] == expected_triangle_count:
                single_contiguous_chunk = True
            else:
                logger.warning(
                    f"Chunk does not have expected triangle count. {chunks[0][1]} != {expected_triangle_count}"
                )

        if not single_contiguous_chunk:
            # expand chunks into one list of triangles
            chunked_data = ChunkedData(data=triangles, chunks=chunks)
            triangles = chunked_data.unpack()

    return trimesh.Trimesh(vertices=vertices, faces=triangles, process=False, validate=False)
