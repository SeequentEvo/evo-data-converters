import numpy as np
import pyarrow as pa
from evo_schemas.components import (
    Crs_V1_0_1_EpsgCode,
    Segments_V1_2_0,
    Segments_V1_2_0_Indices,
    Segments_V1_2_0_Vertices,
)
from evo_schemas.elements import IndexArray2_V1_0_1
from evo_schemas.objects import LineSegments_V2_1_0, LineSegments_V2_1_0_Parts

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from ...common.utils import vertices_bounding_box
from ..common.duf_wrapper import Polyline
from ..common.utils import get_name
from .duf_attributes_to_evo import convert_duf_attributes

logger = evo.logging.getLogger("data_converters")


def convert_duf_lineset(
    polyline: Polyline,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> LineSegments_V2_1_0:
    name = get_name(polyline)
    logger.debug(f'Converting Polyline: "{name}" to LineSegments_V2_0_0.')

    coordinate_reference_system = Crs_V1_0_1_EpsgCode(epsg_code=epsg_code)

    num_vertices = polyline.VertexList.Count

    axes = ("X", "Y", "Z")
    vertices_array = np.fromiter(
        (getattr(vert, axis) for vert in polyline.VertexList for axis in axes),
        dtype=np.float64,
        count=num_vertices * 3,
    ).reshape(num_vertices, 3)

    indices_array = np.column_stack(
        (
            np.arange(num_vertices - 1).reshape(-1, num_vertices - 1).T,
            np.arange(1, num_vertices).reshape(-1, num_vertices - 1).T,
        )
    ).astype("uint64")

    logger.debug(f"Indices: {indices_array.shape}")
    logger.debug(f"Vertices: {vertices_array.shape}")

    attributes = (
        [(xprop.Key, xprop.Value.Value[0].Value) for xprop in polyline.XProperties] if polyline.XProperties else []
    )
    logger.debug(f"Num Polyline Attributes: {len(attributes)}")

    bounding_box_go = vertices_bounding_box(vertices_array)

    vertices_schema = pa.schema(
        [
            pa.field("x", pa.float64()),
            pa.field("y", pa.float64()),
            pa.field("z", pa.float64()),
        ]
    )
    indices_schema = pa.schema([pa.field("n0", pa.uint64()), pa.field("n1", pa.uint64())])

    vertices_table = pa.Table.from_arrays(
        [pa.array(vertices_array[:, i], type=pa.float64()) for i in range(len(vertices_schema))],
        schema=vertices_schema,
    )
    indices_table = pa.Table.from_arrays(
        [pa.array(indices_array[:, i], type=pa.uint64()) for i in range(len(indices_schema))],
        schema=indices_schema,
    )
    parts_table = pa.Table.from_arrays(
        [pa.array([0], type=pa.uint64()), pa.array([num_vertices], type=pa.uint64())],
        schema=pa.schema([pa.field("offset", pa.uint64()), pa.field("count", pa.uint64())]),
    )

    line_attributes_go = convert_duf_attributes(attributes, data_client)
    segment_parts_go = LineSegments_V2_1_0_Parts(
        chunks=IndexArray2_V1_0_1(**data_client.save_table(parts_table)),
        attributes=line_attributes_go,
    )
    vertices_go = Segments_V1_2_0_Vertices(**data_client.save_table(vertices_table))
    segment_indices_go = Segments_V1_2_0_Indices(**data_client.save_table(indices_table))

    line_segments_go = LineSegments_V2_1_0(
        name=name,
        uuid=None,
        bounding_box=bounding_box_go,
        coordinate_reference_system=coordinate_reference_system,
        segments=Segments_V1_2_0(vertices=vertices_go, indices=segment_indices_go),
        parts=segment_parts_go,
    )

    logger.debug(f"Created: {line_segments_go}")

    return line_segments_go
