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
    """
    Base representation of a 3D grid

    Attributes:
    -----------
    origin: list[float] - The coordinates of the origin [x,y,z]
    size: list[int] - The size of the entire grid [grid_size_x, grid_size_y, grid_size_z]
    rotation: numpy NDArray[numpy float] - Orientation of the grid [dip_azimuth, dip, pitch]
    bounding_box: list[float] | None - Bounding box of the spatial data
    mask: numpy NDArray[numpy bool] | None - Indicates which cells have values
    cell_attributes: dict[str, numpy NDArray] | None - Attributes associated with the cells
    vertex_attributes: dict[str, numpy NDArray] | None - Attributes associated with the vertices
    """

    origin: list[float]
    size: list[int]
    rotation: npt.NDArray[np.float_]
    bounding_box: list[float] | None
    mask: npt.NDArray[np.bool_] | None
    cell_attributes: dict[str, np.ndarray] | None
    vertex_attributes: dict[str, np.ndarray] | None


@dataclass
class RegularGridData(BaseGridData):
    """
    Representation of a regular 3D grid

    Attributes:
    -----------
    origin: list[float] - The coordinates of the origin [x,y,z]
    size: list[int] - The size of the entire grid [grid_size_x, grid_size_y, grid_size_z]
    rotation: numpy NDArray[numpy float] - Orientation of the grid [dip_azimuth, dip, pitch]
    bounding_box: list[float] | None - Bounding box of the spatial data
    mask: numpy NDArray[numpy bool] | None - Indicates which cells have values
    cell_attributes: dict[str, numpy NDArray] | None - Attributes associated with the cells
    vertex_attributes: dict[str, numpy NDArray] | None - Attributes associated with the vertices
    cell_size: list[float] - The size of each cell in the grid [cell_size_x, cell_size_y, cell_size_z]
    """

    cell_size: list[float]


@dataclass
class TensorGridData(BaseGridData):
    """
    Representation of a tensor 3D grid, where cells may have different sizes

    Attributes:
    -----------
    origin: list[float] - The coordinates of the origin [x,y,z]
    size: list[int] - The size of the entire grid [grid_size_x, grid_size_y, grid_size_z]
    rotation: numpy NDArray[numpy float] - Orientation of the grid [dip_azimuth, dip, pitch]
    bounding_box: list[float] | None - Bounding box of the spatial data
    mask: numpy NDArray[numpy bool] | None - Indicates which cells have values
    cell_attributes: dict[str, numpy NDArray] | None - Attributes associated with the cells
    vertex_attributes: dict[str, numpy NDArray] | None - Attributes associated with the vertices
    cell_sizes_x: list[float] - Grid cell sizes along the x axis
    cell_sizes_y: list[float] - Grid cell sizes along the y axis
    cell_sizes_z: list[float] - Grid cell sizes along the z axis
    """

    cell_sizes_x: list[float]
    cell_sizes_y: list[float]
    cell_sizes_z: list[float]
