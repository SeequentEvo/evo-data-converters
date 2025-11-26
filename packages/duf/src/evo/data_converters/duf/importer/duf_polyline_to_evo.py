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
from evo_schemas.components import (
    Segments_V1_2_0,
    Segments_V1_2_0_Indices,
    Segments_V1_2_0_Vertices,
)
from evo_schemas.objects import LineSegments_V2_1_0, LineSegments_V2_1_0_Parts

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from evo.data_converters.common import crs_from_epsg_code
from evo.data_converters.duf.common.consts import EvoSchema
import evo.data_converters.duf.common.deswik_types as dw
from .utils import (
    get_name,
    vertices_array_to_go_and_bbox,
    indices_array_to_go,
    parts_to_go,
    obj_list_and_indices_to_arrays,
)

logger = evo.logging.getLogger("data_converters")


def _create_line_segments_obj(name, vertices_array, indices_array, parts, epsg_code, data_client):
    vertices_go, bounding_box_go = vertices_array_to_go_and_bbox(data_client, vertices_array, Segments_V1_2_0_Vertices)

    indices_go = indices_array_to_go(data_client, indices_array, Segments_V1_2_0_Indices)

    parts_go = parts_to_go(data_client, parts, LineSegments_V2_1_0_Parts)

    line_segments_go = LineSegments_V2_1_0(
        name=name,
        uuid=None,
        bounding_box=bounding_box_go,
        coordinate_reference_system=crs_from_epsg_code(epsg_code),
        segments=Segments_V1_2_0(vertices=vertices_go, indices=indices_go),
        parts=parts_go,
    )
    logger.debug(f"Created: {line_segments_go}")
    return line_segments_go


def _polyline_indices_array(num_vertices):
    return np.column_stack(
        (
            np.arange(0, num_vertices - 1, dtype="uint64"),
            np.arange(1, num_vertices, dtype="uint64"),
        )
    )


def combine_duf_polylines(
    polylines: list[dw.Polyline],
    data_client: ObjectDataClient,
    epsg_code: int,
) -> LineSegments_V2_1_0 | None:
    if not polylines:
        logger.warning("No polylines to combine.")
        return None

    layer = get_name(polylines[0].Layer)
    name = f"{layer} - polylines"
    logger.debug(f'Combining polylines from layer: "{layer}" to LineSegments_V2_1_0.')

    indices_arrays = []
    for i, polyline in enumerate(polylines):
        if i % 1000 == 0:
            logger.info(f"Processed {i} polylines")
        pl_num_vertices = polyline.VertexList.Count
        pl_indices_array = _polyline_indices_array(pl_num_vertices)
        indices_arrays.append(pl_indices_array)

    vertices_array, indices_array, parts = obj_list_and_indices_to_arrays(
        polylines, indices_arrays, EvoSchema.line_segments
    )

    return _create_line_segments_obj(name, vertices_array, indices_array, parts, epsg_code, data_client)


def convert_duf_polyline(
    polyline: dw.Polyline,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> LineSegments_V2_1_0:
    name = get_name(polyline)
    logger.debug(f'Converting polyline: "{name}" to LineSegments_V2_1_0.')

    num_vertices = polyline.VertexList.Count

    indices_array = _polyline_indices_array(num_vertices)

    vertices_array, indices_array, parts = obj_list_and_indices_to_arrays(
        [polyline], [indices_array], EvoSchema.line_segments
    )

    return _create_line_segments_obj(name, vertices_array, indices_array, parts, epsg_code, data_client)
