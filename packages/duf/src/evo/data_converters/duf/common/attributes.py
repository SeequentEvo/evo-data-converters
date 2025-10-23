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

import numpy
import pyarrow
from numpy.typing import NDArray


@dataclass
class EvoAttributes:
    name: str
    type: str
    description: str
    fetched_table: pyarrow.Table
    lookup_table: pyarrow.Table | None
    nan_description: list[float] | list[int] | None

    def __post_init__(self):
        self._values: NDArray | None = None
        self._nan_mask: NDArray[numpy.bool_] | None = None
        self._processed: bool = False

    @property
    def values(self) -> NDArray:
        if not self._processed:
            self.process()
        return self._values

    @property
    def nan_mask(self) -> NDArray[numpy.bool_]:
        if not self._processed:
            self.process()
        return self._nan_mask

    def process(self):
        attr_values = numpy.asarray(self.fetched_table)
        attr_values = attr_values.reshape(len(attr_values))

        nan_mask = None
        if self.nan_description is not None:
            nan_mask = numpy.logical_or.reduce([attr_values == x for x in self.nan_description])

        processed = attr_values
        if self.lookup_table is not None:
            lookup = {k.as_py(): v.as_py() for k, v in zip(self.lookup_table.column(0), self.lookup_table.column(1))}
            # The lookup tables are for categories, so the type will be a str
            lookup_vec = numpy.vectorize(lambda k: lookup.get(k, ""))
            processed = lookup_vec(attr_values)

        if numpy.any(nan_mask):
            self._nan_mask = nan_mask
        self._values = processed
        self._processed = True
