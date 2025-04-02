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

import contextlib
import math
import os
from collections.abc import Iterator
from io import TextIOWrapper
from typing import Any

import numpy


class UbcInvalidDataError(Exception):
    pass


class UbcOOMError(Exception):
    pass


class UbcFileIOError(Exception):
    pass


class UBCFile:
    FILE_TYPE = ""  # this is to be overridden in subclass

    def __init__(self, filename: str):
        self.filename = filename
        self.base_filename = os.path.basename(filename)
        self.line_number_of_import_file: int | None = None

    @contextlib.contextmanager
    def opened_file(self) -> Iterator[TextIOWrapper]:
        try:
            with open(self.filename, "r") as open_file:
                yield open_file
        except StopIteration:
            line_number_msg = (
                f" after line: {self.line_number_of_import_file:d}" if self.line_number_of_import_file else ""
            )
            msg = f"The file '{self.base_filename}' is lacking the expected data{line_number_msg}"
            raise UbcFileIOError(msg)
        except OSError as io_error_exception:
            raise UbcFileIOError(
                f"An unexpected IO error ({io_error_exception}) occurred while reading the {self.base_filename}"
            )

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self.run(*args, **kwargs)
        except OSError as exc:
            raise UbcFileIOError(f"Error reading file: {exc.args[0]}")
        except MemoryError:
            raise UbcOOMError(f"Ran out of memory while importing grid file '{self.base_filename}'")
        except ValueError as value_error_exception:
            if str(value_error_exception) == "array is too big.":
                raise UbcOOMError(f"Ran out of memory while importing grid file '{self.base_filename}'")
            else:
                line_number = f":{self.line_number_of_import_file:d}" if self.line_number_of_import_file else ""
                raise UbcInvalidDataError(
                    f"Error importing the UBC model from the file '{self.base_filename}'{line_number}"
                )
        except IndexError:
            raise UbcInvalidDataError(
                f"Error importing the UBC model from the file '{self.base_filename}'"
                "The specified number of cells differs to the number of cell widths given in "
                "one or more directions"
            )
        except Exception as exc:
            raise UbcFileIOError(f"Error importing the UBC model from '{self.base_filename}'.\n{exc.args[0]}")

    def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class UBCMeshFileImporter(UBCFile):
    FILE_TYPE = "mesh"

    @staticmethod
    def row_iter(open_file: TextIOWrapper) -> Iterator[tuple[int, list[str]]]:
        for line_number, line in enumerate(open_file, start=1):
            yield line_number, line.split()

    @staticmethod
    def floats_iter(source: list[str]) -> Iterator[float]:
        for txt in source:
            pos = txt.find("*")
            if pos != -1:
                num = int(txt[:pos])
                val = float(txt[pos + 1 :])
                for _ in range(num):
                    yield val
            else:
                yield float(txt)

    def run(self, *args: Any, **kwargs: Any) -> tuple[numpy.ndarray, list[numpy.ndarray], list[int]]:
        self.line_number_of_import_file = 0
        with self.opened_file() as data_file:
            line_iterator = self.row_iter(data_file)
            self.line_number_of_import_file, line = next(line_iterator)
            size_of_dimensions = [int(size) for size in line[:3]]  # x, y, z dimensions of grid
            if 0 in size_of_dimensions:
                # This is how we do error handling...
                raise UbcInvalidDataError(f"Invalid size (0) detected in {self.filename}")
            self.line_number_of_import_file, line = next(line_iterator)
            origin = numpy.array([float(ordinate) for ordinate in line[:3]])
            if len(origin) < 3:
                raise UbcInvalidDataError(f"Invalid origin detected in {self.filename}")
            spacings = []
            for size in size_of_dimensions:
                i = 0
                d = numpy.zeros((size,), numpy.float64)
                while i < size:
                    self.line_number_of_import_file, input_line = next(line_iterator)
                    for f in self.floats_iter(input_line):
                        d[i] = f
                        i += 1
                spacings.append(d)
        origin[2] -= sum(spacings[2])
        spacings[2] = spacings[2][::-1]
        return origin, spacings, size_of_dimensions


class UBCPropertyFileImporter(UBCFile):
    FILE_TYPE = "property"

    def run(self, n_blocks: int, size_in_blocks: list) -> numpy.ndarray:
        with self.opened_file() as data_file:
            values_array = numpy.fromfile(data_file, sep="\n", count=n_blocks)

        if len(values_array) != n_blocks or any(math.isinf(value) or math.isnan(value) for value in values_array):
            raise UbcInvalidDataError(
                "Error importing the UBC properties from file: "
                f"'{self.base_filename}'. "
                f"The number of property values ({len(values_array)})"
                f"differs from the number of grid cells ({n_blocks})."
            )
        new_shape = tuple(size_in_blocks[:2][::-1] + [size_in_blocks[2]])
        values_array.shape = new_shape
        return values_array[:, :, ::-1].swapaxes(0, 1).swapaxes(0, 2).ravel()
