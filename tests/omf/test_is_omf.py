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

from omf2 import OmfFileIoException

from evo.data_converters.omf import is_omf


class TestIsOmf(TestCase):
    def test_should_detect_omf1_file_as_omf(self) -> None:
        omf1_file = path.join(path.dirname(__file__), "data/omf1.omf")
        self.assertTrue(is_omf(omf1_file))

    def test_should_detect_omf2_file_as_omf(self) -> None:
        omf2_file = path.join(path.dirname(__file__), "data/omf2.omf")
        self.assertTrue(is_omf(omf2_file))

    def test_should_not_detect_non_omf_file_as_omf(self) -> None:
        non_omf_file = path.join(path.dirname(__file__), "data/empty_zip_file.omf")
        self.assertFalse(is_omf(non_omf_file))

    def test_should_raise_expected_exception_when_file_not_found(self) -> None:
        invalid_file_path = "invalid path"
        with self.assertRaises(OmfFileIoException) as context:
            is_omf(invalid_file_path)

        self.assertIn("File IO error:", str(context.exception))
        self.assertIn("(os error 2)", str(context.exception))
