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

import numpy as np
import numpy.typing as npt


class PackedData:
    def __len__(self) -> int:
        raise NotImplementedError

    def _empty_array_from(self, arr: npt.NDArray) -> npt.NDArray:
        return np.empty((len(self), *arr.shape[1:]), dtype=arr.dtype)

    def unpack(self) -> npt.NDArray:
        raise NotImplementedError


@dataclass
class ChunkedData(PackedData):
    data: npt.NDArray
    chunks: npt.NDArray[np.uint]

    def __len__(self) -> int:
        return int(sum(n for _, n in self.chunks))

    def unpack(self) -> npt.NDArray:
        """
        Unpack the data array to include all (start_index, length) sequences defined by the chunks
        array.

        :returns: The unpacked data as an NDArray.

        Example:
        ```
            ChunkedData(
                data=np.array([[0,1,2], [2,3,4], [5,6,7], [8,9,10], [11,12,13]]),
                chunks=np.array([[0, 2], [1, 3]])
            ).unpack()
        ```
            Returns:
        ```
            np.array([[0,1,2], [2,3,4], [2,3,4], [5,6,7], [8,9,10]])
        ```
            `[2,3,4]` appears twice as it is in both chunks.

            `[11,12,13]` is omitted as it is not part of a chunk.
        """
        data = self._empty_array_from(self.data)
        i = 0

        for chunk in self.chunks:
            idx, n = map(int, chunk)
            data[i : i + n] = self.data[idx : idx + n]
            i += n

        return data


@dataclass
class IndexedData(PackedData):
    data: npt.NDArray
    indices: npt.NDArray[np.uint]

    def __len__(self) -> int:
        return len(self.indices)

    def unpack(self) -> npt.NDArray:
        """
        Unpack the data array to include all indices defined by the indices array.

        :returns: The unpacked data as an NDArray.

        Example:
        ```
            IndexedData(
                data=np.array([[0,1,2], [2,3,4], [5,6,7], [8,9,10]),
                indices=np.array([[0, 1, 3]])
            ).unpack()
        ```
            Returns:
        ```
            np.array([[0,1,2], [2,3,4], [8,9,10]])
        ```
        """

        data = self._empty_array_from(self.data)

        for i, idx in enumerate(self.indices):
            data[i] = self.data[idx]

        return data
