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

import tempfile
from os import path
from pathlib import Path
from typing import Optional
from unittest import TestCase
from uuid import UUID

import numpy as np
import pandas as pd
import resqpy.crs as rqcrs
import resqpy.model as rq
import resqpy.property as rqp
import resqpy.property.property_common as rqp_c
import resqpy.well as rqw
from evo_schemas import DownholeIntervals_V1_1_0 as DownholeIntervals
from evo_schemas.components import (
    BoundingBox_V1_0_1 as BoundingBox,
)
from evo_schemas.components import (
    CategoryData_V1_0_1 as CategoryData,
)
from evo_schemas.components import (
    Locations_V1_0_1 as Locations,
)

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.resqml.importer._downhole_intervals_to_evo import (
    _build_boundingbox_from_trajectory,
    _build_hole_ids_for_wellbore_frame,
    _downhole_intervals_for_wellbore_frame,
    _get_depth_locations,
    _get_well_name_for_wellboreframe,
    convert_downhole_intervals_for_trajectory,
)
from evo.data_converters.resqml.importer.resqml_to_evo import _convert_downhole_intervals
from evo.data_converters.resqml.utils import get_crs_epsg_code


def add_wellbore_property(
    model: rq.Model,
    frame: rqw.WellboreFrame,
    values: list[float],
    prop_name: str,
    uom: Optional[str] = None,
    is_discrete: bool = False,
    string_lookup_uuid: Optional[UUID] = None,
) -> None:
    """
    Adds properties to the model directly related to the WellboreFrame. The default
    property type is continuous. For categorical properties set discrete=True,
    and string_lookup_uuid to a valid string lookup table UUID.
    """
    prop_array = np.array(values)

    rqp.Property.from_array(
        parent_model=model,
        cached_array=prop_array,
        source_info="interval data",
        keyword=prop_name,
        property_kind=prop_name,
        uom=uom,
        support_uuid=frame.uuid,
        indexable_element="nodes",
        discrete=is_discrete,
        string_lookup_uuid=string_lookup_uuid,
    ).create_xml()


def add_well_log(
    wlc: rqp.WellLogCollection,
    values: list[float],
    title: str,
    uom: Optional[str] = None,
    is_discrete: bool = False,
    string_lookup_uuid: Optional[UUID] = None,
) -> None:
    """
    Adds properties to the model as WellLogs in a WellLogCollection related to the
    WellboreFrame.
    """
    prop_array = np.array(values)

    property_kind, facet_type, facet = rqp_c.infer_property_kind(title, uom)

    wlc.add_cached_array_to_imported_list(
        cached_array=prop_array,
        source_info="interval data",
        keyword=title,
        property_kind=property_kind,
        uom=uom,
        indexable_element="nodes",
        discrete=is_discrete,
        string_lookup_uuid=string_lookup_uuid,
    )


