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

# type: ignore
import array
import itertools
import math
import os
import os.path
import re
import struct
import typing
from io import TextIOWrapper
from typing import Iterator, Protocol, Union

import numpy

# See documentation at
# http://paulbourke.net/dataformats/gocad/gocad.pdf

BLOCK_SIZE = 250000


class GocadInvalidDataError(Exception):
    def __init__(self, msg: str):
        Exception.__init__(self, msg)


class GocadDataFileIOError(Exception):
    def __init__(self, path: str, errno: int | None, strerror: str | None):
        Exception.__init__(self)
        self.path = path
        self.errno = errno
        self.strerror = strerror


# This loader handles datastored in big-endian IEEE 32 bit floating point numbers.
# The array increases in x fastest then y then z


class VoDataStream:
    def __init__(self, f: TextIOWrapper, total: int, is_msb: bool, block_size: int = BLOCK_SIZE):
        self.is_msb = is_msb
        if is_msb:
            self.st_fmt = struct.Struct(">f")
        else:
            self.st_fmt = struct.Struct("<f")
        self.f = f
        self.total = total
        self.block_size = block_size
        self.end = (total - 1) % block_size + 1
        self.buffer = f.read(4 * self.end)
        self.start = 0

    def fastread(self, dest: numpy.ndarray) -> None:
        ratemp = array.array("f", self.buffer)
        if self.is_msb:
            ratemp.byteswap()
        start = self.end
        dest[:start] = ratemp
        while start < self.total:
            del ratemp[:]
            ratemp.fromfile(self.f, self.block_size)
            end = start + self.block_size
            if self.is_msb:
                ratemp.byteswap()
            dest[start:end] = ratemp
            start = end

    def get(self, offset: int) -> typing.Any:
        while offset >= self.end:
            self.start = self.end
            self.end += self.block_size
            self.buffer = self.f.read(4 * self.block_size)
        return self.st_fmt.unpack_from(self.buffer, 4 * (offset - self.start))[0]


class VoDataLoader:
    def __init__(self, base_grid: tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray], subsample: int = 1):
        self.base_grid = base_grid
        min_pt, spacing, isize = base_grid
        isubsample = int(subsample)
        sub_size = numpy.ceil(isize.astype(numpy.float64) / isubsample).astype(numpy.int32)
        start_extra = (isize - (sub_size - 1) * isubsample) // 2
        self.full_total = isize[0] * isize[1] * isize[2]
        self.full_size = isize
        self.final_size = sub_size
        self.final_start = start_extra
        self.final_subsample = isubsample
        self.final_offsets = numpy.array([1, isize[0], isize[1] * isize[0]])
        self.final_start_index = numpy.dot(start_extra, self.final_offsets)
        self.final_offsets *= self.final_subsample
        self.final_min = min_pt + start_extra * spacing
        self.final_spacing = spacing * isubsample

    def load_data(self, f: TextIOWrapper, is_msb: bool) -> numpy.ndarray:
        stream = VoDataStream(f, self.full_total, is_msb)
        ra = numpy.empty(self.final_size.prod(), numpy.float64)
        if self.final_subsample != 1:
            rev_offsets = self.final_offsets[::-1]
            for i, zyx in enumerate(itertools.product(*[range(sz) for sz in self.final_size[::-1]])):
                idx = numpy.dot(zyx, rev_offsets) + self.final_start_index
                ra[i] = stream.get(idx)
        else:
            stream.fastread(ra)
        return ra

    def load_all_data(
        self, dir: str, properties: dict[int, dict[str, Union[str, list[str], dict[str, str]]]], is_msb: bool
    ) -> dict[str | list[str], tuple[numpy.ndarray[typing.Any, typing.Any], typing.Any | None]]:
        """Loads the raw data values from accompanying .vo_data files for a given set of .vo properties"""
        result = {}
        for prop in properties.values():
            prop_file_path = " ".join(prop["FILE"])
            if int(prop["ESIZE"][0]) != 4 or prop["ETYPE"][0] != "IEEE":
                continue
            prop_file_path = prop_file_path.replace('"', "")  # can be enclosed by '"' when containing whitespace
            _voDataFileDir, voDataFile = os.path.split(prop_file_path)
            path = os.path.join(dir, voDataFile)
            try:
                voDataFilePath = open(path, "rb")
            except OSError as ex:
                raise GocadDataFileIOError(path, ex.errno, ex.strerror)
            offset = int(prop["OFFSET"][0])
            if offset > 0:
                voDataFilePath.seek(offset)
            data = self.load_data(voDataFilePath, is_msb)
            filter_array = None
            if "NO_DATA_VALUE" in prop:
                [no_data_replacement_val] = prop["NO_DATA_VALUE"]
                filter_array = data == float(no_data_replacement_val)
            result[prop["name"]] = (data, filter_array)
        return result


