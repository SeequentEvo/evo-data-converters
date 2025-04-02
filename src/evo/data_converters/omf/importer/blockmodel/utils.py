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

import math
import warnings

import numpy as np
import numpy.typing as npt
import pyarrow as pa
from scipy.spatial.transform import Rotation

import evo.logging

logger = evo.logging.getLogger("data_converters")
warnings.filterwarnings("ignore", category=UserWarning)


class IndexToSidx:
    """Class which stores the mapping of sidx to sub-block."""

    def __init__(self, max_depth: npt.NDArray[np.int_]):
        self._max_depth = max_depth
        self._total_max_depth = max(self._max_depth)
        self._next_sibling_increase = self._calculate_next_sibling_increase(max_depth)
        self._indexes_per_level = [2 ** sum(self._max_depth >= level) for level in range(1, self._total_max_depth + 1)]
        self._init_ijk_per_level()
        self._init_sidx()

    def _init_ijk_per_level(self) -> None:
        self._ijk_per_level = [np.array([0])]
        for level in range(1, self._total_max_depth + 1):
            values = [[0, 1] if subdivide else [0] for subdivide in self._max_depth >= level]
            ijk = np.array(np.meshgrid(*values, indexing="ij")).T.reshape(-1, 3)
            self._ijk_per_level.append(ijk)

    def _init_sidx(self) -> None:
        n_subblocks_per_level = np.array([1, 1, 1])
        self._sidx = {0: np.empty(n_subblocks_per_level, dtype=np.uint32)}
        for level in range(1, self._total_max_depth + 1):
            n_subblocks_per_level *= 2 ** (self._max_depth >= level)
            self._sidx[level] = np.empty(n_subblocks_per_level, dtype=np.uint32)

    def create(self) -> dict:
        self._calculate_sidx(0, 0, np.zeros(3, dtype=int))
        return self._sidx

    def _calculate_sidx(self, level: int, start_index: int, parent_ijk: npt.NDArray[np.int_]) -> None:
        indexes = self._get_level_indexes(level, start_index)
        for counter, index in enumerate(indexes):
            ijk = parent_ijk * 2 ** (self._max_depth >= level) + self._ijk_per_level[level][counter]
            i, j, k = ijk
            self._sidx[level][i][j][k] = index
            if level < self._total_max_depth:
                self._calculate_sidx(level + 1, index + 1, ijk)

    def _get_level_indexes(self, level: int, start_index: int) -> list[int]:
        if level == 0:
            return [0]
        next_sibling = self._next_sibling_increase[self._total_max_depth - level]
        return [start_index + i * next_sibling for i in range(self._indexes_per_level[level - 1])]

    @staticmethod
    def _calculate_next_sibling_increase(max_depth: npt.NDArray[np.int_]) -> dict[int, int]:
        """
        This calculates the difference with the next sub-block sibling, knowing how many levels it has underneath
        E.g. if you are in the last level, the indexes would be (starting at 5): 5, 6, 7, 8, 9... [+1]
        If it has one level under, and it's a full octree: 5, 14, 23, 32, 41... [+9]
        """
        subblocks_per_level = [2 ** sum(max_depth >= level) for level in range(max(max_depth), 1, -1)]
        result = {0: 1}
        for i in range(len(subblocks_per_level)):
            result[i + 1] = 1 + result[i] * subblocks_per_level[i]
        return result


def convert_orient_to_angle(orient_vectors: list[np.ndarray]) -> npt.NDArray[np.float_]:
    """Converts an orientation vector to an angle array (in degrees).
    The Euler rotations used are the same as those in LeapFrog, ie. intrinsic zxz.

    :param orient_vectors: An array of orientation vectors, [u, v, w].

    :return: An array of angles for each axis in that orientation.
    """
    rot = Rotation.from_matrix(orient_vectors)
    angles: npt.NDArray[np.float_] = rot.as_euler("zxz", degrees=True)
    return angles


def get_max_depth(subblocks_count: list[int]) -> npt.NDArray[np.int_]:
    """Calculate the maximum depth, aka maximum number of splits for each subblock
    in each axis (x, y, z).

    Note: This is only applicable to variable octree models.

    :param subblocks_count: The count list of a subblock object.

    :return: An np.array of [max_splits_x_axis, max_splits_y_axis, max_splits_z_axis]
    """
    nx = subblocks_count[0]
    ny = subblocks_count[1]
    nz = subblocks_count[2]
    return np.array(
        [
            round(math.log(nx) / math.log(2)),
            round(math.log(ny) / math.log(2)),
            round(math.log(nz) / math.log(2)),
        ]
    )


def calc_level(subblock_count: list, i_min: int, i_max: int, j_min: int, j_max: int, k_min: int, k_max: int) -> int:
    """Calculate the octree level.

    :param subblock_count: The subblock grid size
    :params i_min, i_max, j_min, j_max, k_min, k_max: Vertices of the subblock grid.

    :return: The octree level

    Raises a value error if the subblock is invalid.
    """
    i_diff = i_max - i_min
    j_diff = j_max - j_min
    k_diff = k_max - k_min

    level_i = int(math.log2(subblock_count[0] / i_diff))
    level_j = int(math.log2(subblock_count[1] / j_diff))
    level_k = int(math.log2(subblock_count[2] / k_diff))
    level = max(level_i, level_j, level_k)

    # If the difference between the max and min is 1, then it can't be subdivided further,
    # so the level for that axis can be less than the max.
    if i_diff > 1 and level_i != level:
        raise ValueError("Sub-block isn't a valid sub-block.")

    if j_diff > 1 and level_j != level:
        raise ValueError("Sub-block isn't a valid sub-block.")

    if k_diff > 1 and level_k != level:
        raise ValueError("Sub-block isn't a valid sub-block.")

    return level


def schema_type_to_blocksync(pa_datatype: pa.DataType) -> str:
    """Map pyarrow schema types to BlockSync schema types.

    :param pa_datatype: The pyarrow data type to convert.

    :return: A string representation of the corresponding BlockSync data type.

    Any unsupported datatypes will be raised as errors.
    """
    if pa_datatype == pa.string():
        datatype = "Utf8"
    elif pa_datatype == pa.bool_():
        datatype = "Boolean"
    elif pa_datatype == pa.float64():
        datatype = "Float64"
    elif pa_datatype == pa.date32():
        datatype = "Date32"
    elif pa_datatype == pa.timestamp("us", tz="UTC"):
        datatype = "Timestamp"
    else:
        raise AssertionError(f"The data type {pa_datatype} is not yet supported.")
    return datatype


def check_all_same(block_sizes: list[float]) -> bool:
    """Checks if all the floats in a block size list are the same.
    This is relative to the default tolerance provided by math.isclose()

    :param block_sizes: The list to be checked.

    :return: True if all values are the same, false otherwise.
    """
    block_size = block_sizes[0]
    is_same = True
    for block in block_sizes:
        if not math.isclose(block, block_size):
            is_same = False
    return is_same
