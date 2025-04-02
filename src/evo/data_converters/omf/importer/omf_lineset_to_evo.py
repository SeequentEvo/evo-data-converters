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

import omf2
import pyarrow as pa
from evo_schemas.components import (
    Crs_V1_0_1_EpsgCode,
    Segments_V1_2_0,
    Segments_V1_2_0_Indices,
    Segments_V1_2_0_Vertices,
)
from evo_schemas.objects import LineSegments_V2_1_0

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from ...common.utils import vertices_bounding_box
from .omf_attributes_to_evo import convert_omf_attributes

logger = evo.logging.getLogger("data_converters")


def convert_omf_lineset(
    lineset: omf2.Element,
    project: omf2.Project,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> LineSegments_V2_1_0:
    logger.debug(f'Converting omf2 Element: "{lineset.name}" to LineSegments_V2_0_0.')

    coordinate_reference_system = Crs_V1_0_1_EpsgCode(epsg_code=epsg_code)

    geometry: omf2.LineSet = lineset.geometry()

    # Convert vertices to absolute position in world space by adding the project and geometry origin
    vertices_array = reader.array_vertices(geometry.vertices) + project.origin + geometry.origin
    segments_array = reader.array_segments(geometry.segments)

    bounding_box_go = vertices_bounding_box(vertices_array)

    vertices_schema = pa.schema(
        [
            pa.field("x", pa.float64()),
            pa.field("y", pa.float64()),
            pa.field("z", pa.float64()),
        ]
    )

    segment_indices_schema = pa.schema([pa.field("n0", pa.uint64()), pa.field("n1", pa.uint64())])

    vertices_table = pa.Table.from_arrays(
        [pa.array(vertices_array[:, i], type=pa.float64()) for i in range(len(vertices_schema))],
        schema=vertices_schema,
    )

    segment_indices_table = pa.Table.from_arrays(
        [pa.array(segments_array[:, i], type=pa.uint64()) for i in range(len(segment_indices_schema))],
        schema=segment_indices_schema,
    )

    vertex_attributes_go = convert_omf_attributes(lineset, reader, data_client, omf2.Location.Vertices)
    line_attributes_go = convert_omf_attributes(lineset, reader, data_client, omf2.Location.Primitives)

    vertices_go = Segments_V1_2_0_Vertices(**data_client.save_table(vertices_table), attributes=vertex_attributes_go)

    segment_indices_go = Segments_V1_2_0_Indices(
        **data_client.save_table(segment_indices_table), attributes=line_attributes_go
    )

    line_segments_go = LineSegments_V2_1_0(
        name=lineset.name,
        uuid=None,
        bounding_box=bounding_box_go,
        coordinate_reference_system=coordinate_reference_system,
        segments=Segments_V1_2_0(vertices=vertices_go, indices=segment_indices_go),
    )

    logger.debug(f"Created: {line_segments_go}")

    return line_segments_go
