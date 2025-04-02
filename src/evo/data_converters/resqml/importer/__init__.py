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

"""Evo RESQML importer
===================

Convert the data in RESQML formatted files, to the corresponding Evo geoscience objects and
upload them to Evo

"""

from typing import Any, Optional, Union

import numpy as np
import numpy.typing as npt
import resqpy.grid
import resqpy.olio.uuid as bu
import resqpy.olio.xml_et as rqet
import resqpy.organize as rqo
import resqpy.property as rqp
import resqpy.well as rqw
import resqpy.well.well_utils as rqwu

import evo.logging
from evo.data_converters.resqml.utils import load_lattice_array

from .conversion_options import ResqmlConversionOptions
from .resqml_to_evo import convert_resqml

__all__ = ["convert_resqml", "ResqmlConversionOptions"]


logger = evo.logging.getLogger("data_converters.resqml")


# Need to work around a issue in the grid class's
# extract_stratigraphy function to enable it to load successfully.
#
# The assertion
#    assert len(grid.stratigraphic_units) == grid.nk_plus_k_gaps
#
#    Does not hold for all input files.
def extract_stratigraphy(grid: resqpy.grid.Grid) -> None:
    """Loads stratigraphic information from xml."""
    # modified from resqpy.grid._extract_functions.extract_stratigraphy
    # add the standard resqpy abbreviated imports!
    import resqpy.olio.uuid as bu

    grid.stratigraphic_column_rank_uuid = None
    grid.stratigraphic_units = None
    strata_node = rqet.find_tag(grid.root, "IntervalStratigraphicUnits")
    if strata_node is None:
        return
    grid.stratigraphic_column_rank_uuid = bu.uuid_from_string(
        rqet.find_nested_tags_text(strata_node, ["StratigraphicOrganization", "UUID"])
    )
    assert grid.stratigraphic_column_rank_uuid is not None
    unit_indices_node = rqet.find_tag(strata_node, "UnitIndices")
    h5_key_pair = grid.model.h5_uuid_and_path_for_node(unit_indices_node)
    grid.model.h5_array_element(
        h5_key_pair, index=None, cache_array=True, object=grid, array_attribute="stratigraphic_units", dtype="int"
    )
    # only change is to comment out this assert, and to log a warning
    # assert len(grid.stratigraphic_units) == grid.nk_plus_k_gaps
    if grid.stratigraphic_units is None:
        # This should have been set by the call to grid.model.h5_array_element
        # if not, lets log the occurrence and continue
        logger.warning("grid.stratigraphic_units is None")
    elif len(grid.stratigraphic_units) != grid.nk_plus_k_gaps:
        logger.warning(
            "Number of stratigraphic units (%d) does not equal the number layers plus gaps (%d)",
            len(grid.stratigraphic_units),
            grid.nk_plus_k_gaps,
        )


# patch the module.
resqpy.grid._grid.extract_stratigraphy = extract_stratigraphy
# was resqpy.grid._extract_functions.extract_stratigraphy
#

# Need to patch resqpy.grid.point_raw, otherwise grid.corner_points will throw
#    IndexError: too many indices for array: array is 2-dimensional, but 3 were indexed
# If the grid contains split nodes.
#
_grid_point_raw = resqpy.grid._grid.point_raw


def _get_split_nodes(grid: resqpy.grid.Grid) -> int:
    split_nodes = rqet.find_tag(grid.geometry_root, "SplitNodes")
    return 0 if split_nodes is None else int(rqet.find_tag(split_nodes, "Count").text)  # pyright: ignore


def point_raw(
    grid: resqpy.grid.Grid,
    index: Optional[Union[tuple[int, int, int], tuple[int, int]]] = None,
    points_root: Optional[Any] = None,
    cache_array: bool = True,
) -> Optional[npt.NDArray[np.float_]]:
    has_cache = getattr(grid, "points_cached", None) is not None
    rv: Optional[npt.NDArray[np.float_]] = _grid_point_raw(
        grid, index=index, points_root=points_root, cache_array=cache_array
    )
    if rv is None:
        return rv

    if index is None and cache_array is True and not has_cache:
        if rv.ndim == 2:  # pyright: ignore
            num_split = _get_split_nodes(grid)
            if num_split > 0:
                logger.warning("point_raw called with split_nodes, fixing points_cached array")
                grid.raw_points_cached = grid.points_cached
                grid.points_cached = rv = grid.raw_points_cached[:-num_split].reshape(grid.nk_plus_k_gaps + 1, -1, 3)
    return rv


resqpy.grid._grid.point_raw = point_raw


# Need to add additional method for importing NodeMd data from RESQML files which
# provide it as DoubleLatticeArray. This will be called from a patch for the
# _load_from_xml method in the WellboreFrame class (resqpy/well/_wellbore_frame.py).
#
def _wellbore_frame_load_from_xml(self: rqw.WellboreFrame) -> None:
    """Loads the wellbore frame object from an xml node (and associated hdf5 data)."""

    # NB: node is the root level xml node, not a node in the md list!

    node = self.root
    assert node is not None

    trajectory_uuid = bu.uuid_from_string(rqet.find_nested_tags_text(node, ["Trajectory", "UUID"]))
    assert trajectory_uuid is not None, "wellbore frame trajectory reference not found in xml"
    if self.trajectory is None:
        self.trajectory = rqw.Trajectory(self.model, uuid=trajectory_uuid)
    else:
        assert bu.matching_uuids(self.trajectory.uuid, trajectory_uuid), "wellbore frame trajectory uuid mismatch"

    self.node_count = rqet.find_tag_int(node, "NodeCount")
    assert self.node_count is not None, "node count not found in xml for wellbore frame"
    assert self.node_count > 1, "fewer than 2 nodes for wellbore frame"

    mds_node = rqet.find_tag(node, "NodeMd")

    assert mds_node is not None, "wellbore frame measured depths hdf5 reference not found in xml"

    # Load the node measured depths from either a DoubleLatticeArray or hdf5 array
    if rqet.node_type(mds_node) == "DoubleLatticeArray":
        load_lattice_array(self, mds_node, "node_mds", self.trajectory)
        self.node_count = self.node_mds.size
    else:
        rqwu.load_hdf5_array(self, mds_node, "node_mds")

    assert self.node_mds is not None and self.node_mds.ndim == 1 and self.node_mds.size == self.node_count

    interp_uuid = rqet.find_nested_tags_text(node, ["RepresentedInterpretation", "UUID"])
    if interp_uuid is None:
        self.wellbore_interpretation = None
    else:
        self.wellbore_interpretation = rqo.WellboreInterpretation(self.model, uuid=interp_uuid)

    self.extract_property_collection()
    self.logs = rqp.WellLogCollection(frame=self)


# Patch the above method into the WellboreFrame class
rqw._wellbore_frame.WellboreFrame._load_from_xml = _wellbore_frame_load_from_xml
