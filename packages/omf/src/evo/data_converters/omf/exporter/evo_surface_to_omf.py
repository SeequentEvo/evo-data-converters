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
from typing import Optional
from uuid import UUID

import numpy as np
from evo_schemas.objects import TriangleMesh_V2_0_0, TriangleMesh_V2_1_0
from omf import SurfaceElement, SurfaceGeometry
from omf.data import ProjectElementData

from evo.objects.utils.data import ObjectDataClient

from .evo_attributes_to_omf import export_omf_attributes
from .utils import ChunkedData, IndexedData


def export_omf_surface(
    object_id: UUID,
    version_id: Optional[str],
    surface_go: TriangleMesh_V2_0_0 | TriangleMesh_V2_1_0,
    data_client: ObjectDataClient,
) -> SurfaceElement:
    vertices_table = asyncio.run(
        data_client.download_table(object_id, version_id, surface_go.triangles.vertices.as_dict())
    )
    vertices = np.asarray(vertices_table)

    vertex_attribute_data = export_omf_attributes(
        object_id, version_id, surface_go.triangles.vertices.attributes, "vertices", data_client
    )

    triangles_table = asyncio.run(
        data_client.download_table(object_id, version_id, surface_go.triangles.indices.as_dict())
    )
    triangles = np.asarray(triangles_table)

    triangles_attribute_data = export_omf_attributes(
        object_id, version_id, surface_go.triangles.indices.attributes, "faces", data_client
    )

    if parts := surface_go.parts:
        if parts.triangle_indices:
            # parse optional triangle_indices data as a preprocessing step
            triangle_indices_table = asyncio.run(
                data_client.download_table(object_id, version_id, parts.triangle_indices.as_dict())
            )
            triangle_indices = np.asarray(triangle_indices_table)

            # preprocess triangles and their attributes before chunking
            indexed_data = IndexedData(data=triangles, indices=triangle_indices, attributes=triangles_attribute_data)
            triangles = indexed_data.unpack()

        chunks_table = asyncio.run(data_client.download_table(object_id, version_id, parts.chunks.as_dict()))
        chunks = np.asarray(chunks_table)

        chunks_attribute_data = export_omf_attributes(object_id, version_id, parts.attributes, "segments", data_client)

        # compute the new triangles and their attributes, if available
        chunked_data = ChunkedData(data=triangles, chunks=chunks, attributes=chunks_attribute_data)
        triangles = chunked_data.unpack()
    else:
        chunks_attribute_data = []

    data: list[ProjectElementData] = []
    data.extend(vertex_attribute_data)
    data.extend(triangles_attribute_data)
    data.extend(chunks_attribute_data)

    element_description = surface_go.description if surface_go.description else ""
    return SurfaceElement(
        name=surface_go.name,
        description=element_description,
        geometry=SurfaceGeometry(vertices=vertices, triangles=triangles),
        data=data,
    )
