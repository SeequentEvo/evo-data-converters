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

from unittest import TestCase

import numpy as np
import pyarrow as pa

from evo.data_converters.omf.importer.blockmodel.utils import (
    IndexToSidx,
    calc_level,
    check_all_same,
    get_max_depth,
    schema_type_to_blocksync,
)


class TestUtilsFromBlockSync(TestCase):
    def test_index_to_sidx(self) -> None:
        max_depth = np.array([3, 2, 1])
        i2s = IndexToSidx(max_depth).create()
        self.assertEqual(i2s[0][0, 0, 0], 0)
        self.assertEqual(i2s[1][0, 0, 0], 1)
        self.assertEqual(i2s[1][1, 0, 0], 14)
        self.assertEqual(i2s[1][0, 1, 0], 27)
        self.assertEqual(i2s[1][1, 1, 0], 40)
        self.assertEqual(i2s[1][0, 0, 1], 53)
        self.assertEqual(i2s[2][0, 0, 0], 2)
        self.assertEqual(i2s[2][1, 0, 0], 5)
        self.assertEqual(i2s[2][0, 1, 0], 8)
        self.assertEqual(i2s[2][1, 1, 0], 11)
        self.assertEqual(i2s[3][0, 0, 0], 3)
        self.assertEqual(i2s[3][1, 0, 0], 4)
        self.assertEqual(i2s[3][0, 1, 0], 9)
        self.assertEqual(i2s[3][1, 1, 0], 10)

    def test_max_depth(self) -> None:
        max_depth_1 = get_max_depth([1, 2, 4])

        self.assertEqual(max_depth_1[0], 0)
        self.assertEqual(max_depth_1[1], 1)
        self.assertEqual(max_depth_1[2], 2)

        max_depth_2 = get_max_depth([8, 16, 32])
        self.assertEqual(max_depth_2[0], 3)
        self.assertEqual(max_depth_2[1], 4)
        self.assertEqual(max_depth_2[2], 5)

        max_depth_3 = get_max_depth([64, 64, 64])
        self.assertEqual(max_depth_3[0], 6)
        self.assertEqual(max_depth_3[1], 6)
        self.assertEqual(max_depth_3[2], 6)

    def test_calc_level(self) -> None:
        subblock_count = [8, 4, 2]

        i_min = 0
        i_max = 8
        j_min = 0
        j_max = 4
        k_min = 0
        k_max = 2
        expected_lvl = 0
        lvl = calc_level(subblock_count, i_min, i_max, j_min, j_max, k_min, k_max)
        self.assertEqual(lvl, expected_lvl)

        i_min_2 = 4
        i_max_2 = 8
        j_min_2 = 0
        j_max_2 = 2
        k_min_2 = 0
        k_max_2 = 1
        expected_lvl_2 = 1
        lvl_2 = calc_level(subblock_count, i_min_2, i_max_2, j_min_2, j_max_2, k_min_2, k_max_2)
        self.assertEqual(lvl_2, expected_lvl_2)

    def test_check_all_same_int(self) -> None:
        test_block_sizes = [9, 9, 9, 9]
        actual = check_all_same(test_block_sizes)
        self.assertEqual(actual, True)

    def test_check_all_same_float_true(self) -> None:
        test_block_sizes = [9.2, 9.2, 9.2, 9.20000000000000001]
        actual = check_all_same(test_block_sizes)
        self.assertEqual(actual, True)

    def test_check_all_same_float_false(self) -> None:
        test_block_sizes = [9.2, 9.2, 9.2, 9.2001]
        actual = check_all_same(test_block_sizes)
        self.assertEqual(actual, False)

    def test_schema_type_to_blocksync(self) -> None:
        self.assertEqual(schema_type_to_blocksync(pa.string()), "Utf8")
        self.assertEqual(schema_type_to_blocksync(pa.bool_()), "Boolean")
        self.assertEqual(schema_type_to_blocksync(pa.float64()), "Float64")
        self.assertEqual(schema_type_to_blocksync(pa.date32()), "Date32")
        self.assertEqual(schema_type_to_blocksync(pa.timestamp("us", tz="UTC")), "Timestamp")

        with self.assertRaises(AssertionError):
            # Should raise an assertion if it doesn't handle the type
            schema_type_to_blocksync(pa.int16())
