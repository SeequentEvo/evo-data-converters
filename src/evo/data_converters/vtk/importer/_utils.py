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
import numpy.typing as npt
import vtk
from evo_schemas.components import BoundingBox_V1_0_1, Crs_V1_0_1_EpsgCode, Rotation_V1_1_0
from scipy.spatial.transform import Rotation
from vtk.util.numpy_support import vtk_to_numpy

from evo.data_converters.common.utils import convert_rotation

from .exceptions import GhostValueError


def get_bounding_box(grid: vtk.vtkDataSet) -> BoundingBox_V1_0_1:
    min_x, max_x, min_y, max_y, min_z, max_z = grid.GetBounds()
    return BoundingBox_V1_0_1(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y, min_z=min_z, max_z=max_z)


def get_rotation(vtk_matrix: vtk.vtkMatrix3x3) -> Rotation_V1_1_0:
    matrix = [[vtk_matrix.GetElement(i, j) for j in range(3)] for i in range(3)]
    rot = Rotation.from_matrix(matrix)
    return convert_rotation(rot)


def check_for_ghosts(dataset: vtk.vtkDataSet) -> npt.NDArray[np.bool_] | None:
    # Ghost cells/points, are used for parallel processing, to indicate that cells/points are not in this chunk,
    # but still exist. If any are present, skip this grid as it's not obvious how to handle them.
    #
    # Blank points, mean the cells around that point are not visible, we aren't handling this case for the
    # time being.
    if dataset.HasAnyBlankPoints():
        raise GhostValueError("Grid with blank points are not supported")
    if dataset.HasAnyGhostPoints():
        raise GhostValueError("Grid with ghost points are not supported")
    if dataset.HasAnyGhostCells():
        raise GhostValueError("Grid with ghost cells are not supported")

    # Blank cell information is stored in the ghost array
    ghost_array = dataset.GetCellGhostArray()
    if ghost_array is not None:
        ghosts = vtk_to_numpy(ghost_array)
        mask: npt.NDArray[np.bool_] = ghosts == 0  # Only include cells that aren't blank
        return mask
    else:
        return None


def common_fields(name: str, epsg_code: int, dataset: vtk.vtkDataSet) -> dict:
    bounding_box = get_bounding_box(dataset)
    return {
        "name": name,
        "coordinate_reference_system": Crs_V1_0_1_EpsgCode(epsg_code=epsg_code),
        "bounding_box": bounding_box,
        "uuid": None,
    }
