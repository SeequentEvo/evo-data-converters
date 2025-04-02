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

from os import path
from unittest import TestCase

from evo.data_converters.omf import OmfReaderContext
from evo.data_converters.omf.importer.blockmodel.utils import convert_orient_to_angle


class TestConvertOrientToAngle(TestCase):
    def test_should_convert_orient_to_angle(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/rotated_block_model.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()
        orient = project.elements()[0].geometry().orient

        angles = convert_orient_to_angle([orient.u, orient.v, orient.w])
        expected_azimuth = 30
        expected_dip = 20
        expected_pitch = 10

        self.assertEqual(orient.u.shape, (3,))
        self.assertEqual(orient.v.shape, (3,))
        self.assertEqual(orient.w.shape, (3,))
        self.assertAlmostEqual(angles[0], expected_azimuth)
        self.assertAlmostEqual(angles[1], expected_dip)
        self.assertAlmostEqual(angles[2], expected_pitch)

    def test_should_convert_orient_to_angle_octree(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/bunny_blocks.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()
        orient = project.elements()[0].geometry().orient

        angles = convert_orient_to_angle([orient.u, orient.v, orient.w])
        # change to correct angles
        expected_azimuth = -10
        expected_dip = 0
        expected_pitch = 0

        self.assertAlmostEqual(angles[0], expected_azimuth)
        self.assertAlmostEqual(angles[1], expected_dip)
        self.assertAlmostEqual(angles[2], expected_pitch)