I_matrix = numpy.identity(3, numpy.float64)
ZEROS = numpy.zeros(3, numpy.float64)
ONES = numpy.ones(3, numpy.float64)

GRID_DEF_MIN = ZEROS
GRID_DEF_MAX = ONES


def normalize_coordinates(axis_dict: dict[str, numpy.ndarray]) -> None:
    min_vec = axis_dict.get("MIN", GRID_DEF_MIN).copy()
    max_vec = axis_dict.get("MAX", GRID_DEF_MAX).copy()
    spacing = axis_dict.get("D")
    for i, name in enumerate(["U", "V", "W"]):
        if name not in axis_dict:
            raise GocadInvalidDataError(f"Missing AXIS_{name}")
        axis_vector = axis_dict[name]
        length = numpy.linalg.norm(axis_vector)
        min_vec[i] *= length
        max_vec[i] *= length
        if spacing is not None:
            spacing[i] *= length
        axis_dict[name] = axis_vector / length
    axis_dict["MIN"] = min_vec
    axis_dict["MAX"] = max_vec


def get_grid_transform(grid: dict[str, numpy.ndarray]) -> tuple[Union[numpy.ndarray, None], Union[numpy.ndarray, None]]:
    mtx = numpy.array([grid["U"], grid["V"], grid["W"]])
    if numpy.all(mtx == I_matrix):
        mtx = None
    off = grid.get("O")
    if off is None:
        raise GocadInvalidDataError("Missing AXIS_O")
    if numpy.all(off == ZEROS):
        off = None
    if grid.get("ZPOSITIVE", "Elevation").lower() == "depth":
        mtx[:, 2] *= -1.0
        if off is not None:
            off[2] *= -1.0
    return mtx, off


def get_grid_shape(grid: dict[str, numpy.ndarray]) -> tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    min = grid.get("MIN", GRID_DEF_MIN)
    max = grid.get("MAX", GRID_DEF_MAX)
    if numpy.equal(min, max).all():
        raise GocadInvalidDataError("AXIS_MIN and AXIS_MAX should not be equal")
    size = grid.get("N")
    spacing = grid.get("D")
    if size is None:
        if spacing is None:
            raise GocadInvalidDataError("Grid dimensions are missing")
        size = numpy.ceil((max - min / spacing) + 0.5)
    else:
        if numpy.any(size != numpy.ceil(size)):
            raise GocadInvalidDataError("Invalid grid dimensions")
        if spacing is None:
            spacing = (max - min) / (size - 1)

    isize = size.astype(numpy.int32)
    return min, spacing, isize


def get_grid_params(
    axis: dict[str, numpy.ndarray],
) -> tuple[
    tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray], tuple[Union[numpy.ndarray, None], Union[numpy.ndarray, None]]
]:
    normalize_coordinates(axis)
    return get_grid_shape(axis), get_grid_transform(axis)


RE_HEADER_START = re.compile(r"^(\S+)\s+(\d*)")
RE_HEADER_LINE = re.compile(r"^(\S+)\:(.+)\s*$")
RE_HEADER_END = re.compile(r"^\s*\}\s*$")
RE_EMPTY = re.compile(r"^\s*$")
RE_COMMENTED_LINE = re.compile("^#")


