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

from typing import cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import vtk
from scipy.spatial.transform import Rotation as ScipyRotation
from vtk.util.numpy_support import vtk_to_numpy

from evo.data_converters.common.utils import convert_rotation
from evo.objects.typed import Rotation, EpsgCode

from .exceptions import GhostValueError


def get_rotation(vtk_matrix: vtk.vtkMatrix3x3) -> Rotation:
    matrix = [[vtk_matrix.GetElement(i, j) for j in range(3)] for i in range(3)]
    rot = ScipyRotation.from_matrix(matrix)
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


def common_fields(name: str, epsg_code: int) -> dict:
    return {
        "name": name,
        "coordinate_reference_system": EpsgCode(epsg_code),
    }


def is_float_array(array: vtk.vtkAbstractArray) -> bool:
    return array.GetDataType() in [vtk.VTK_DOUBLE, vtk.VTK_FLOAT]


def is_integer_array(array: vtk.vtkAbstractArray) -> bool:
    return array.GetDataType() in [
        vtk.VTK_SIGNED_CHAR,
        vtk.VTK_UNSIGNED_CHAR,
        vtk.VTK_SHORT,
        vtk.VTK_UNSIGNED_SHORT,
        vtk.VTK_INT,
        vtk.VTK_UNSIGNED_INT,
        vtk.VTK_LONG,
        vtk.VTK_UNSIGNED_LONG,
        vtk.VTK_LONG_LONG,
    ]


def is_string_array(array: vtk.vtkAbstractArray) -> bool:
    # mypy doesn't know that GetDataType() and vtk.VTK_STRING are ints
    return cast(bool, array.GetDataType() == vtk.VTK_STRING)


def convert_array(
    values: npt.NDArray | vtk.vtkAbstractArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
    dtype: npt.DTypeLike,
) -> pa.Array:
    if isinstance(values, vtk.vtkAbstractArray):
        values = vtk_to_numpy(values)
    if grid_is_filtered and mask is not None:
        values = values[mask]
        mask = None  # Don't need to filter the values again

    values = values.astype(dtype)
    return pa.array(values, mask=~mask if mask is not None else None)
