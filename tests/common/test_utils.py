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
import pytest
from evo_schemas.components import BoundingBox_V1_0_1
from scipy.spatial.transform import Rotation

from evo.data_converters.common.utils import convert_rotation, grid_bounding_box, vertices_bounding_box


class TestUtils(TestCase):
    """
    Tests for utils
    """

    def test_vertices_bounding_box(self) -> None:
        # given a points array
        points = np.array(
            [
                [-100.0, 1.0, 2.0],
                [3.0, -200.0, 4.0],
                [5.0, 6.0, -300.0],
                [400.0, 7.0, 8.0],
                [9.0, 500.0, 10.0],
                [11.0, 12.0, 600.0],
            ]
        )

        # Then vertices_bounding_box returns the expected values
        bb = vertices_bounding_box(points)
        self.assertEqual(-100, bb.min_x)
        self.assertEqual(-200, bb.min_y)
        self.assertEqual(-300, bb.min_z)
        self.assertEqual(400, bb.max_x)
        self.assertEqual(500, bb.max_y)
        self.assertEqual(600, bb.max_z)


@pytest.mark.parametrize(
    "angles, dip_azimuth, dip, pitch",
    [
        pytest.param([-45, -15, -20], 45, 15, 20, id="clockwise"),
        pytest.param([12, 121, -17], 168, 121, 197, id="mixed"),
        pytest.param([0, 0, 0], 0, 0, 0, id="zero"),
    ],
)
def test_rotations(angles: list[float], dip_azimuth: float, dip: float, pitch: float) -> None:
    rotation = Rotation.from_euler("ZXZ", angles, degrees=True)
    go_rotation = convert_rotation(rotation)
    assert go_rotation.dip_azimuth == pytest.approx(dip_azimuth)
    assert go_rotation.dip == pytest.approx(dip)
    assert go_rotation.pitch == pytest.approx(pitch)


def test_get_bbox() -> None:
    orig = np.array([0, 0, 0])
    rotation_matrix = np.eye(3)
    block_sizes = np.array([1, 1, 1])
    num_blocks = np.array([2, 2, 2])
    bbox = grid_bounding_box(orig, rotation_matrix, block_sizes * num_blocks)
    expected_bbox = BoundingBox_V1_0_1(min_x=0.0, max_x=2.0, min_y=0.0, max_y=2.0, min_z=0.0, max_z=2.0)
    assert bbox == expected_bbox


def test_get_bbox_with_rotation() -> None:
    orig = np.array([0.0, 0.0, 0.0])
    rotation_matrix = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    block_sizes = np.array([1, 1, 1])
    num_blocks = np.array([2, 2, 2])
    bbox = grid_bounding_box(orig, rotation_matrix, block_sizes * num_blocks)
    expected_bbox = BoundingBox_V1_0_1(min_x=0.0, max_x=2.0, min_y=-2.0, max_y=0.0, min_z=0.0, max_z=2.0)
    assert bbox == expected_bbox


def test_get_bbox_with_offset() -> None:
    orig = np.array([1.0, 1.0, 1.0])
    rotation_matrix = np.eye(3)
    block_sizes = np.array([1, 1, 1])
    num_blocks = np.array([2, 2, 2])
    bbox = grid_bounding_box(orig, rotation_matrix, block_sizes * num_blocks)
    expected_bbox = BoundingBox_V1_0_1(min_x=1.0, max_x=3.0, min_y=1.0, max_y=3.0, min_z=1.0, max_z=3.0)
    assert bbox == expected_bbox


def test_get_bbox_non_orthogonal_with_offset() -> None:
    orig = np.array([1449895.62073, 21595604.87936, 5968.65961])
    rotation_matrix = np.array([[0.99939, -0.03480, 0.00001], [0.74525, 0.66679, -0.00004], [0.0, 0.0, 1.0]])
    block_sizes = np.array([16.36803, 10.14984, 5.34010])
    num_blocks = np.array([100, 100, 100])
    bbox = grid_bounding_box(orig, rotation_matrix, block_sizes * num_blocks)

    min_coord = (bbox.min_x, bbox.min_y, bbox.min_z)
    max_coord = (bbox.max_x, bbox.max_y, bbox.max_z)

    assert min_coord == (
        pytest.approx(1449895.62073, rel=1e-5),
        pytest.approx(21595547.92033, rel=1e-5),
        pytest.approx(5968.61996, rel=1e-5),
    )
    assert max_coord == (
        pytest.approx(1452287.84806, rel=1e-5),
        pytest.approx(21596281.65616, rel=1e-5),
        pytest.approx(6502.68848, rel=1e-5),
    )
