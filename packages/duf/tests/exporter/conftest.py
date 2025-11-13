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


@pytest.fixture(scope="session")
def polyline_attrs_boat_path():
    return str((Path(__file__).parent.parent / "data" / "polyline_attrs_boat.duf").resolve())


@pytest.fixture(scope="session")
def pit_mesh_attrs_path():
    return str((Path(__file__).parent.parent / "data" / "pit_mesh_attrs.duf").resolve())


@pytest.fixture(scope="function")
def test_out_path(tmp_path):
    return str(tmp_path / "test_out.duf")
