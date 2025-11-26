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
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Triangles_V1_2_0,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.objects import TriangleMesh_V2_1_0

import evo.logging
from evo.objects.utils.data import ObjectDataClient
from numpy._typing import NDArray

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


def _create_triangle_mesh_obj(name, vertices_array, indices_array, parts, epsg_code, data_client):
    vertices_go, bounding_box_go = vertices_array_to_go_and_bbox(data_client, vertices_array, Triangles_V1_2_0_Vertices)

    indices_go = indices_array_to_go(data_client, indices_array, Triangles_V1_2_0_Indices)

    parts_go = parts_to_go(data_client, parts, EmbeddedTriangulatedMesh_V2_1_0_Parts)

    triangle_mesh_go = TriangleMesh_V2_1_0(
        name=name,
        uuid=None,
        bounding_box=bounding_box_go,
        coordinate_reference_system=crs_from_epsg_code(epsg_code),
        triangles=Triangles_V1_2_0(vertices=vertices_go, indices=indices_go),
        parts=parts_go,
    )
    logger.debug(f"Created: {triangle_mesh_go}")
    return triangle_mesh_go


def indices_from_polyface(dw_facelist) -> NDArray[np.uint64]:
    """
    Extracts triangles from the PolyFace's FaceList.

    Returns a numpy uint64 array of shape (*, 3).

    The FaceList is a flat integer array. Each face is represented by 5 consecutive integers. The faces can be triangles
    or quads.
    - triangle: [..., 1, 2, 3, 1, -1, ...]
    - quad: [..., 1, 2, 3, 4, -1, ...]
    The first four integers describe the triangle/quad. The 5th integer can optionally represent colour information,
    but we don't care about this and I don't know the details.

    The FaceList is 1-indexed, and indices can be negative. Indices being negative has a special meaning for the
    visibility of parts of the geometry, but we ignore that and force everything to be positive.
    """
    count = dw_facelist.Count // 5
    assert dw_facelist.Count % 5 == 0, f"Expected a multiple of 5 indicies, but got {dw_facelist.Count}"

    # The indices are 1-indexed and possibly negative
    indices_arr = np.abs(np.fromiter(dw_facelist, dtype=np.int32, count=count * 5).reshape(count, 5)) - 1

    # Triangles repeat the 0th and 3rd indices, and quads have 4 distinct indices (not considering degenerate cases)
    quads_mask = indices_arr[:, 0] != indices_arr[:, 3]

    # The first three indices are either the entire triangle we care about, or the first half of a quad
    tris = indices_arr[:, [0, 1, 2]]

    # Split off an extra triangle for each quad
    extra_tris_from_quads = indices_arr[quads_mask][:, [2, 3, 0]]

    result = np.vstack([tris, extra_tris_from_quads])

    # We're not expecting the FaceList to have indices of `0`, which will have been shifted to `-1` by this point.
    rows_with_negative_value = np.any(result < 0, axis=1)
    if rows_with_negative_value.any():
        msg = "The FaceList values were expected to be 1-index, but there was a zero value"
        assert False, msg
        logger.error(msg)

    return result[~rows_with_negative_value].astype("uint64")


def combine_duf_polyfaces(
    polyfaces: list[dw.Polyface],
    data_client: ObjectDataClient,
    epsg_code: int,
) -> TriangleMesh_V2_1_0 | None:
    if not polyfaces:
        logger.warning("No polyfaces to combine.")
        return None

    layer = get_name(polyfaces[0].Layer)
    name = f"{layer} - polyfaces"
    logger.debug(f'Combining polyfaces from layer: "{layer}" to TriangleMesh_V2_1_0.')

    indices_arrays = []
    for i, polyface in enumerate(polyfaces):
        if i % 1000 == 0:
            logger.info(f"Processed {i} polyfaces")
        indices_arrays.append(indices_from_polyface(polyface.FaceList))

    vertices_array, indices_array, parts = obj_list_and_indices_to_arrays(
        polyfaces, indices_arrays, EvoSchema.triangle_mesh
    )

    return _create_triangle_mesh_obj(name, vertices_array, indices_array, parts, epsg_code, data_client)


def convert_duf_polyface(
    polyface: dw.Polyface,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> TriangleMesh_V2_1_0:
    name = get_name(polyface)
    logger.debug(f'Converting polyface: "{name}" to TriangleMesh_V2_1_0.')

    indices_array = indices_from_polyface(polyface.FaceList)

    vertices_array, indices_array, parts = obj_list_and_indices_to_arrays(
        [polyface], [indices_array], EvoSchema.triangle_mesh
    )

    return _create_triangle_mesh_obj(name, vertices_array, indices_array, parts, epsg_code, data_client)
