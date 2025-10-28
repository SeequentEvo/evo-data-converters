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
from unittest import TestCase

import pyarrow.parquet as pq
from evo_schemas.components import BoundingBox_V1_0_1
from evo_schemas.objects import Pointset_V1_2_0

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    crs_from_epsg_code,
)

from evo.data_converters.omf import OMFReaderContext
from evo.data_converters.omf.importer import convert_omf_pointset


class TestPointsetConverter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(metadata)
        self.data_client = data_client

    def test_should_convert_omf_pointset_to_geoscience_object(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/pointset_v2.omf")
        context = OMFReaderContext(omf_file)
        reader = context.reader()

        project, _ = reader.project()

        pointset = project.elements()[0]

        epsg_code = 32650
        pointset_go = convert_omf_pointset(
            pointset=pointset,
            project=project,
            reader=reader,
            data_client=self.data_client,
            epsg_code=epsg_code,
        )

        self.assertIsInstance(pointset_go, Pointset_V1_2_0)

        expected_pointset_go = Pointset_V1_2_0(
            name=pointset.name,
            uuid=None,
            coordinate_reference_system=crs_from_epsg_code(epsg_code),
            bounding_box=pointset_go.bounding_box,
            locations=pointset_go.locations,
        )

        self.assertEqual(pointset_go, expected_pointset_go)

        expected_bounding_box = BoundingBox_V1_0_1(
            min_x=444772.133711,
            max_x=445708.119805,
            min_y=492890.345953,
            max_y=494306.133144,
            min_z=2384.435887,
            max_z=3239.137023,
        )
        self.assertAlmostEqual(expected_bounding_box.min_x, pointset_go.bounding_box.min_x)
        self.assertAlmostEqual(expected_bounding_box.max_x, pointset_go.bounding_box.max_x)
        self.assertAlmostEqual(expected_bounding_box.min_y, pointset_go.bounding_box.min_y)
        self.assertAlmostEqual(expected_bounding_box.max_y, pointset_go.bounding_box.max_y)
        self.assertAlmostEqual(expected_bounding_box.min_z, pointset_go.bounding_box.min_z)
        self.assertAlmostEqual(expected_bounding_box.max_z, pointset_go.bounding_box.max_z)

        vertices_parquet_file = path.join(str(self.data_client.cache_location), pointset_go.locations.coordinates.data)

        vertices = pq.read_table(vertices_parquet_file)

        self.assertEqual(8332, len(vertices))
        self.assertAlmostEqual(vertices["x"][0].as_py(), 445198.861764)
        self.assertAlmostEqual(vertices["y"][0].as_py(), 494110.588392)
        self.assertAlmostEqual(vertices["z"][0].as_py(), 3052.607678)