def _next_line(it_lines: "Iterator[str]", skip_commented_lines: bool = True) -> list[str]:
    for line in it_lines:
        if not RE_EMPTY.match(line):
            if not (skip_commented_lines and RE_COMMENTED_LINE.match(line) is not None):
                result = line.rstrip().split(None, 1)
                if len(result) != 2:
                    if line.startswith("END") or line.startswith("GOCAD"):
                        # these are valid lines without a value, return an empty value to make using this function easier.
                        result.append("")
                    else:
                        raise GocadInvalidDataError("Incorrect data format")
                return result
    raise GocadInvalidDataError("Unexpected end of file")


def parse_vo(
    it_lines: "Iterator[str]",
) -> tuple[
    dict[str, str] | None, dict[str, numpy.ndarray], dict[int, dict[str, Union[str, list[str], dict[str, str]]]]
]:
    key, value = _next_line(it_lines)
    while key != "GOCAD" or value.split() != ["Voxet", "1"]:
        key, value = _next_line(it_lines)
    line = _next_line(it_lines)
    if line != ["HEADER", "{"]:
        print(line)
        raise GocadInvalidDataError("Header not found")
    header = parse_header(it_lines)
    axis = {}
    key, value = _next_line(it_lines)

    # ignore the block between GOCAD_ORIGINAL_COORDINATE_SYSTEM and END_ORIGINAL_COORDINATE_SYSTEM
    if key == "GOCAD_ORIGINAL_COORDINATE_SYSTEM":
        while key != "END_ORIGINAL_COORDINATE_SYSTEM":
            if key == "ZPOSITIVE":
                axis["ZPOSITIVE"] = value
            key, value = _next_line(it_lines)
        key, value = _next_line(it_lines)

    # Ignore all lines until we hit our expected AXIS section
    # See LF-24600 for the reason
    while not key.startswith("AXIS_"):
        key, value = _next_line(it_lines)

    while key.startswith("AXIS_"):
        try:
            axis[key[5:]] = numpy.array([float(v) for v in value.split()], numpy.float64)
        except ValueError:
            pass
        key, value = _next_line(it_lines)
    props = {}
    default_property_file = None
    while 1:
        while key not in ["PROPERTY", "END"]:
            if key == "ASCII_DATA_FILE":
                default_property_file = value
            key, value = _next_line(it_lines)

        if key == "END":
            return header, axis, props

        num, name = value.split(None, 1)
        prop_num = num = int(num)
        prop = {"num": num, "name": name, "FILE": [default_property_file], "ETYPE": ["IEEE"], "OFFSET": ["0"]}
        if num in props:
            raise GocadInvalidDataError("Duplicate property found")
        props[num] = prop

        while 1:
            key, value = _next_line(it_lines)
            if key == "END":
                return header, axis, props
            if not key.startswith("PROP"):
                continue
            if key[4] == "_":
                pkey = key[5:]
                values = value.split()
                num = values[0]
                pvalue = values[1:]
            else:
                if key[4:8] != "ERTY":
                    raise GocadInvalidDataError("Invalid property key found")
                if key == "PROPERTY":
                    break
                pkey = key[9:]
                num, pvalue = value.split(None, 1)

                if pkey == "CLASS_HEADER":
                    name, bracket = pvalue.rsplit(None, 1)
                    if bracket != "{":
                        raise GocadInvalidDataError("Invalid property class header found")
                    pvalue = parse_header(it_lines)
                    pvalue["name"] = name
            num = int(num)
            if num != prop_num:
                raise GocadInvalidDataError("Incorrect property number found")
            prop[pkey] = pvalue


def parse_header(it_lines: Iterator[str]) -> dict[str, str] | None:
    vals: dict[str, str] = {}
    for line in it_lines:
        m = RE_HEADER_LINE.match(line)
        if m is None:
            if RE_HEADER_END.match(line):
                return vals
            continue
        vals[m.group(1)] = m.group(2)
    return None


