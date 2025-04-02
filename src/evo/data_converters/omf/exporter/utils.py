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
from typing import Optional

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
    attributes: Optional[list] = None

    def __len__(self) -> int:
        return int(sum(n for _, n in self.chunks))

    def unpack(self) -> npt.NDArray:
        """
        Unpack the data array to include all (start_index, length) sequences defined by the chunks
        array. Also modifies the attributes data in-place, if defined.

        :returns: The unpacked data as an NDArray.
        """
        if self.attributes:
            return self._unpack_with_attributes()

        data = self._empty_array_from(self.data)
        i = 0

        for chunk in self.chunks:
            idx, n = map(int, chunk)
            data[i : i + n] = self.data[idx : idx + n]
            i += n

        return data

    def _unpack_with_attributes(self) -> npt.NDArray:
        if not self.attributes:
            raise ValueError("Undefined attributes")

        data = self._empty_array_from(self.data)
        i = 0

        for chunk, attr in zip(self.chunks, self.attributes):
            idx, n = map(int, chunk)
            data[i : i + n] = self.data[idx : idx + n]
            attr.array.array = np.tile(attr.array.array, n)
            i += n

        return data


@dataclass
class IndexedData(PackedData):
    data: npt.NDArray
    indices: npt.NDArray[np.uint]
    attributes: Optional[list] = None

    def __len__(self) -> int:
        return len(self.indices)

    def unpack(self) -> npt.NDArray:
        """
        Unpack the data array to include all indices defined by the indices array. Also modifies
        the attributes data in-place, if defined.

        :returns: The unpacked data as an NDArray.
        """
        if self.attributes:
            return self._unpack_with_attributes()

        data = self._empty_array_from(self.data)

        for i, idx in enumerate(self.indices):
            data[i] = self.data[idx]

        return data

    def _unpack_with_attributes(self) -> npt.NDArray:
        if not self.attributes:
            raise ValueError("Undefined attributes")

        data = self._empty_array_from(self.data)
        attribute_data = [self._empty_array_from(attr.array.array) for attr in self.attributes]

        for i, idx in enumerate(self.indices):
            data[i] = self.data[idx]

            # rebuild this data point's attribute data for all attributes
            for attr, arr in zip(self.attributes, attribute_data):
                arr[i] = attr.array.array[idx]

        # rewrite attributes
        for attr, arr in zip(self.attributes, attribute_data):
            attr.array.array = arr

        return data
