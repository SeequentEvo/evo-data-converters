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
    Crs_V1_0_1_EpsgCode,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Triangles_V1_2_0,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.objects import TriangleMesh_V2_1_0

import evo.logging
from evo.objects.utils.data import ObjectDataClient

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
        coordinate_reference_system=Crs_V1_0_1_EpsgCode(epsg_code=epsg_code),
        triangles=Triangles_V1_2_0(vertices=vertices_go, indices=indices_go),
        parts=parts_go,
    )
    logger.debug(f"Created: {triangle_mesh_go}")
    return triangle_mesh_go


def combine_duf_polyfaces(
    polyfaces: list[dw.Polyface],
    data_client: ObjectDataClient,
    epsg_code: int,
) -> TriangleMesh_V2_1_0 | None:
    if not polyfaces:
        logger.warning("No polyfaces to combine.")
        return None

    name = get_name(polyfaces[0].Layer)
    logger.debug(f'Combining polyfaces from layer: "{name}" to TriangleMesh_V2_1_0.')

    indices_arrays = []
    for polyface in polyfaces:
        count = int(polyface.FaceList.Count / 5)

        pf_indices_array = (
            np.fromiter(polyface.FaceList, dtype=np.int32, count=count * 5).reshape(count, 5)[:, :3].astype("uint64")
            - 1
        )  # 1-indexed in the file, last element is -1 separator, 2nd last is same as 1st

        indices_arrays.append(pf_indices_array)

    vertices_array, indices_array, parts = obj_list_and_indices_to_arrays(polyfaces, indices_arrays)

    return _create_triangle_mesh_obj(name, vertices_array, indices_array, parts, epsg_code, data_client)


def convert_duf_polyface(
    polyface: dw.Polyface,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> TriangleMesh_V2_1_0:
    name = get_name(polyface)
    logger.debug(f'Converting polyface: "{name}" to TriangleMesh_V2_1_0.')

    num_faces = int(polyface.FaceList.Count / 5)

    indices_array = (
        np.fromiter(polyface.FaceList, dtype=np.int32, count=num_faces * 5).reshape(num_faces, 5)[:, :3] - 1
    )  # 1-indexed in the file, last element is -1 separator, 2nd last is same as 1st
    indices_array = indices_array.astype("uint64")

    vertices_array, indices_array, parts = obj_list_and_indices_to_arrays([polyface], [indices_array])

    return _create_triangle_mesh_obj(name, vertices_array, indices_array, parts, epsg_code, data_client)