class VOReadResult:
    def __init__(
        self,
        header: dict[str, str] | None,
        base_grid_shape: tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray],
        transform: tuple[Union[numpy.ndarray, None], Union[numpy.ndarray, None]],
        properties: dict[int, dict[str, Union[str, list[str], dict[str, str]]]],
    ):
        self.header = header
        self.base_grid_shape = base_grid_shape
        self.rotation, self.offset = transform
        self.properties = properties
        self._validate()

    @property
    def transform(self) -> tuple[Union[numpy.ndarray, None], Union[numpy.ndarray, None]]:
        return self.rotation, self.offset

    @staticmethod
    def has_nan(arr: numpy.ndarray) -> bool:
        return bool(numpy.isnan(arr).any())

    @staticmethod
    def has_zero(arr: numpy.ndarray) -> bool:
        return bool(numpy.equal(arr, 0.0).any())

    def _validate(self) -> None:
        # Validate base grid shape
        min_point, spacing, isize = self.base_grid_shape
        if min_point is None or self.has_nan(min_point):
            raise GocadInvalidDataError("Bad MIN")
        if spacing is None or self.has_nan(spacing) or self.has_zero(spacing):
            raise GocadInvalidDataError("Bad spacing size")
        if isize is None or self.has_nan(isize) or self.has_zero(isize):
            raise GocadInvalidDataError("Bad block size")

        # Validate transform
        if self.rotation is not None:
            if self.has_nan(self.rotation):
                raise GocadInvalidDataError("Bad rotation")
            if numpy.linalg.det(self.rotation) == 0:
                raise GocadInvalidDataError("Rotation is linearly dependent")
        if self.offset is not None:
            if self.has_nan(self.offset):
                raise GocadInvalidDataError("Bad offset")


def read_vo(filename: str) -> VOReadResult:
    if not os.path.exists(filename):
        raise GocadInvalidDataError(f"The file {filename} does not exist")

    with open(filename, encoding="latin-1") as f:
        header, axis, properties = parse_vo(f)
        base_grid, transform = get_grid_params(axis)
    return VOReadResult(header, base_grid, transform, properties)


def import_gocad_voxel(
    filename: str,
) -> tuple[
    VOReadResult,
    dict[str | list[str], tuple[numpy.ndarray, typing.Any | None]],
    tuple[typing.Any, numpy.ndarray, typing.Any],
]:
    # Read properties from the .vo file
    big_endian = True
    vo_result = read_vo(filename)
    basedir = os.path.dirname(filename)
    # Load the values from the data file
    sub_sample_rate = 1
    vo_data_loader = VoDataLoader(vo_result.base_grid_shape, sub_sample_rate)
    values = vo_data_loader.load_all_data(basedir, vo_result.properties, big_endian)
    final_grid = vo_data_loader.final_min, vo_data_loader.final_spacing, vo_data_loader.final_size
    return vo_result, values, final_grid


def findSubsampleRate(base_size: int, dataSize: int) -> int:
    if base_size > dataSize:
        scalefactor = float(base_size) / float(dataSize)
        subsamplerate = scalefactor ** (1.0 / 3.0)
        return int(math.ceil(subsamplerate))
    else:
        return 1


class _ItemWithName(Protocol):
    name: str


def get_gocad_property_files(grid_name: str, all_items: list[_ItemWithName]) -> list[_ItemWithName]:
    # Gocad properties are files with no extension starting with the base grid name
    reg = re.escape(grid_name) + r"[^\.]*"
    unnamed_properties = [item for item in all_items if re.fullmatch(reg, item.name)]
    # properties may also be specified via a PROP_FILE directive, typically with a vo_data extension
    # Since we don't actually have the file yet, we hope they are in the same folder
    named_properties = [item for item in all_items if item.name.lower().endswith(".vo_data")]
    return unnamed_properties + named_properties
