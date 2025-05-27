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

from pathlib import Path

import pytest

from evo.data_converters.duf import is_duf, DufFileNotFoundException


def test_should_detect_duf_file_as_duf():
    duf_file = str((Path(__file__).parent.parent / "data" / "pit_mesh.duf").resolve())
    assert is_duf(duf_file)


def test_should_not_detect_non_duf_file_as_duf():
    duf_file = str((Path(__file__).parent.parent / "data" / "not_duf.duf").resolve())
    assert not is_duf(duf_file)


def test_should_raise_expected_exception_when_file_not_found():
    invalid_file_path = "invalid path"
    with pytest.raises(DufFileNotFoundException, match=invalid_file_path):
        is_duf(invalid_file_path)
