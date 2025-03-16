import omf_python
import pyarrow as pa
from geoscience_object_models.components import (
    Crs_V1_0_1_EpsgCode,
    Segments_V1_2_0,
    Segments_V1_2_0_Indices,
    Segments_V1_2_0_Vertices,
)
from geoscience_object_models.objects import LineSegments_V2_1_0

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from ...common.utils import vertices_bounding_box
from .omf_attributes_to_evo import convert_omf_attributes

logger = evo.logging.getLogger("data_converters")


def convert_omf_lineset(
    lineset: omf_python.Element,
    project: omf_python.Project,
    reader: omf_python.Reader,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> LineSegments_V2_1_0:
    logger.debug(f'Converting omf_python Element: "{lineset.name}" to LineSegments_V2_0_0.')

    coordinate_reference_system = Crs_V1_0_1_EpsgCode(epsg_code=epsg_code)

    geometry: omf_python.LineSet = lineset.geometry()

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

    vertex_attributes_go = convert_omf_attributes(lineset, reader, data_client, omf_python.Location.Vertices)
    line_attributes_go = convert_omf_attributes(lineset, reader, data_client, omf_python.Location.Primitives)

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
