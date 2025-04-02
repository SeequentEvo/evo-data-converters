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

import math
from typing import Any, Optional
from zipfile import BadZipFile

import numpy as np
import resqpy.crs as rqc
import resqpy.olio.xml_et as rqet
from evo_schemas.components import Crs_V1_0_1_EpsgCode as Crs_EpsgCode
from resqpy.grid import Grid
from resqpy.model import Model, ModelContext
from resqpy.property import Property
from resqpy.well import Trajectory


def is_resqml(filepath: str) -> bool:
    r"""
    Returns true if the file appears to be a RESQML file.

    Requires:
        The file pointed to by file path must exist

    Ensures:
        True  if file path points to a valid RESQML file
        False if file paths does not point to a valid RESQML file

    Raises:
        FileNotFoundError if the file does not exist.
    """

    try:
        # Attempt to open the file as a RESQML model
        with ModelContext(filepath) as _:
            return True
    except (BadZipFile, AssertionError, KeyError):
        pass
    return False


def property_is_discrete(p: Property) -> bool:
    """Is the RESQML property a discrete property?

    RESQML does not provide an explicit function to do this.
    However, the values should be integers, so check the underlying numpy
    array type and require that it be an integer type

    requires:
        p is not None
    ensures:
        IF    p is None
           OR p.array_ref() is None
           OR p.is_continuous
           OR p.is_points
           OR p.is_categorical
        THEN
            False
        ELSE IF p.array_ref().dtype.kind is u
             OR p.array_ref().dtype.kind is i
            True
        ELSE
            False
    """

    if p.is_continuous() or p.is_points() or p.is_categorical():
        return False

    array_ref = p.array_ref()
    if array_ref is None:
        return False
    if array_ref.dtype.kind != "i" and array_ref.dtype.kind != "u":
        return False
    return True


def load_lattice_array(object: Any, node: Any, array_attribute: str, trajectory: Trajectory) -> None:
    """
    Loads the measured depth nodes data as an attribute of object, from the xml node.
    This loader expects the data to be in the form of a lattice array, which is a
    variant of NodeMd data expressed as a series of regularly spaced measured depth values.

    :param: object: The object to load the data into (typically a WellboreFrame)
    :param: node: The XML node to load the data from
    :param: array_attribute: The name of the attribute on 'object' to load the data into
    :param: trajectory: The trajectory object to use to check the validity of the data
    """

    def check_md(md: float, trajectory: Trajectory) -> bool:
        xyz = np.array(trajectory.xyz_for_md(md))
        return isinstance(xyz, np.ndarray) and xyz.shape == (3,)

    if array_attribute is not None and getattr(object, array_attribute, None) is not None:
        return

    start_value = rqet.find_tag_float(node, "StartValue", must_exist=True)
    offset = rqet.find_tag(node, "Offset", must_exist=True)
    step_value = rqet.find_tag_float(offset, "Value", must_exist=True)
    step_count = rqet.find_tag_int(offset, "Count", must_exist=True)

    if step_count > 0:
        step_mds = start_value + np.arange(step_count) * step_value
        valid_mds = [md for md in step_mds if check_md(md, trajectory)]
        object.__dict__[array_attribute] = np.array(valid_mds)


def get_crs_epsg_code(model: Model, int_epsg_code: Optional[int] = None) -> Crs_EpsgCode | None:
    """
    # Return the CRS EPSG code as Evo Crs_EpsgCode object.
    # If an integer EPSG code is provided then use that, otherwise default
    # to the Model crs_root. If neither option results in a valid EPSG code
    # return None.

    :param model: The resqpy model
    :param int_epsg_code: An integer code to use
    :return: an Evo Crs_EpsqCode
    """
    assert model is not None

    if int_epsg_code is not None:
        return Crs_EpsgCode(epsg_code=int_epsg_code)

    crs_root = rqc.Crs(model, uuid=model.crs_uuid)
    if crs_root is not None and crs_root.epsg_code is not None:
        return Crs_EpsgCode(epsg_code=int(crs_root.epsg_code))

    return None


def convert_size(size_bytes: int) -> str:
    """Display a size in bytes in a more human-readable form"""
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KiB", "MiB", "GiB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


CORNERS_PER_CELL = 8
"""Number of corner points for a cell"""

FLOAT_64_SIZE = 8
"""Number of bytes in a float_64"""

FLOATS_IN_XYZ = 3
""" Number of floats making up the corner points xyz coordinates"""


def estimate_corner_points_size(grid: Grid) -> int:
    """Calculate an estimate of the size of the corner_points array for a Grid.
    As this can get very large, causing out of memory issues.
    The estimate can be used to decide whether there is enough memory to
    import a particular grid"""

    cells = (grid.nk or 1) * (grid.nj or 1) * (grid.ni or 1)
    return cells * CORNERS_PER_CELL * FLOATS_IN_XYZ * FLOAT_64_SIZE
