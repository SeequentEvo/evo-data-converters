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


@dataclass
class BaseGridData:
    origin: list[float]
    size: list[int]
    rotation: npt.NDArray[np.float_]
    bounding_box: list[float] | None
    mask: npt.NDArray[np.bool_] | None
    cell_attributes: dict[str, np.ndarray] | None
    vertex_attributes: dict[str, np.ndarray] | None


@dataclass
class RegularGridData(BaseGridData):
    cell_size: list[float]


@dataclass
class TensorGridData(BaseGridData):
    cell_sizes_x: list[float]
    cell_sizes_y: list[float]
    cell_sizes_z: list[float]
