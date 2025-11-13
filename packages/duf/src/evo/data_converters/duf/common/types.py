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
from typing import Protocol

import numpy
from numpy.typing import NDArray

from evo.data_converters.duf.common.attributes import EvoAttributes


class IndexedEvoAttributes:
    def __init__(self, index: int, attributes: EvoAttributes):
        self._index = index
        self._attributes = attributes


class AttributedEvoData(Protocol):
    name: str
    attributes: list[EvoAttributes]


@dataclass
class FetchedTriangleMesh:
    name: str
    vertices: NDArray[numpy.float64]
    parts: list[NDArray[numpy.int32]]  # Lists of triangles
    attributes: list[EvoAttributes]


@dataclass
class FetchedLines:
    name: str
    paths: list[NDArray[numpy.float64]]  # Lists of arrays of 3D points
    attributes: list[EvoAttributes]
