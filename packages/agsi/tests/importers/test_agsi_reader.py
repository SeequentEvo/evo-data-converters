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

from evo.data_converters.agsi.importer.agsi_reader import (
    AGSIDataFileIOError,
    AGSIInvalidDataError,
    read_agsi_file,
)
from evo.data_converters.agsi.reader import AgsiPackage


def test_read_agsi_file(v06_zip: Path) -> None:
    package = read_agsi_file(str(v06_zip))
    assert isinstance(package, AgsiPackage)
    assert package.source_version == "0.6"
    assert len(package.models[0].agsi_model_element) == 2


def test_read_agsi_file_missing() -> None:
    with pytest.raises(AGSIDataFileIOError):
        read_agsi_file("dummy_file.txt")


def test_read_agsi_file_invalid(tmp_path: Path) -> None:
    path = tmp_path / "not-agsi.json"
    path.write_text("[]")
    with pytest.raises(AGSIInvalidDataError):
        read_agsi_file(str(path))
