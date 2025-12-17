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
from evo_schemas.objects import LineSegments_V2_0_0, LineSegments_V2_1_0
from omf import LineSetElement, LineSetGeometry
from omf.data import ProjectElementData

from evo.objects.utils.data import ObjectDataClient

from .evo_attributes_to_omf import export_omf_attributes
from .utils import ChunkedData


def export_omf_lineset(
    object_id: UUID,
    version_id: Optional[str],
    linesegments_go: LineSegments_V2_0_0 | LineSegments_V2_1_0,
    data_client: ObjectDataClient,
) -> LineSetElement:
    vertices_table = asyncio.run(
        data_client.download_table(object_id, version_id, linesegments_go.segments.vertices.as_dict())
    )
    vertices = np.asarray(vertices_table)

    vertex_attribute_data = export_omf_attributes(
        object_id, version_id, linesegments_go.segments.vertices.attributes, "vertices", data_client
    )

    segments_table = asyncio.run(
        data_client.download_table(object_id, version_id, linesegments_go.segments.indices.as_dict())
    )
    segments = np.asarray(segments_table)

    segments_attribute_data = export_omf_attributes(
        object_id, version_id, linesegments_go.segments.indices.attributes, "segments", data_client
    )

    if linesegments_go.parts:
        chunks_table = asyncio.run(
            data_client.download_table(object_id, version_id, linesegments_go.parts.chunks.as_dict())
        )
        chunks = np.asarray(chunks_table)

        chunks_attribute_data = export_omf_attributes(
            object_id, version_id, linesegments_go.parts.attributes, "segments", data_client
        )

        # compute the new segments and their attributes, if available
        chunked_data = ChunkedData(data=segments, chunks=chunks, attributes=chunks_attribute_data)
        segments = chunked_data.unpack()
    else:
        chunks_attribute_data = []

    data: list[ProjectElementData] = []
    data.extend(vertex_attribute_data)
    data.extend(segments_attribute_data)
    data.extend(chunks_attribute_data)

    element_description = linesegments_go.description if linesegments_go.description else ""
    return LineSetElement(
        name=linesegments_go.name,
        description=element_description,
        geometry=LineSetGeometry(vertices=vertices, segments=segments),
        data=data,
    )
