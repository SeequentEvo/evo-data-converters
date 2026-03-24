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

from evo.data_converters.obj.exporter.part_utils import ChunkedData, IndexedData


class PackedDataBaseTestCase(TestCase):
    data = np.array([[0, 2, 3], [4, 5, 6], [7, 8, 9], [20, 23, 24], [45, 46, 47]])


class TestChunkedData(PackedDataBaseTestCase):
    def test_chunked_data(self) -> None:
        chunks = np.array([[0, 3], [1, 2], [2, 3]])
        expected = [[0, 2, 3], [4, 5, 6], [7, 8, 9], [4, 5, 6], [7, 8, 9], [7, 8, 9], [20, 23, 24], [45, 46, 47]]

        chunked_data = ChunkedData(data=self.data, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), expected)

    def test_chunked_data_is_whole_array(self) -> None:
        chunks = np.array([[0, len(self.data)]])

        chunked_data = ChunkedData(data=self.data, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), self.data.tolist())

    def test_chunked_data_is_empty(self) -> None:
        chunks = np.array([])

        chunked_data = ChunkedData(data=self.data, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), [])

        chunks = np.array([[0, 0]])

        chunked_data = ChunkedData(data=self.data, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), [])


class TestIndexedData(PackedDataBaseTestCase):
    def test_indexed_data(self) -> None:
        indices = np.array([0, 1, 1, 3])
        expected = [[0, 2, 3], [4, 5, 6], [4, 5, 6], [20, 23, 24]]

        indexed_data = IndexedData(data=self.data, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), expected)

    def test_indexed_data_is_whole_array(self) -> None:
        indices = np.array(range(len(self.data)))

        indexed_data = IndexedData(data=self.data, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), self.data.tolist())

    def test_indexed_data_is_empty(self) -> None:
        indices = np.array([])

        indexed_data = IndexedData(data=self.data, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), [])

    def test_indexed_data_is_single_index(self) -> None:
        indices = np.array([4])
        expected = [[45, 46, 47]]

        indexed_data = IndexedData(data=self.data, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), expected)
