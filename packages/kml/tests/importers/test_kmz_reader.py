#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from pathlib import Path

import pytest

from evo.data_converters.kml.importer.exceptions import InvalidKMLError
from evo.data_converters.kml.importer.implementation.kml_or_kmz_reader import KmlOrKmzReader

this_dir = Path(__file__).resolve().parent.parent / "data"

def test_read_kmz_file() -> None:
    # Read a valid .kmz sample and verify that the reader extracts the embedded KML and returns a <kml> root element.
    source = KmlOrKmzReader(this_dir / "KML_Test.kmz").read()

    assert source.source_format == "kmz"
    assert source.root.tag.endswith("kml")

def test_kmz_reader_rejects_missing_file() -> None:
    # A missing .kmz file should raise nvalidKMLError instead of a raw filesystem or archive exception.
    with pytest.raises(InvalidKMLError, match="Could not read KML/KMZ file"):
        KmlOrKmzReader(this_dir / "missing.kmz").read()