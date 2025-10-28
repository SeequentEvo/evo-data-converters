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

from unittest.mock import MagicMock

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import pytest
import vtk
from vtk.util.numpy_support import numpy_to_vtk

from evo.data_converters.vtk.importer.vtk_attributes_to_grid import convert_attributes_for_grid


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

    data_client = MagicMock()

    result = convert_attributes_for_grid(vtk_data)
    assert len(result) == 1
    assert result[0]["name"] == "float_attr"

    table = result[0]["values"]

    assert table[0].type == pa.float64()

    data_client.assert_not_called()


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

    data_client = MagicMock()

    result = convert_attributes_for_grid(vtk_data)
    assert len(result) == 1
    assert result[0]["name"] == "int_attr"
    table = result[0]["values"]

    assert table[0].type == go_dtype

    data_client.assert_not_called()


def test_convert_attributes_with_string_data() -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    array = _create_string_array(["A", "B", "C", "A", "A"])
    array.SetName("string_attr")
    vtk_data.AddArray(array)

    data_client = MagicMock()

    result = convert_attributes_for_grid(vtk_data)
    assert len(result) == 1
    assert isinstance(result[0], dict)
    assert result[0]["name"] == "string_attr"

    lookup_table = result[0]["table"]
    assert lookup_table == pa.table({"key": pa.array([0, 1, 2], type=pa.int32()), "value": ["A", "B", "C"]})
    values_table = result[0]["values"]
    assert values_table[0].combine_chunks() == pa.array([0, 1, 2, 0, 0], type=pa.int32())

    data_client.assert_not_called()


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

    result = convert_attributes_for_grid(vtk_data)
    assert len(result) == 0


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

    data_client = MagicMock()

    result = convert_attributes_for_grid(vtk_data, np.array([True, False, True]), grid_is_filtered=grid_is_filtered)
    assert len(result) == 1
    assert result[0]["name"] == "int_attr"
    table = result[0]["values"]

    array = table[0].combine_chunks()
    assert array == pa.array(expected_values, type=pa.int32())

    data_client.assert_not_called()


@pytest.mark.parametrize(
    "grid_is_filtered, expected_values",
    [
        pytest.param(False, [0, None, 1, None, 0], id="not_filtered"),
        pytest.param(True, [0, 1, 0], id="filtered"),
    ],
)
def test_convert_string_attributes_with_mask(grid_is_filtered: bool, expected_values: list[int | None]) -> None:
    vtk_data = vtk.vtkDataSetAttributes()
    array = _create_string_array(["A", "B", "C", "A", "A"])
    array.SetName("string_attr")
    vtk_data.AddArray(array)

    data_client = MagicMock()
    result = convert_attributes_for_grid(
        vtk_data, np.array([True, False, True, False, True]), grid_is_filtered=grid_is_filtered
    )
    assert len(result) == 1
    assert isinstance(result[0], dict)
    assert result[0]["name"] == "string_attr"

    lookup_table = result[0]["table"]
    assert lookup_table == pa.table({"key": pa.array([0, 1], type=pa.int32()), "value": ["A", "C"]})
    values_table = result[0]["values"]
    assert values_table[0].combine_chunks() == pa.array(expected_values, type=pa.int32())

    data_client.assert_not_called()
