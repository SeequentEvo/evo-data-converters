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
from evo_schemas.components import (
    CategoryAttribute_V1_1_0,
    ContinuousAttribute_V1_1_0,
    IntegerAttribute_V1_1_0,
    NanCategorical_V1_0_1,
    NanContinuous_V1_0_1,
    OneOfAttribute_V1_2_0,
)
from evo_schemas.elements import FloatArray1_V1_0_1, IntegerArray1_V1_0_1, LookupTable_V1_0_1
from vtk.util.numpy_support import vtk_to_numpy

import evo.logging
from evo.objects.utils.data import ObjectDataClient

logger = evo.logging.getLogger("data_converters")


def _is_float_array(array: vtk.vtkAbstractArray) -> bool:
    return array.GetDataType() in [vtk.VTK_DOUBLE, vtk.VTK_FLOAT]


def _is_integer_array(array: vtk.vtkAbstractArray) -> bool:
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


def _is_string_array(array: vtk.vtkAbstractArray) -> bool:
    # mypy doesn't know that GetDataType() and vtk.VTK_STRING are ints
    return cast(bool, array.GetDataType() == vtk.VTK_STRING)


def _create_table(
    values: npt.NDArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
    dtype: npt.DTypeLike,
) -> pa.Table:
    if grid_is_filtered and mask is not None:
        values = values[mask]
        mask = None  # Don't need to filter the values again

    values = values.astype(dtype)
    array = pa.array(values, mask=~mask if mask is not None else None)
    return pa.table({"values": array})


def _create_continuous_attribute(
    data_client: ObjectDataClient,
    name: str,
    array: vtk.vtkAbstractArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
) -> ContinuousAttribute_V1_1_0:
    values = vtk_to_numpy(array)
    # Convert to float64, as Geoscience Objects only support float64 for continuous attributes
    table = _create_table(values, mask, grid_is_filtered, np.float64)
    return ContinuousAttribute_V1_1_0(
        name=name,
        key=name,
        nan_description=NanContinuous_V1_0_1(values=[]),
        values=FloatArray1_V1_0_1(**data_client.save_table(table)),
    )


def _create_integer_attribute(
    data_client: ObjectDataClient,
    name: str,
    array: vtk.vtkAbstractArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
) -> IntegerAttribute_V1_1_0:
    values = vtk_to_numpy(array)
    # Convert to int32 or int64
    dtype = np.int64 if values.dtype in [np.uint32, np.int64] else np.int32
    table = _create_table(values, mask, grid_is_filtered, dtype)
    return IntegerAttribute_V1_1_0(
        name=name,
        key=name,
        nan_description=NanCategorical_V1_0_1(values=[]),
        values=IntegerArray1_V1_0_1(**data_client.save_table(table)),
    )


_numpy_dtype_for_pyarrow_type = {
    pa.int32(): np.int32,
    pa.int64(): np.int64,
}


def _create_categorical_attribute(
    data_client: ObjectDataClient,
    name: str,
    array: vtk.vtkStringArray,
    mask: npt.NDArray[np.bool_] | None,
    grid_is_filtered: bool,
) -> CategoryAttribute_V1_1_0:
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
    return CategoryAttribute_V1_1_0(
        name=name,
        key=name,
        nan_description=NanCategorical_V1_0_1(values=[]),
        table=LookupTable_V1_0_1(**data_client.save_table(lookup_table)),
        values=IntegerArray1_V1_0_1(**data_client.save_table(values_table)),
    )


def convert_attributes(
    vtk_data: vtk.vtkDataSetAttributes,
    data_client: ObjectDataClient,
    mask: npt.NDArray[np.bool_] | None = None,
    grid_is_filtered: bool = False,
) -> OneOfAttribute_V1_2_0:
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

        if _is_float_array(array):
            attribute = _create_continuous_attribute(data_client, name, array, mask, grid_is_filtered)
        elif _is_integer_array(array):
            attribute = _create_integer_attribute(data_client, name, array, mask, grid_is_filtered)
        elif _is_string_array(array):
            attribute = _create_categorical_attribute(data_client, name, array, mask, grid_is_filtered)
        else:
            logger.warning(
                f"Unsupported data type {array.GetDataTypeAsString()} for attribute {name}, skipping this attribute"
            )
            continue
        attributes.append(attribute)
    return attributes
