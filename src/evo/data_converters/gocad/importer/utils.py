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

import os
from typing import Optional

import numpy
import pyarrow as pa
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0,
    Crs_V1_0_1_EpsgCode,
    NanContinuous_V1_0_1,
)
from evo_schemas.elements import FloatArray1_V1_0_1
from evo_schemas.objects import Regular3DGrid_V1_2_0
from scipy.spatial.transform import Rotation

from evo.data_converters.common.utils import check_rotation_matrix, convert_rotation, grid_bounding_box
from evo.data_converters.gocad.importer.gocad_reader import import_gocad_voxel
from evo.objects.utils.data import ObjectDataClient


def _create_continuous_attributes(
    data_client: ObjectDataClient, label_to_values_and_filter: dict
) -> list[ContinuousAttribute_V1_1_0]:
    cell_attributes = []
    for name, values_and_filter in label_to_values_and_filter.items():
        values, filter = values_and_filter
        table = pa.table({"values": values})
        nans = numpy.unique(values[filter])
        cell_attributes.append(
            ContinuousAttribute_V1_1_0(
                name=name,
                key=name,
                nan_description=NanContinuous_V1_0_1(values=nans.tolist()),
                values=FloatArray1_V1_0_1(**data_client.save_table(table)),
            )
        )
    return cell_attributes


def get_geoscience_object_from_gocad(
    data_client: ObjectDataClient, filepath: str, epsg_code: int, tags: Optional[dict[str, str]] = None
) -> Regular3DGrid_V1_2_0:
    vo_result, label_to_values_and_filter, final_grid = import_gocad_voxel(filepath)
    tx_rotation, tx_offset = vo_result.transform
    base_point, spacing, grid_size = final_grid
    rotation = tx_rotation if tx_rotation is not None else numpy.identity(3)

    check_rotation_matrix(rotation)
    origin = base_point - spacing * 0.5
    rotated_origin = origin @ rotation

    if tx_offset is not None:
        rotated_origin += tx_offset

    bbox = grid_bounding_box(rotated_origin, rotation, numpy.array(spacing) * numpy.array(grid_size))
    cell_attributes = _create_continuous_attributes(data_client, label_to_values_and_filter)

    object_tags = {}
    object_tags["Source"] = f"{os.path.basename(filepath)} (via Evo Data Converters)"
    object_tags["Stage"] = "Experimental"
    object_tags["InputType"] = "GOCAD"

    # Add custom tags
    if tags:
        object_tags.update(tags)

    return Regular3DGrid_V1_2_0(
        name=vo_result.header["name"],
        origin=rotated_origin.tolist(),
        size=grid_size.tolist(),
        cell_size=spacing.tolist(),
        coordinate_reference_system=Crs_V1_0_1_EpsgCode(epsg_code=epsg_code),
        bounding_box=bbox,
        rotation=convert_rotation(Rotation.from_matrix(rotation.T)),
        cell_attributes=cell_attributes,
        uuid=None,
        tags=object_tags,
    )
