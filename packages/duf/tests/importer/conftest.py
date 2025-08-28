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

from evo.data_converters.duf import DUFCollectorContext


@pytest.fixture(scope="session")
def simple_objects_path():
    return str((Path(__file__).parent.parent / "data" / "simple_objects.duf").resolve())


@pytest.fixture(scope="session")
def simple_objects(simple_objects_path):
    with DUFCollectorContext(simple_objects_path) as context:
        yield context.collector
