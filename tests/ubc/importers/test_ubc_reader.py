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

import typing
from unittest.mock import MagicMock, mock_open, patch

import numpy as np
import pytest

from evo.data_converters.ubc.importer.ubc_reader import (
    UBCFile,
    UbcFileIOError,
    UbcInvalidDataError,
    UBCMeshFileImporter,
    UbcOOMError,
    UBCPropertyFileImporter,
)

# Test data
mesh_file_content = """3 3 3
0.0 0.0 0.0
1.0 1.0 1.0
1.0 1.0 1.0
1.0 1.0 1.0
"""
property_file_content = "1.0\n2.0\n3.0\n4.0\n5.0\n6.0\n7.0\n8.0\n9.0\n"


@pytest.fixture
def mock_mesh_file() -> typing.Any:
    with patch("builtins.open", mock_open(read_data=mesh_file_content)):
        yield


@pytest.fixture
def mock_property_file() -> typing.Any:
    with patch("builtins.open", mock_open(read_data=property_file_content)):
        yield


def test_ubc_mesh_file_importer_run(mock_mesh_file: MagicMock) -> None:
    importer = UBCMeshFileImporter("dummy_mesh_file.txt")
    origin, spacings, size_of_dimensions = importer.run()
    assert np.array_equal(origin, np.array([0.0, 0.0, -3.0]))
    assert len(spacings) == 3
    assert size_of_dimensions == [3, 3, 3]


def test_floats_iter() -> None:
    importer = UBCMeshFileImporter("dummy_mesh_file.txt")
    input_data = ["3*1.5", "2*2.0", "1.0"]
    expected_output = [1.5, 1.5, 1.5, 2.0, 2.0, 1.0]
    result = list(importer.floats_iter(input_data))
    assert result == expected_output


@patch("numpy.fromfile")
def test_ubc_property_file_importer_run(mock_fromfile: MagicMock, mock_property_file: MagicMock) -> None:
    mock_fromfile.return_value = np.array(list(range(60)))
    importer = UBCPropertyFileImporter("dummy_property_file.txt")
    size_in_blocks = [3, 4, 5]
    values_array = importer.run(60, size_in_blocks)
    assert len(values_array) == 60
    assert np.array_equal(
        values_array,
        np.array(
            list(range(4, 60, 5))
            + list(range(3, 60, 5))
            + list(range(2, 60, 5))
            + list(range(1, 60, 5))
            + list(range(0, 60, 5))
        ),
    )


def test_ubc_file_opened_file() -> None:
    ubc_file = UBCFile("dummy_file.txt")
    with patch("builtins.open", mock_open(read_data="data")) as mock_file:
        with ubc_file.opened_file() as f:
            assert f.read() == "data"
    mock_file.assert_called_once_with("dummy_file.txt", "r")


def test_execute_memory_error() -> None:
    class TestUBCFile(UBCFile):
        def run(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            raise MemoryError

    ubc_file = TestUBCFile("dummy_file.txt")
    with pytest.raises(UbcOOMError) as exc_info:
        ubc_file.execute()
    assert "Ran out of memory while importing grid file 'dummy_file.txt'" in str(exc_info.value)


def test_execute_value_error_array_too_big() -> None:
    class TestUBCFile(UBCFile):
        def run(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            raise ValueError("array is too big.")

    ubc_file = TestUBCFile("dummy_file.txt")
    with pytest.raises(UbcOOMError) as exc_info:
        ubc_file.execute()
    assert "Ran out of memory while importing grid file 'dummy_file.txt'" in str(exc_info.value)


def test_execute_value_error_other() -> None:
    class TestUBCFile(UBCFile):
        def run(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            raise ValueError("some other error")

    ubc_file = TestUBCFile("dummy_file.txt")
    ubc_file.line_number_of_import_file = 5
    with pytest.raises(UbcInvalidDataError) as exc_info:
        ubc_file.execute()
    assert "Error importing the UBC model from the file 'dummy_file.txt':5" in str(exc_info.value)


def test_execute_index_error() -> None:
    class TestUBCFile(UBCFile):
        def run(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            raise IndexError

    ubc_file = TestUBCFile("dummy_file.txt")
    with pytest.raises(UbcInvalidDataError) as exc_info:
        ubc_file.execute()
    assert (
        "Error importing the UBC model from the file 'dummy_file.txt'The specified number of cells differs to the number of cell widths given in one or more directions"
        in str(exc_info.value)
    )


def test_execute_generic_exception() -> None:
    class TestUBCFile(UBCFile):
        def run(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            raise Exception("generic error")

    ubc_file = TestUBCFile("dummy_file.txt")
    with pytest.raises(UbcFileIOError) as exc_info:
        ubc_file.execute()
    assert "Error importing the UBC model from 'dummy_file.txt'.\ngeneric error" in str(exc_info.value)


def test_opened_file_stop_iteration() -> None:
    ubc_file = UBCFile("dummy_file.txt")
    ubc_file.line_number_of_import_file = 10
    with patch("builtins.open", mock_open(read_data="data")) as mock_file:
        mock_file.side_effect = StopIteration
        with pytest.raises(UbcFileIOError) as exc_info:
            with ubc_file.opened_file():
                pass
        assert "lacking the expected data after line: 10" in str(exc_info.value)


def test_opened_file_os_error() -> None:
    ubc_file = UBCFile("dummy_file.txt")
    with patch("builtins.open", mock_open(read_data="data")) as mock_file:
        mock_file.side_effect = OSError("Test IO error")
        with pytest.raises(UbcFileIOError) as exc_info:
            with ubc_file.opened_file():
                pass
        assert "An unexpected IO error (Test IO error) occurred while reading the dummy_file.txt" in str(exc_info.value)


def test_ubc_file_execute() -> None:
    class TestUBCFile(UBCFile):
        def run(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            return "success"

    ubc_file = TestUBCFile("dummy_file.txt")
    result = ubc_file.execute()
    assert result == "success"


def test_ubc_file_execute_raises_ubc_file_io_error() -> None:
    class TestUBCFile(UBCFile):
        def run(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            raise OSError("Test error")

    ubc_file = TestUBCFile("dummy_file.txt")
    with pytest.raises(UbcFileIOError):
        ubc_file.execute()
