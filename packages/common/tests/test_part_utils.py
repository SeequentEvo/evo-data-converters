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

from dataclasses import dataclass
from unittest import TestCase

import numpy as np
import numpy.typing as npt

from evo.data_converters.common.part_utils import ChunkedData, IndexedData


@dataclass
class MockAttributeArrayWrapper:
    array: npt.NDArray


@dataclass
class MockAttribute:
    array: MockAttributeArrayWrapper


class PackedDataBaseTestCase(TestCase):
    vertices = np.array([[0, 2], [3, 4], [5, 6], [20, 23], [45, 46]])

    def mock_attributes(self, data_arrays: list[list]) -> list[MockAttribute]:
        return [MockAttribute(array=MockAttributeArrayWrapper(array=np.array(arr))) for arr in data_arrays]


class TestChunkedData(PackedDataBaseTestCase):
    def test_chunked_data_without_attributes(self) -> None:
        chunks = np.array([[0, 3], [1, 2], [2, 3]])
        expected = [[0, 2], [3, 4], [5, 6], [3, 4], [5, 6], [5, 6], [20, 23], [45, 46]]

        chunked_data = ChunkedData(data=self.vertices, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), expected)

    def test_chunked_data_is_whole_array(self) -> None:
        chunks = np.array([[0, len(self.vertices)]])

        chunked_data = ChunkedData(data=self.vertices, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), self.vertices.tolist())

    def test_chunked_data_is_empty(self) -> None:
        chunks = np.array([])

        chunked_data = ChunkedData(data=self.vertices, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), [])

        chunks = np.array([[0, 0]])

        chunked_data = ChunkedData(data=self.vertices, chunks=chunks)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), [])

    def test_chunked_data_with_attributes(self) -> None:
        chunks = np.array([[1, 2], [3, 2]])
        expected = [[3, 4], [5, 6], [20, 23], [45, 46]]
        attributes = self.mock_attributes([[1], [2]])

        chunked_data = ChunkedData(data=self.vertices, chunks=chunks, attributes=attributes)
        result = chunked_data.unpack()

        self.assertEqual(result.tolist(), expected)
        self.assertEqual(attributes[0].array.array.tolist(), [1, 1])
        self.assertEqual(attributes[1].array.array.tolist(), [2, 2])


class TestIndexedData(PackedDataBaseTestCase):
    def test_indexed_data(self) -> None:
        indices = np.array([0, 1, 1, 3])
        expected = [[0, 2], [3, 4], [3, 4], [20, 23]]

        indexed_data = IndexedData(data=self.vertices, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), expected)

    def test_indexed_data_is_whole_array(self) -> None:
        indices = np.array(range(len(self.vertices)))

        indexed_data = IndexedData(data=self.vertices, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), self.vertices.tolist())

    def test_indexed_data_is_empty(self) -> None:
        indices = np.array([])

        indexed_data = IndexedData(data=self.vertices, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), [])

    def test_indexed_data_is_single_index(self) -> None:
        indices = np.array([4])
        expected = [[45, 46]]

        indexed_data = IndexedData(data=self.vertices, indices=indices)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), expected)

    def test_indexed_data_with_attributes(self) -> None:
        indices = np.array([0, 2, 4])
        expected = [[0, 2], [5, 6], [45, 46]]
        attributes = self.mock_attributes(
            [
                [1, 2, 3, 4, 5],
                [0, 2, 4, 6, 8],
                [1, 3, 5, 7, 9],
                [5, 6, 7, 8, 9],
            ]
        )

        indexed_data = IndexedData(data=self.vertices, indices=indices, attributes=attributes)
        result = indexed_data.unpack()

        self.assertEqual(result.tolist(), expected)

        self.assertEqual(len(attributes), 4)
        self.assertEqual(attributes[0].array.array.tolist(), [1, 3, 5])
        self.assertEqual(attributes[1].array.array.tolist(), [0, 4, 8])
        self.assertEqual(attributes[2].array.array.tolist(), [1, 5, 9])
        self.assertEqual(attributes[3].array.array.tolist(), [5, 7, 9])
