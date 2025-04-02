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

import pyarrow as pa
import vtk
from evo_schemas.components import BoolAttribute_V1_1_0
from evo_schemas.elements import BoolArray1_V1_0_1
from evo_schemas.objects import Regular3DGrid_V1_2_0, RegularMasked3DGrid_V1_2_0

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from ._utils import check_for_ghosts, common_fields, get_rotation
from .vtk_attributes_to_evo import convert_attributes

logger = evo.logging.getLogger("data_converters")


def convert_vtk_image_data(
    name: str,
    image_data: vtk.vtkImageData,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> Regular3DGrid_V1_2_0 | RegularMasked3DGrid_V1_2_0:
    """Convert a vtkImageData object to a Regular3DGrid or RegularMasked3DGrid object, depending on whether the
    vtkImageData object has any blanked cells.
    """

    # GetDimensions returns the number of points in each dimension, so we need to subtract 1 to get the number of cells
    dimensions = image_data.GetDimensions()
    dimensions = [dim - 1 for dim in dimensions]
    spacing = image_data.GetSpacing()

    # VTK supports the origin being offset from the corner of the grid, but Geoscience Objects don't.
    # So, get the location of the corner of grid extent, and use that as the origin.
    i1, _, j1, _, k1, _ = image_data.GetExtent()
    origin = [0.0, 0.0, 0.0]
    image_data.TransformIndexToPhysicalPoint(i1, j1, k1, origin)

    cell_data = image_data.GetCellData()
    vertex_data = image_data.GetPointData()

    mask = check_for_ghosts(image_data)
    if mask is not None and not mask.all():
        if vertex_data.GetNumberOfArrays() > 0:
            logger.warning("Blank cells are not supported with point data, skipping the point data")

        cell_attributes = convert_attributes(cell_data, data_client, mask=mask, grid_is_filtered=True)
        mask_attributes = BoolAttribute_V1_1_0(
            name="mask",
            key="mask",
            values=BoolArray1_V1_0_1(**data_client.save_table(pa.table({"mask": mask}))),
        )
        return RegularMasked3DGrid_V1_2_0(
            **common_fields(name, epsg_code, image_data),
            origin=origin,
            size=list(dimensions),
            cell_size=list(spacing),
            rotation=get_rotation(image_data.GetDirectionMatrix()),
            cell_attributes=cell_attributes,
            mask=mask_attributes,
            number_of_active_cells=int(mask.sum()),
        )
    else:
        cell_attributes = convert_attributes(cell_data, data_client)
        vertex_attributes = convert_attributes(vertex_data, data_client)
        return Regular3DGrid_V1_2_0(
            **common_fields(name, epsg_code, image_data),
            origin=origin,
            size=list(dimensions),
            cell_size=list(spacing),
            rotation=get_rotation(image_data.GetDirectionMatrix()),
            cell_attributes=cell_attributes,
            vertex_attributes=vertex_attributes,
        )