class TestDownholeIntervals(TestCase):
    """
    Tests downhole_intervals_to_evo converter
    """

    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(metadata)
        self.data_client = data_client

        self.data_dir = tempfile.TemporaryDirectory()
        model_file = path.join(self.data_dir.name, "new_file.epc")
        self.model = rq.new_model(model_file)

        self.well_name = "Test Well #1"
        self.model_crs_epsg_code_int = 4326

        # Create a CRS
        self.crs = rqcrs.Crs(
            parent_model=self.model,
            epsg_code=str(self.model_crs_epsg_code_int),
            title=f"EPSG:{str(self.model_crs_epsg_code_int)}",
        )
        self.crs.create_xml()
        self.model.crs_uuid = self.crs.uuid

        # Add a Trajectory definition for the well.
        trajectory_df = pd.DataFrame(
            (
                (145.899994, 15051.129883, 8561.570312, 90.999992),
                (218.500000, 15051.081055, 8561.413086, 163.599762),
                (259.000000, 15050.992188, 8561.308594, 204.099487),
                (299.500000, 15050.823242, 8561.232422, 244.599030),
                (340.000000, 15050.803711, 8561.299805, 285.098663),
                (394.299988, 15050.877930, 8561.629883, 339.397522),
                (420.399994, 15050.846680, 8561.786133, 365.497040),
                (460.600006, 15050.901367, 8562.007812, 405.696381),
                (500.799988, 15051.045898, 8562.207031, 445.895599),
                (540.900024, 15052.113281, 8562.105469, 485.977386),
                (580.400024, 15054.400391, 8561.649414, 525.407959),
                (620.799988, 15057.659180, 8560.903320, 565.667603),
                (661.500000, 15062.120117, 8560.461914, 606.117188),
                (701.799988, 15067.651367, 8560.851562, 646.032104),
                (742.200012, 15074.749023, 8561.744141, 685.788574),
                (782.599976, 15082.649414, 8563.025391, 725.386841),
                (823.000000, 15090.331055, 8564.900391, 765.004150),
                (863.299988, 15097.926758, 8567.539062, 804.492676),
                (902.599976, 15104.895508, 8569.920898, 843.094116),
                (968.020020, 15115.603516, 8572.855469, 907.564209),
                (1008.500000, 15122.037109, 8574.555664, 947.493042),
                (1048.859985, 15128.499023, 8576.191406, 987.298340),
                (1083.000000, 15134.030273, 8577.557617, 1020.959351),
            ),
            columns=["MD", "X", "Y", "Z"],
        )

        # Establish an MdDatum object for the well and set it vertically
        # above the first trajectory control point.
        datum_xyz = trajectory_df["X"][0], trajectory_df["Y"][0], trajectory_df["Z"][0] - trajectory_df["MD"][0]
        self.md_datum = rqw.MdDatum(
            parent_model=self.model,
            crs_uuid=self.model.crs_uuid,  # handy if all your objects use the same crs
            location=datum_xyz,
            md_reference="ground level",
            title="spud datum",
        )
        self.md_datum.create_xml()

        # Create the well Trajectory
        self.trajectory = rqw.Trajectory(
            well_name=self.well_name,
            parent_model=self.model,
            md_datum=self.md_datum,
            data_frame=trajectory_df,
            length_uom="m",  # this is the md_uom
        )

        # Create the WellboreFeature and WellboreInterpretation objects
        self.trajectory.create_feature_and_interpretation()

        # Add the trajectory (and related objects) permanently to our model
        self.trajectory.write_hdf5()
        self.trajectory.create_xml()

        # A WellboreFrame is used as an entity to associate with downhole intervals
        # It follows the well trajectory but can define its own measured depths for
        # each set of downhole interval data. For testing, we are setting 5
        # arbitrary depths and will be adding 4 downhole interval properties.
        self.wellbore_frame = rqw.WellboreFrame(
            parent_model=self.model,
            trajectory=self.trajectory,
            mds=[420.8, 433.4, 505.5, 530.28, 610.18],
            title="Test wellbore measurements #1",
        )

        # Creates WellboreFeature, and WellboreInterpretation objects
        # related to the WellboreFrame and its Trajectory
        self.wellbore_frame.write_hdf5()
        self.wellbore_frame.create_xml()

        # Create the downhole interval data.
        # This is a mix of Categorical and Continuous properties.
        # Lookup table for some categorical lithology data
        lithology_lookup = rqp.StringLookup(
            self.model, title="lithology", int_to_str_dict={0: "Sandstone", 1: "Shale", 2: "Limestone"}
        )
        lithology_lookup.create_xml()

        # Create the intervals datasets
        interval_data: dict[str, list[float]] = {
            "porosity": [0.15, 0.18, 0.22, 0.20, 0.17],
            "temperature": [40, 60, 80, 90, 100],
            "formation_pressure": [1500, 2000, 2500, 3000, 3500],
            "lithology": [0, 1, 1, 2, 0],
        }

        # Adding interval properties directly to the WellboreFrame
        add_wellbore_property(
            model=self.model,
            frame=self.wellbore_frame,
            values=interval_data["porosity"],
            prop_name="porosity",
            uom="fraction",
        )
        add_wellbore_property(
            model=self.model,
            frame=self.wellbore_frame,
            values=interval_data["temperature"],
            prop_name="temperature",
            uom="F",
        )
        add_wellbore_property(
            model=self.model,
            frame=self.wellbore_frame,
            values=interval_data["formation_pressure"],
            prop_name="formation_pressure",
            uom="mPA",
        )
        add_wellbore_property(
            model=self.model,
            frame=self.wellbore_frame,
            values=interval_data["lithology"],
            prop_name="lithology",
            string_lookup_uuid=lithology_lookup.uuid,
            is_discrete=True,
        )

        # Adding interval properties to a WellLogCollection as WellLogs
        well_log_collection = rqp.WellLogCollection(self.wellbore_frame)
        add_well_log(wlc=well_log_collection, values=interval_data["porosity"], title="porosity2", uom="fraction")
        add_well_log(wlc=well_log_collection, values=interval_data["temperature"], title="temperature2", uom="degF")
        add_well_log(
            wlc=well_log_collection, values=interval_data["formation_pressure"], title="formation_pressure2", uom="psi"
        )
        add_well_log(
            wlc=well_log_collection,
            values=interval_data["lithology"],
            title="lithology2",
            uom="Euc",
            string_lookup_uuid=lithology_lookup.uuid,
            is_discrete=True,
        )
        well_log_collection.write_hdf5_for_imported_list()
        well_log_collection.create_xml_for_imported_list_and_add_parts_to_model()

        # Finalize the model and save it
        self.model.store_epc()
        self.model.h5_release()

    def tearDown(self) -> None:
        tempfile.TemporaryDirectory().cleanup()

    def check_data_is_valid(
        self, wellboreframe: rqw.WellboreFrame, trajectory: rqw.Trajectory, go_intervals: DownholeIntervals
    ) -> None:
        """
        Check that the data in the DownholeIntervals object matches the source RESQML data
        """
        self.assertEqual(
            go_intervals.hole_id,
            _build_hole_ids_for_wellbore_frame(wellboreframe, self.data_client),
        )
        for attribute in go_intervals.attributes:
            self.assertTrue(
                attribute.name
                in [
                    "porosity",
                    "temperature",
                    "formation_pressure",
                    "lithology",
                    "porosity2",
                    "temperature2",
                    "formation_pressure2",
                    "lithology2",
                ]
            )
        depths = wellboreframe.node_mds
        starts = depths[:-1]
        ends = depths[1:]
        mids = (starts + ends) / 2
        self.assertEqual(go_intervals.start, _get_depth_locations(starts, trajectory, self.data_client))
        self.assertEqual(go_intervals.end, _get_depth_locations(ends, trajectory, self.data_client))
        self.assertEqual(go_intervals.mid_points, _get_depth_locations(mids, trajectory, self.data_client))

    def test_build_boundingbox_from_trajectory(self) -> None:
        bounding_box = _build_boundingbox_from_trajectory(self.trajectory)
        self.assertIsInstance(bounding_box, BoundingBox)

    def test_get_well_name_for_wellboreframe(self) -> None:
        self.assertEqual(self.well_name, _get_well_name_for_wellboreframe(self.wellbore_frame))

    def test_get_depth_locations(self) -> None:
        depths = self.wellbore_frame.node_mds
        locations = _get_depth_locations(depths, self.trajectory, self.data_client)
        self.assertIsInstance(locations, Locations)

    def test_build_hole_ids(self) -> None:
        self.assertIsInstance(_build_hole_ids_for_wellbore_frame(self.wellbore_frame, self.data_client), CategoryData)

    def test_get_crs_epsg_code(self) -> None:
        crs_2193 = get_crs_epsg_code(self.model, 2193)
        self.assertEqual(crs_2193.epsg_code, 2193)
        self.assertEqual(get_crs_epsg_code(self.model).epsg_code, self.model_crs_epsg_code_int)

    def test_convert_downhole_intervals_to_evo(self) -> None:
        stem = Path(self.model.epc_file or "None").stem
        prefix1 = f"{stem}/downhole_intervals/1/"
        go_intervals_from_model = _convert_downhole_intervals(self.model, self.data_client)
        self.assertIsInstance(go_intervals_from_model[0], DownholeIntervals)
        go_intervals_from_trajectory = convert_downhole_intervals_for_trajectory(
            model=self.model, trajectory=self.trajectory, prefix=prefix1, data_client=self.data_client
        )
        go_intervals_from_wellbore_frame = _downhole_intervals_for_wellbore_frame(
            self.model, self.wellbore_frame, self.trajectory, prefix1, self.data_client
        )
        self.assertEqual(go_intervals_from_model[0], go_intervals_from_trajectory[0])
        self.assertEqual(go_intervals_from_wellbore_frame, go_intervals_from_trajectory[0])
        go_intervals = go_intervals_from_model[0]
        self.check_data_is_valid(self.wellbore_frame, self.trajectory, go_intervals)
