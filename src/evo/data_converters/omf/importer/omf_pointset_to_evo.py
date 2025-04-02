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
from evo_schemas.components import Crs_V1_0_1_EpsgCode
from evo_schemas.elements import FloatArray3_V1_0_1
from evo_schemas.objects import Pointset_V1_2_0, Pointset_V1_2_0_Locations

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from ...common.utils import vertices_bounding_box
from .omf_attributes_to_evo import convert_omf_attributes

logger = evo.logging.getLogger("data_converters")


def convert_omf_pointset(
    pointset: omf2.Element,
    project: omf2.Project,
    reader: omf2.Reader,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> Pointset_V1_2_0:
    logger.debug(f'Converting omf2 Element: "{pointset.name}" to Pointset_V1_1_0.')

    coordinate_reference_system = Crs_V1_0_1_EpsgCode(epsg_code=epsg_code)

    geometry = pointset.geometry()

    # Convert vertices to absolute position in world space by adding the project and geometry origin
    vertices_array = reader.array_vertices(geometry.vertices) + project.origin + geometry.origin

    bounding_box_go = vertices_bounding_box(vertices_array)

    vertices_schema = pa.schema(
        [
            pa.field("x", pa.float64()),
            pa.field("y", pa.float64()),
            pa.field("z", pa.float64()),
        ]
    )

    coordinates_table = pa.Table.from_arrays(
        [pa.array(vertices_array[:, i], type=pa.float64()) for i in range(len(vertices_schema))],
        schema=vertices_schema,
    )
    coordinates_args = data_client.save_table(coordinates_table)
    coordinates_go = FloatArray3_V1_0_1.from_dict(coordinates_args)

    attributes_go = convert_omf_attributes(pointset, reader, data_client, omf2.Location.Vertices)

    locations = Pointset_V1_2_0_Locations(
        coordinates=coordinates_go,
        attributes=attributes_go,
    )

    pointset_go = Pointset_V1_2_0(
        name=pointset.name,
        uuid=None,
        bounding_box=bounding_box_go,
        coordinate_reference_system=coordinate_reference_system,
        locations=locations,
    )

    logger.debug(f"Created: {pointset_go}")

    return pointset_go
