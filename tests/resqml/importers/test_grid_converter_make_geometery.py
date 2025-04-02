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

""" """

import tempfile
from os import path
from unittest import TestCase

import numpy as np
import numpy.typing as npt
import resqpy.grid as rqg
import resqpy.model as rqm

from evo.data_converters.resqml.importer._grid_converter import _make_geometry


class TestConverterMakeGeometry(TestCase):
    r"""
    Tests for grid_converter::_make_geometry
    """

    def setUp(self) -> None:
        self.data_dir = tempfile.TemporaryDirectory()
        model_file = path.join(self.data_dir.name, "new_file.epc")
        self.model = rqm.new_model(model_file)

    def test_get_geometry_include_is_none(self) -> None:
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=(3, 3, 3),
            dxyz=(4, 4, 4),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
            title="BLOCK GRID",
        )

        (points, cells) = _make_geometry(grid, None)
        self.assertEqual(64, len(points))
        self.assertEqual(27, len(cells))

    def test_get_geometry_include_centre_cell(self) -> None:
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=(3, 3, 3),
            dxyz=(4, 4, 4),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
            title="BLOCK GRID",
        )

        (points, cells) = _make_geometry(grid, ([1], [1], [1]))

        self.assertTrue((centre_corner_points == points).all())
        self.assertEqual(8, len(points))

        self.assertEqual(1, len(cells))
        self.assertTrue(([0, 4, 6, 2, 1, 5, 7, 3] == cells[0]).all())

        self._check_post_conditions(grid, cells, points)

    def test_get_geometry_include_centre_column(self) -> None:
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=(3, 3, 3),
            dxyz=(4, 4, 4),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
            title="BLOCK GRID",
        )

        (points, cells) = _make_geometry(grid, ([0, 1, 2], [1, 1, 1], [1, 1, 1]))

        self.assertTrue((centre_column_corner_points == points).all())
        self.assertEqual(16, len(points))

        self.assertEqual(3, len(cells))
        expected_cells = [[0, 8, 12, 4, 1, 9, 13, 5], [1, 9, 13, 5, 2, 10, 14, 6], [2, 10, 14, 6, 3, 11, 15, 7]]
        self.assertTrue((expected_cells == cells).all())

        self._check_post_conditions(grid, cells, points)

    def test_get_geometry_no_corner_points(self) -> None:
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=(0, 0, 0),
            dxyz=(0, 0, 0),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
            title="BLOCK GRID",
        )

        (points, cells) = _make_geometry(grid, None)
        self.assertEqual(0, len(points))
        self.assertEqual(0, len(cells))

    def _check_post_conditions(self, grid: rqg.RegularGrid, cells: npt.NDArray, points: npt.NDArray) -> None:
        # all points are unique
        self.assertTrue(len(points), len(np.unique(points)))

        # all cells are unique
        self.assertTrue(len(cells), len(np.unique(cells)))

        # all points are in in the global points space of
        # the original corner points
        pl = points.tolist()
        cps = grid.corner_points().copy()
        grid.crs.local_to_global_array(cps, global_z_inc_down=False)
        self.assertTrue(all([c in cps for c in pl]))


centre_corner_points = [
    [4.0, 4.0, -4.0],
    [4.0, 4.0, -8.0],
    [4.0, 8.0, -4.0],
    [4.0, 8.0, -8.0],
    [8.0, 4.0, -4.0],
    [8.0, 4.0, -8.0],
    [8.0, 8.0, -4.0],
    [8.0, 8.0, -8.0],
]

centre_column_corner_points = [
    [4.0, 4.0, -0.0],
    [4.0, 4.0, -4.0],
    [4.0, 4.0, -8.0],
    [4.0, 4.0, -12.0],
    [4.0, 8.0, -0.0],
    [4.0, 8.0, -4.0],
    [4.0, 8.0, -8.0],
    [4.0, 8.0, -12.0],
    [8.0, 4.0, -0.0],
    [8.0, 4.0, -4.0],
    [8.0, 4.0, -8.0],
    [8.0, 4.0, -12.0],
    [8.0, 8.0, -0.0],
    [8.0, 8.0, -4.0],
    [8.0, 8.0, -8.0],
    [8.0, 8.0, -12.0],
]
