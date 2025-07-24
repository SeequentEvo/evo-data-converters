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

from tempfile import NamedTemporaryFile, _TemporaryFileWrapper
from typing import Optional

import omf2

import evo.logging

logger = evo.logging.getLogger("data_converters")


class OMFReaderContext:
    """OMF Reader Context

    Reads an OMF v1 or v2 file and creates an omf2.Reader object which can be accessed via the reader() method.

    If an OMF v1 file is provided, it is automatically converted to a temporary v2 file.
    The temporary file is automatically deleted when this object is garbage collected.
    """

    def __init__(self, filepath: str):
        self._temp_file: Optional[_TemporaryFileWrapper] = None
        self._reader = self._load_omf_reader(filepath)

    def reader(self) -> omf2.Reader:
        return self._reader

    def temp_file(self) -> Optional[_TemporaryFileWrapper]:
        return self._temp_file

    def _load_omf_reader(self, filepath: str) -> omf2.Reader:
        """Attempts to load an omf2.Reader object for the given OMF file.

        :param filepath: Path to the OMF file.

        :raise omf2.OmfFileIoException: If the file does not exist.
        :raise omf2.OmfLimitExceededException: If the json_bytes limit is reached.
        """
        if omf2.detect_omf1(filepath):
            logger.debug(f"{filepath} detected as OMF v1, converting to a temporary v2 file.")
            self._temp_file = NamedTemporaryFile(mode="w+b", suffix=".omf")
            converter = omf2.Omf1Converter()
            converter = self._set_converter_limits(converter)
            converter.convert(filepath, self._temp_file.name)

            logger.debug(f"Converted {filepath} to OMFv2 using temporary file {self._temp_file.name}")
            filepath = self._temp_file.name

        logger.debug(f"Loading omf2.Reader with {filepath}")
        return omf2.Reader(filepath)

    def _set_converter_limits(self, converter: omf2.Omf1Converter) -> omf2.Omf1Converter:
        """
        Increase JSON bytes minimum limit if needed, which allows for opening a wider variety of OMF1 files.
        """
        limits = converter.limits()
        json_bytes_minimum = 100 * 1024 * 1024  # 100mb

        if limits.json_bytes and limits.json_bytes > json_bytes_minimum:
            return converter

        limits.json_bytes = json_bytes_minimum
        converter.set_limits(limits)
        return converter
