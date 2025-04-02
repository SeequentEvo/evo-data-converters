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

from typing import Optional

import numpy as np
import numpy.typing as npt
import pandas as pd
import pyarrow as pa
import resqpy.crs as rqcrs
import resqpy.model as rq
import resqpy.property as rqp
import resqpy.well as rqw
from evo_schemas import DownholeIntervals_V1_1_0 as DownholeIntervals
from evo_schemas.components import BoundingBox_V1_0_1 as BoundingBox
from evo_schemas.components import CategoryData_V1_0_1 as CategoryData
from evo_schemas.components import Intervals_V1_0_1 as Intervals
from evo_schemas.components import IntervalTable_V1_1_0_FromTo as IntervalTable_FromTo
from evo_schemas.components import Locations_V1_0_1 as Locations
from evo_schemas.elements import FloatArray2_V1_0_1 as FloatArray2
from evo_schemas.elements import FloatArray3_V1_0_1 as FloatArray3
from evo_schemas.elements import IntegerArray1_V1_0_1 as IntegerArray1
from evo_schemas.elements import LookupTable_V1_0_1 as LookupTable

import evo.logging
from evo.data_converters.resqml.importer._attribute_converters import convert_resqml_properties_to_evo_attributes
from evo.data_converters.resqml.utils import get_crs_epsg_code
from evo.objects.utils.data import ObjectDataClient

from .conversion_options import ResqmlConversionOptions

logger = evo.logging.getLogger("data_converters.resqml")


def convert_downhole_intervals_for_trajectory(
    model: rq.Model,
    trajectory: rqw.Trajectory,
    prefix: str,
    data_client: ObjectDataClient,
    epsg_code: Optional[int] = None,
    options: Optional[ResqmlConversionOptions] = None,
) -> list[DownholeIntervals]:
    """
    Convert all downhole intervals for a given trajectory to Evo DownholeIntervals objects
    :param model: The resqpy model
    :param trajectory: The resqpy trajectory
    :param prefix: Naming prefix, object names are not guaranteed to be unique
                   within a model. The prefix should be unique to ensure the
                   names of the generated geo science objects are unique
    :param data_client: The Evo data client
    :param epsg_code: Optional. The EPSG code to use.
    :return: A list of Evo DownholeIntervals objects
    """
    downhole_intervals_go = []

    # Iterate over WellboreFrames which reference this Trajectory
    try:
        for frame in trajectory.iter_wellbore_frames():
            dhi = _downhole_intervals_for_wellbore_frame(
                model=model,
                wellboreframe=frame,
                trajectory=trajectory,
                prefix=prefix,
                epsg_code=epsg_code,
                data_client=data_client,
            )
            if isinstance(dhi, DownholeIntervals):
                downhole_intervals_go.append(dhi)
    except AssertionError as error:
        logger.error(
            f"Unable to iterate over WellBoreFrames for Trajectory {trajectory.citation_title} {trajectory.uuid}: {error}"
        )
        return []

    return downhole_intervals_go


def _downhole_intervals_for_wellbore_frame(
    model: rq.Model,
    wellboreframe: rqw.WellboreFrame,
    trajectory: rqw.Trajectory,
    prefix: str,
    data_client: ObjectDataClient,
    epsg_code: Optional[int] = None,
) -> DownholeIntervals | None:
    """
    Convert properties associated with a wellbore frame to an Evo DownholeIntervals object
    :param model: The resqpy model
    :param wellboreframe: The resqpy wellbore frame
    :param trajectory: The resqpy trajectory
    :param prefix: Naming prefix, object names are not guaranteed to be unique
    :param data_client: The Evo data client
    :param epsg_code: Optional. The EPSG code to use.
    :return: The Evo DownholeIntervals object
    """

    # Get properties directly linked to WellboreFrame
    property_uuids = model.uuids(related_uuid=wellboreframe.uuid, obj_type="ContinuousProperty") + model.uuids(
        related_uuid=wellboreframe.uuid, obj_type="CategoricalProperty"
    )
    f_props = [rqp.Property(model, uuid=prop_uuid) for prop_uuid in property_uuids]

    # Get properties defined as WellLogs in a WellLogCollection
    wellboreframe.extract_log_collection()
    w_props = [log for log in wellboreframe.logs.iter_logs()] if wellboreframe.logs is not None else []

    # Convert these to Evo attributes
    attributes_go = convert_resqml_properties_to_evo_attributes(model, f_props + w_props, data_client)

    # Get the name of the well of the wellboreframe
    well_name = _get_well_name_for_wellboreframe(wellboreframe)

    # Get from-to data from intervals measured depths for this frame
    # Calculate intervals, and map to properties
    depths = wellboreframe.node_mds
    start_depths = depths[:-1]
    end_depths = depths[1:]
    mid_depths = (start_depths + end_depths) / 2

    intervals_df = pd.DataFrame(
        {
            "from": start_depths,  # Starts of each interval
            "to": end_depths,  # Ends of each interval
        }
    )
    schema = pa.schema([("from", pa.float64()), ("to", pa.float64())])
    table = pa.Table.from_pandas(intervals_df, schema=schema)
    float_array_args = data_client.save_table(table)
    from_to_interval_depths_go = FloatArray2.from_dict(float_array_args)
    intervals_from_to = IntervalTable_FromTo(
        intervals=Intervals(
            start_and_end=from_to_interval_depths_go,
        )
    )

    # Build locations: start, end, and points in-between
    start_locations = _get_depth_locations(start_depths, trajectory, data_client)
    end_locations = _get_depth_locations(end_depths, trajectory, data_client)
    mid_locations = _get_depth_locations(mid_depths, trajectory, data_client)

    # Get the EPSG code for the trajectory
    trajectory_epsg_code = None
    if epsg_code is not None:
        trajectory_epsg_code = epsg_code
    else:
        if trajectory.crs_uuid is not None:
            crs_traj = rqcrs.Crs(model, uuid=trajectory.crs_uuid)
            trajectory_epsg_code = int(crs_traj.epsg_code)

    return DownholeIntervals(
        name=prefix + well_name,
        is_composited=False,
        start=start_locations,
        end=end_locations,
        mid_points=mid_locations,
        from_to=intervals_from_to,
        hole_id=_build_hole_ids_for_wellbore_frame(wellboreframe, data_client),
        coordinate_reference_system=get_crs_epsg_code(model, trajectory_epsg_code),
        bounding_box=_build_boundingbox_from_trajectory(trajectory),
        attributes=attributes_go,
        uuid=None,
    )


