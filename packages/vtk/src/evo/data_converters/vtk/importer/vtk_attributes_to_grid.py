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

from typing import Any, Dict, List

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import vtk
from vtk.util.numpy_support import vtk_to_numpy

import evo.logging

from ._utils import is_float_array, is_integer_array, is_string_array, create_table

logger = evo.logging.getLogger("data_converters")


def _create_continuous_attribute(
    name: str,
    array: vtk.vtkAbstractArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
) -> Dict[str, Any]:
    values = vtk_to_numpy(array)
    # Convert to float64, as Geoscience Objects only support float64 for continuous attributes
    table = create_table(values, mask, grid_is_filtered, np.float64)
    return dict(
        name=name,
        values=table,
    )


def _create_integer_attribute(
    name: str,
    array: vtk.vtkAbstractArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
) -> Dict[str, Any]:
    values = vtk_to_numpy(array)
    # Convert to int32 or int64
    dtype = np.int64 if values.dtype in [np.uint32, np.int64] else np.int32
    table = create_table(values, mask, grid_is_filtered, dtype)
    return dict(
        name=name,
        values=table,
    )


_numpy_dtype_for_pyarrow_type = {
    pa.int32(): np.int32,
    pa.int64(): np.int64,
}


def _create_categorical_attribute(
    name: str,
    array: vtk.vtkStringArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
) -> Dict[str, Any]:
    values = [array.GetValue(i) for i in range(array.GetNumberOfValues())]
    arrow_array = pa.array(values, mask=~mask if mask is not None else None)

    # Encode the array as a dictionary encoded array
    dict_array = arrow_array.dictionary_encode()

    indices = dict_array.indices
    if grid_is_filtered and mask is not None:
        indices = indices.filter(mask)

    # Create a lookup table
    indices_dtype = _numpy_dtype_for_pyarrow_type[indices.type]
    lookup_table = pa.table(
        {"key": np.arange(len(dict_array.dictionary), dtype=indices_dtype), "value": dict_array.dictionary}
    )

    values_table = pa.table({"values": indices})
    return dict(
        name=name,
        table=lookup_table,
        values=values_table,
    )


def convert_attributes_for_grid(
    vtk_data: vtk.vtkDataSetAttributes,
    mask: npt.NDArray[np.bool_] | None = None,
    grid_is_filtered: bool = False,
) -> List[Dict[str, Any]]:
    """
    Convert VTK attributes to Geoscience Objects attributes.

    :param vtk_data: VTK attributes
    :param data_client: Data client used to save the attribute values
    :param mask: Mask to filter the attribute values
    :param grid_is_filtered: True if the attribute values should be filtered by the mask, otherwise the
        attribute values should be set to null where the mask is False.
    """
    attributes = []

    for i in range(vtk_data.GetNumberOfArrays()):
        name = vtk_data.GetArrayName(i)
        if name == "vtkGhostType":
            continue  # Skip ghost type attribute, we check for ghost cells elsewhere
        array = vtk_data.GetAbstractArray(i)
        if array.GetNumberOfComponents() > 1:
            logger.warning(f"Attribute {name} has more than one component, skipping this attribute")
            continue

        if is_float_array(array):
            attribute = _create_continuous_attribute(name, array, mask, grid_is_filtered)
        elif is_integer_array(array):
            attribute = _create_integer_attribute(name, array, mask, grid_is_filtered)
        elif is_string_array(array):
            attribute = _create_categorical_attribute(name, array, mask, grid_is_filtered)
        else:
            logger.warning(
                f"Unsupported data type {array.GetDataTypeAsString()} for attribute {name}, skipping this attribute"
            )
            continue
        attributes.append(attribute)
    return attributes
