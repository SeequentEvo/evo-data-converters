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

from evo.data_converters.resqml.importer._grid_converter import _get_cells_to_include


class TestConverterGetCellsToInclude(TestCase):
    r"""
    Tests for grid_converter::_get_cells_to_include
    """

    def setUp(self) -> None:
        self.data_dir = tempfile.TemporaryDirectory()
        model_file = path.join(self.data_dir.name, "new_file.epc")
        self.model = rqm.new_model(model_file)

    def test_get_cells_to_include_test_active_only_false(self) -> None:
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
            title="BLOCK GRID",
        )

        grid.inactive = np.full((grid.nk, grid.nj, grid.ni), False)  # pyright: ignore
        grid.inactive[3, 3, 3] = True  # pyright: ignore

        (ak, aj, ai) = _get_cells_to_include(grid, False)
        self.assertEqual((10 * 20 * 25), len(ak))
        self.assertTrue(len(ak) == len(aj) and len(aj) == len(ai))
        self.assertTrue((3, 3, 3) in zip(ak, aj, ai))
        self._check_post_conditions(grid, ak, aj, ai, False)

    def test_get_cells_to_include_test_empty_grid_active_only_true(self) -> None:
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
            title="BLOCK GRID",
        )

        grid.inactive = np.full((grid.nk, grid.nj, grid.ni), False)  # pyright: ignore
        grid.inactive[3, 3, 3] = True  # pyright: ignore

        (ak, aj, ai) = _get_cells_to_include(grid, True)
        self.assertEqual((10 * 20 * 25) - 1, len(ak))
        self.assertTrue(len(ak) == len(aj) and len(aj) == len(ai))
        self.assertFalse((3, 3, 3) in zip(ak, aj, ai))
        self._check_post_conditions(grid, ak, aj, ai, True)

    def _check_post_conditions(
        self, grid: rqg.RegularGrid, ak: npt.NDArray, aj: npt.NDArray, ai: npt.NDArray, use_active: bool
    ) -> None:
        r"""
            Check the post conditions for _unique_points
        Ensures:
            if use_active
                for all (k,j,i) in (ak, aj, ak): not grid.inactive(k,j,i)
            else
                ak, aj, ai reference all points in a [grid.nk][grid.nj][grid.ni] array
                           of True values.
        """
        # Length of the arrays should be equal
        self.assertEqual(len(ak), len(aj))
        self.assertEqual(len(ak), len(ai))

        # the arrays should be the expected length
        expected_length = grid.nk * grid.nj * grid.ni
        if use_active:
            expected_length -= (grid.inactive).sum()
        self.assertEqual(expected_length, len(ak))

        # The indexes should all be inside grid cell array bounds.
        self.assertTrue(all([k >= 0 and k < grid.nk for k in ak]))
        self.assertTrue(all([j >= 0 and j < grid.nj for j in aj]))
        self.assertTrue(all([i >= 0 and i < grid.ni for i in ai]))

        if use_active:
            # There should be no inactive cells in (ak, aj, ai)
            self.assertTrue(all([not grid.inactive[c] for c in zip(ak, aj, ai)]))
