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

import uuid
from unittest.mock import MagicMock

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import pandas as pd
import pandas.testing as pdt
import pytest
import vtk
from evo_schemas.components import CategoryAttribute_V1_1_0
from vtk.util.numpy_support import numpy_to_vtk
from vtk_test_helpers import MockDataClient

from evo.data_converters.vtk.importer.vtk_attributes_to_evo import convert_attributes


def _create_string_array(values: list[str]) -> vtk.vtkStringArray:
    array = vtk.vtkStringArray()
    for value in values:
        array.InsertNextValue(value)
    return array


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_convert_attributes_with_float_data(dtype: np.dtype) -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    array = numpy_to_vtk(np.array([1.0, 2.0, 3.0], dtype=dtype))
    array.SetName("float_attr")
    vtk_data.AddArray(array)

    result = convert_attributes(vtk_data)

    pdt.assert_frame_equal(
        result,
        pd.DataFrame({
            "float_attr": np.array([1.0, 2.0, 3.0], dtype=np.float64),
        })
    )


@pytest.mark.parametrize(
    "input_dtype, go_dtype",
    [
        pytest.param(np.int8, pa.int32(), id="int8"),
        pytest.param(np.uint8, pa.int32(), id="uint8"),
        pytest.param(np.int16, pa.int32(), id="int16"),
        pytest.param(np.uint16, pa.int32(), id="uint16"),
        pytest.param(np.int32, pa.int32(), id="int32"),
        pytest.param(np.uint32, pa.int64(), id="uint32"),
        pytest.param(np.int64, pa.int64(), id="int64"),
    ],
)
def test_convert_attributes_with_int_data(input_dtype: np.dtype, go_dtype: pa.DataType) -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    array = numpy_to_vtk(np.array([1, 2, 3], dtype=input_dtype))
    array.SetName("int_attr")
    vtk_data.AddArray(array)

    result = convert_attributes(vtk_data)
    pdt.assert_frame_equal(
        result,
        pd.DataFrame({
            "int_attr": pa.array([1, 2, 3], go_dtype),
        })
    )


def test_convert_attributes_with_string_data() -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    array = _create_string_array(["A", "B", "C", "A", "A"])
    array.SetName("string_attr")
    vtk_data.AddArray(array)

    result = convert_attributes(vtk_data)
    pdt.assert_frame_equal(
        result,
        pd.DataFrame({
            "string_attr": ["A", "B", "C", "A", "A"],
        })
    )

@pytest.mark.parametrize(
    "array",
    [
        pytest.param(np.array([1, 2, 3], dtype=np.uint64), id="uint64"),
        pytest.param(np.array([[1, 2], [2, 4]], dtype=np.int32), id="2d"),
    ],
)
def test_convert_attributes_unsupported_data_types(array: npt.NDArray) -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    if array.dtype == object:
        vtk_array = vtk.vtkStringArray()
        for value in array:
            vtk_array.InsertNextValue(value)
    else:
        vtk_array = numpy_to_vtk(array)
    vtk_data.AddArray(vtk_array)

    result = convert_attributes(vtk_data)
    assert len(result.columns) == 0


@pytest.mark.parametrize(
    "grid_is_filtered, expected_values",
    [
        pytest.param(False, [1, None, 3], id="not_filtered"),
        pytest.param(True, [1, 3], id="filtered"),
    ],
)
def test_convert_attributes_with_mask(grid_is_filtered: bool, expected_values: list[int | None]) -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    array = numpy_to_vtk(np.array([1, 2, 3], dtype=np.int32))
    array.SetName("int_attr")
    vtk_data.AddArray(array)

    result = convert_attributes(vtk_data, np.array([True, False, True]), grid_is_filtered=grid_is_filtered)
    pdt.assert_frame_equal(
        result,
        pd.DataFrame({
            "int_attr": pa.array(expected_values, pa.int32()),
        })
    )


@pytest.mark.parametrize(
    "grid_is_filtered, expected_values",
    [
        pytest.param(False, ["A", None, "C", None, "A"], id="not_filtered"),
        pytest.param(True, ["A", "C", "A"], id="filtered"),
    ],
)
def test_convert_string_attributes_with_mask(grid_is_filtered: bool, expected_values: list[int | None]) -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    array = _create_string_array(["A", "B", "C", "A", "A"])
    array.SetName("string_attr")
    vtk_data.AddArray(array)

    result = convert_attributes(
        vtk_data, np.array([True, False, True, False, True]), grid_is_filtered=grid_is_filtered
    )
    
    pdt.assert_frame_equal(
        result,
        pd.DataFrame({
            "string_attr": expected_values,
        })
    )