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
import vtk
from evo_schemas.components import Rotation_V1_1_0
from evo_schemas.objects import Tensor3DGrid_V1_2_0, Tensor3DGrid_V1_2_0_GridCells3D
from vtk.util.numpy_support import vtk_to_numpy

import evo.logging
from evo.objects.utils.data import ObjectDataClient

from ._utils import check_for_ghosts, common_fields
from .vtk_attributes_to_evo import convert_attributes

logger = evo.logging.getLogger("data_converters")


def convert_vtk_rectilinear_grid(
    name: str,
    rectilinear_grid: vtk.vtkRectilinearGrid,
    data_client: ObjectDataClient,
    epsg_code: int,
) -> Tensor3DGrid_V1_2_0:
    # GetDimensions returns the number of points in each dimension, so we need to subtract 1 to get the number of cells
    dimensions = rectilinear_grid.GetDimensions()
    dimensions = [dim - 1 for dim in dimensions]

    x_coords = vtk_to_numpy(rectilinear_grid.GetXCoordinates())
    y_coords = vtk_to_numpy(rectilinear_grid.GetYCoordinates())
    z_coords = vtk_to_numpy(rectilinear_grid.GetZCoordinates())

    origin = [x_coords[0], y_coords[0], z_coords[0]]
    x_spacings = np.diff(x_coords)
    y_spacings = np.diff(y_coords)
    z_spacings = np.diff(z_coords)

    cell_data = rectilinear_grid.GetCellData()
    vertex_data = rectilinear_grid.GetPointData()

    mask = check_for_ghosts(rectilinear_grid)
    cell_attributes = convert_attributes(cell_data, data_client, mask)
    if mask is not None and not mask.all():
        if vertex_data.GetNumberOfArrays() > 0:
            logger.warning("Blank cells are not supported with point data, skipping the point data")
        vertex_attributes = []
    else:
        vertex_attributes = convert_attributes(vertex_data, data_client)

    return Tensor3DGrid_V1_2_0(
        **common_fields(name, epsg_code, rectilinear_grid),
        origin=origin,
        size=list(dimensions),
        grid_cells_3d=Tensor3DGrid_V1_2_0_GridCells3D(
            cell_sizes_x=list(x_spacings),
            cell_sizes_y=list(y_spacings),
            cell_sizes_z=list(z_spacings),
        ),
        rotation=Rotation_V1_1_0(dip_azimuth=0.0, dip=0.0, pitch=0.0),  # Rectilinear grids don't have rotation
        cell_attributes=cell_attributes,
        vertex_attributes=vertex_attributes,
    )
