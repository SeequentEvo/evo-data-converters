import numpy as np
import pyarrow as pa
from evo_schemas.components import (
    Crs_V1_0_1_EpsgCode,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    Triangles_V1_2_0,
    Triangles_V1_2_0_Indices,
    Triangles_V1_2_0_Vertices,
)
from evo_schemas.elements import IndexArray2_V1_0_1
from evo_schemas.objects import TriangleMesh_V2_1_0

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from evo.data_converters.common.utils import vertices_bounding_box
from ..common import Polyface
from .utils import get_name
from .duf_attributes_to_evo import convert_duf_attributes

logger = evo.logging.getLogger("data_converters")


def convert_duf_polyface(
    surface: Polyface,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> TriangleMesh_V2_1_0:
    name = get_name(surface)
    logger.debug(f'Converting Polyface: "{name}" to TriangleMesh_V2_1_0.')

    coordinate_reference_system = Crs_V1_0_1_EpsgCode(epsg_code=epsg_code)

    num_faces = int(surface.FaceList.Count / 5)
    num_vertices = surface.VertexList.Count

    indices_array = (
        np.fromiter(surface.FaceList, dtype=np.int32, count=num_faces * 5).reshape(num_faces, 5)[:, :3] - 1
    )  # 1-indexed in the file, last element is -1 separator, 2nd last is same as 1st
    indices_array = indices_array.astype("uint64")

    axes = ("X", "Y", "Z")
    vertices_array = np.fromiter(
        (getattr(vert, axis) for vert in surface.VertexList for axis in axes),
        dtype=np.float64,
        count=num_vertices * 3,
    ).reshape(num_vertices, 3)
    logger.debug(f"Indices: {indices_array.shape}")
    logger.debug(f"Vertices: {vertices_array.shape}")

    attributes = (
        [(xprop.Key, xprop.Value.Value[0].Value) for xprop in surface.XProperties] if surface.XProperties else []
    )
    logger.debug(f"Num Surface Attributes: {len(attributes)}")

    bounding_box_go = vertices_bounding_box(vertices_array)

    vertices_schema = pa.schema(
        [
            pa.field("x", pa.float64()),
            pa.field("y", pa.float64()),
            pa.field("z", pa.float64()),
        ]
    )

    indices_schema = pa.schema(
        [
            pa.field("x", pa.uint64()),
            pa.field("y", pa.uint64()),
            pa.field("z", pa.uint64()),
        ]
    )

    vertices_table = pa.Table.from_arrays(
        [pa.array(vertices_array[:, i], type=pa.float64()) for i in range(len(vertices_schema))],
        schema=vertices_schema,
    )

    indices_table = pa.Table.from_arrays(
        [pa.array(indices_array[:, i], type=pa.uint64()) for i in range(len(indices_schema))],
        schema=indices_schema,
    )

    if attributes:
        # Use parts to store object-level attributes
        surface_attributes_go = convert_duf_attributes(attributes, data_client)
        parts_table = pa.Table.from_arrays(
            [pa.array([0], type=pa.uint64()), pa.array([num_vertices], type=pa.uint64())],
            schema=pa.schema([pa.field("offset", pa.uint64()), pa.field("count", pa.uint64())]),
        )
        mesh_parts_go = EmbeddedTriangulatedMesh_V2_1_0_Parts(
            chunks=IndexArray2_V1_0_1(**data_client.save_table(parts_table)),
            attributes=surface_attributes_go,
        )
    else:
        mesh_parts_go = None

    mesh_vertices_go = Triangles_V1_2_0_Vertices(**data_client.save_table(vertices_table))
    mesh_triangle_indices_go = Triangles_V1_2_0_Indices(**data_client.save_table(indices_table))

    triangle_mesh_go = TriangleMesh_V2_1_0(
        name=name,
        uuid=None,
        bounding_box=bounding_box_go,
        coordinate_reference_system=coordinate_reference_system,
        triangles=Triangles_V1_2_0(vertices=mesh_vertices_go, indices=mesh_triangle_indices_go),
        parts=mesh_parts_go,
    )

    logger.debug(f"Created: {triangle_mesh_go}")

    return triangle_mesh_go
