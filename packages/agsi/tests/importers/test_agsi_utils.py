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

import typing
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from evo.data_converters.common import crs_from_epsg_code
from evo.data_converters.agsi.importer.utils import get_geoscience_object_from_agsi
from evo.objects.utils.data import ObjectDataClient


@pytest.fixture
def mock_data_client() -> typing.Any:
    return MagicMock(spec=ObjectDataClient)


def test_get_geoscience_object_from_agsi_not_implemented(mock_data_client: MagicMock, v06_dir: Path) -> None:
    # Building the geological-sections object is implemented in a follow-up PR; the file is read first.
    with pytest.raises(NotImplementedError):
        get_geoscience_object_from_agsi(mock_data_client, str(v06_dir), crs_from_epsg_code(27700))
