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
import pyarrow as pa
from pandas import pd
import vtk
from vtk.util.numpy_support import vtk_to_numpy

import evo.logging

from ._utils import is_float_array, is_integer_array, is_string_array, convert_array

logger = evo.logging.getLogger("data_converters")



def convert_attributes(
    vtk_data: vtk.vtkDataSetAttributes,
    mask: npt.NDArray[np.bool_] | None = None,
    grid_is_filtered: bool = False,
) -> pd.DataFrame:
    """
    Convert VTK attributes to Geoscience Objects attributes.

    :param vtk_data: VTK attributes
    :param mask: Mask to filter the attribute values
    :param grid_is_filtered: True if the attribute values should be filtered by the mask, otherwise the
        attribute values should be set to null where the mask is False.
    """
    attributes = {}

    for i in range(vtk_data.GetNumberOfArrays()):
        name = vtk_data.GetArrayName(i)
        if name == "vtkGhostType":
            continue  # Skip ghost type attribute, we check for ghost cells elsewhere
        array = vtk_data.GetAbstractArray(i)
        if array.GetNumberOfComponents() > 1:
            logger.warning(f"Attribute {name} has more than one component, skipping this attribute")
            continue

        if is_float_array(array):
            attributes[name] = convert_array(array, mask, grid_is_filtered, np.float64)
        elif is_integer_array(array):
            values = vtk_to_numpy(array)
            # Convert to int32 or int64
            dtype = np.int64 if values.dtype in [np.uint32, np.int64] else np.int32
            attributes[name] = convert_array(array, mask, grid_is_filtered, dtype)
        elif is_string_array(array):
            values = [array.GetValue(i) for i in range(array.GetNumberOfValues())]
            attributes[name] = pa.array(values, mask=~mask if mask is not None else None)
        else:
            logger.warning(
                f"Unsupported data type {array.GetDataTypeAsString()} for attribute {name}, skipping this attribute"
            )
            continue
    return pd.DataFrame(attributes)