def _get_well_name_for_wellboreframe(wellboreframe: rqw.WellboreFrame) -> str:
    """
    Get the Well name of a WellboreFrame
    :param wellboreframe: The resqpy WellboreFrame to get the name of.
    :returns: The name of the Well this frame is a part of
    """
    if wellboreframe.trajectory is not None:
        title: str = wellboreframe.trajectory.title
        return title
    elif wellboreframe.title:
        title = wellboreframe.title
        return title
    return "WellboreFrame-" + str(wellboreframe.uuid)


def _build_hole_ids_for_wellbore_frame(wellboreframe: rqw.WellboreFrame, data_client: ObjectDataClient) -> CategoryData:
    """
    Build a Hole IDs for the WellboreFrame. In our case we will be constructing
    a lookup table comprised of a single 'hole', and indexing all of our intervals
    to that.
    :param wellboreframe The WellboreFrame which the intervals are defined in
    :param data_client Evo data client
    :returns: Evo CategoryData instance
    """
    # Lookup table
    well_name = _get_well_name_for_wellboreframe(wellboreframe)
    lookup_df = pd.DataFrame({"key": [1], "value": [well_name]})
    schema = pa.schema([("key", pa.int64()), ("value", pa.string())])
    table = pa.Table.from_pandas(lookup_df, schema=schema)
    lookup_table_args = data_client.save_table(table)
    lookup_table_go = LookupTable.from_dict(lookup_table_args)

    # Data
    data_df = pd.DataFrame([1] * wellboreframe.node_count, columns=["data"])
    schema = pa.schema([("data", pa.int64())])
    table = pa.Table.from_pandas(data_df, schema=schema)
    int_array_args = data_client.save_table(table)
    int_array_go = IntegerArray1.from_dict(int_array_args)
    return CategoryData(
        table=lookup_table_go,
        values=int_array_go,
    )


def _get_depth_locations(
    depths: npt.NDArray[np.float_], trajectory: rqw.Trajectory, data_client: ObjectDataClient
) -> Locations:
    depth_xyzs = [
        trajectory.xyz_for_md(depths[i]) if trajectory.xyz_for_md(depths[i]) is not None else (np.NaN, np.NaN, np.NaN)
        for i in range(depths.size)
    ]
    df = pd.DataFrame(depth_xyzs, columns=["x", "y", "z"])
    schema = pa.schema([("x", pa.float64()), ("y", pa.float64()), ("z", pa.float64())])
    table = pa.Table.from_pandas(df, schema=schema)
    float_array_args = data_client.save_table(table)
    float_array_go = FloatArray3.from_dict(float_array_args)

    return Locations(coordinates=float_array_go)


def _build_boundingbox_from_trajectory(trajectory: rqw.Trajectory) -> BoundingBox:
    """
    Extract the bounding box from the Wellbore Trajectory
    :param trajectory: The resqpy Wellbore Trajectory object
    :return: The Evo BoundingBox for the trajectory
    """
    assert trajectory is not None
    # Get control point locations along the trajectory
    trajectory_df = trajectory.dataframe(md_col=None)
    min_coords = trajectory_df[["X", "Y", "Z"]].min().values
    max_coords = trajectory_df[["X", "Y", "Z"]].max().values
    x_min, y_min, z_min = min_coords
    x_max, y_max, z_max = max_coords

    return BoundingBox(min_x=x_min, min_y=y_min, min_z=z_min, max_x=x_max, max_y=y_max, max_z=z_max)
