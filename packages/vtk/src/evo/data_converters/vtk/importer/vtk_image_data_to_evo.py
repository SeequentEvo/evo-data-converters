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

import vtk
from evo.objects.typed import Regular3DGridData, RegularMasked3DGridData, Point3, Size3d, Size3i

import evo.logging

from ._utils import check_for_ghosts, common_fields, get_rotation
from .vtk_attributes_to_evo import convert_attributes

logger = evo.logging.getLogger("data_converters")


def convert_vtk_image_data(
    name: str,
    image_data: vtk.vtkImageData,
    epsg_code: int,
) -> Regular3DGridData | RegularMasked3DGridData:
    """Convert a vtkImageData object to a Regular3DGrid or RegularMasked3DGrid object, depending on whether the
    vtkImageData object has any blanked cells.
    """
    size = image_data.GetDimensions()
    size = [dim - 1 for dim in size]
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

        cell_attributes = convert_attributes(cell_data, mask=mask, grid_is_filtered=True)
       
        return RegularMasked3DGridData(
            **common_fields(name, epsg_code),
            origin=Point3(*origin),
            size=Size3i(*size),
            cell_size=Size3d(*spacing),
            rotation=get_rotation(image_data.GetDirectionMatrix()),
            cell_data=cell_attributes,
            mask=mask,
        )
    else:
        cell_attributes = convert_attributes(cell_data)
        vertex_attributes = convert_attributes(vertex_data)
        return Regular3DGridData(
            **common_fields(name, epsg_code),
            origin=Point3(*origin),
            size=Size3i(*size),
            cell_size=Size3d(*spacing),
            rotation=get_rotation(image_data.GetDirectionMatrix()),
            cell_data=cell_attributes,
            vertex_data=vertex_attributes,
        )
