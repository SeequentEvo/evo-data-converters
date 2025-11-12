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

from typing import Any

import numpy as np
from evo_schemas.components import BoundingBox_V1_0_1, Rotation_V1_1_0
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation


def vertices_bounding_box(vertices: NDArray[Any]) -> BoundingBox_V1_0_1:
    bbox_min = np.min(vertices, axis=0)
    bbox_max = np.max(vertices, axis=0)

    return BoundingBox_V1_0_1(
        min_x=float(bbox_min[0]),
        max_x=float(bbox_max[0]),
        min_y=float(bbox_min[1]),
        max_y=float(bbox_max[1]),
        min_z=float(bbox_min[2]),
        max_z=float(bbox_max[2]),
    )


def grid_bounding_box(
    orig: np.ndarray, transformation_matrix: np.ndarray, grid_extents: np.ndarray
) -> BoundingBox_V1_0_1:
    """
    Calculated bounding box of the grid using origin coordinates, transformation matrix and grid extents.
    - Defines the local corners of the grid based on the grid extents.
    - Transforms these local corners using the transformation matrix and adds the origin coordinates to get the global corners.
    - Computes the minimum and maximum coordinates from the global corners.
    - Returns a BoundingBox_V1_0_1 object with the calculated minimum and maximum coordinates for the x, y, and z dimensions.
    """
    local_corners = np.array(
        [
            [0, 0, 0],
            [grid_extents[0], 0, 0],
            [0, grid_extents[1], 0],
            [0, 0, grid_extents[2]],
            [grid_extents[0], grid_extents[1], 0],
            [grid_extents[0], 0, grid_extents[2]],
            [grid_extents[0], grid_extents[1], grid_extents[2]],
            [grid_extents[0], grid_extents[1], grid_extents[2]],
        ]
    )
    global_corners = np.dot(local_corners, transformation_matrix) + orig
    min_coord = np.min(global_corners, axis=0)
    max_coord = np.max(global_corners, axis=0)
    return BoundingBox_V1_0_1(
        min_x=min_coord[0],
        max_x=max_coord[0],
        min_y=min_coord[1],
        max_y=max_coord[1],
        min_z=min_coord[2],
        max_z=max_coord[2],
    )


class UnsupportedRotation(Exception):
    pass


def check_rotation_matrix(rotation_matrix: np.ndarray, threshold: float = 1e-6) -> None:
    u, v, w = rotation_matrix
    for vector in u, v, w:
        if abs(np.linalg.norm(vector) - 1) > threshold:
            raise UnsupportedRotation("scale")
    for a, b, c in [(u, v, w), (v, w, u), (w, u, v)]:
        if np.dot(np.cross(a, b), c) < 0.0:
            raise UnsupportedRotation("invert")
    for a, b in [(u, v), (v, w), (w, u)]:
        if np.dot(a, b) > threshold:
            raise UnsupportedRotation("skew")


def convert_rotation(rotation: Rotation) -> Rotation_V1_1_0:
    """
    Convert scipy Rotation object into a Geoscience Object rotation.

    The Geoscience Object rotation convention is made up of three rotations:
    - dip azimuth, clockwise rotations around the z-axis, in degrees.
    - dip, clockwise rotations around the x'-axis, in degrees.
    - pitch. clockwise rotations around the z''-axis, in degrees.

    The rotations are intrinsic, i.e. the second and third rotation is applied to the rotated coordinate system.
    The notation x' and z'' is used to indicate that the axes they apply to are rotated from the result of the first and second rotation respectively.
    """
    azimuth, dip, pitch = rotation.as_euler("ZXZ", degrees=True)

    # Rotations returned from scipy are counter-clockwise, so we need to negate them to be clockwise.
    # Also, ensure azimuth and pitch values are in the range [0, 360).
    azimuth = (-azimuth + 360) % 360
    dip = -dip
    pitch = (-pitch + 360) % 360

    # Ensure dip is in the range [0, 180). Do this by flipping the azimuth and pitch by 180 degrees.
    if dip < 0:
        azimuth = (azimuth + 180) % 360
        dip = -dip
        pitch = (pitch + 180) % 360
    return Rotation_V1_1_0(dip_azimuth=azimuth, dip=dip, pitch=pitch)


def get_object_tags(path: str, input_type: str, extra_tags: dict = None) -> dict[str, str]:
    return {
        "Source": f"{path} (via Evo Data Converters)",
        "Stage": "Experimental",  # TODO: stages is now a separate API, update or remove this
        "InputType": input_type,
        **(extra_tags if extra_tags else {}),
    }
