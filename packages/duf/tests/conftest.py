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

import os
from os import path


import pyarrow.parquet as pq
import pytest

from evo.data_converters.common import (
    create_evo_object_service_and_data_client,
    EvoWorkspaceMetadata,
)


@pytest.fixture(scope="session")
def evo_metadata(tmp_path_factory):
    cache_root_dir = tmp_path_factory.mktemp("temp", numbered=False)
    return EvoWorkspaceMetadata(
        workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae",
        cache_root=cache_root_dir.name,
    )


class TestDataClient:
    def __init__(self, data_client):
        self.data_client = data_client

    def __getattr__(self, name):
        return getattr(self.data_client, name)

    def load_table(self, table):
        chunks_parquet_file = path.join(str(self.data_client.cache_location), table.data)
        return pq.read_table(chunks_parquet_file)


@pytest.fixture(scope="session")
def data_client(evo_metadata) -> TestDataClient:
    _, data_client = create_evo_object_service_and_data_client(evo_metadata)
    return TestDataClient(data_client)


@pytest.fixture(autouse=True, scope="function")
def cleanup():
    test_dir = os.path.dirname(__file__)
    files_to_clean = [
        # TODO Getting permission error when trying to clean these
        # os.path.join(test_dir, 'importer', 'temp'),
        # os.path.join(test_dir, 'exporter', 'temp'),
        os.path.join(test_dir, "exporter", "test_out.duf"),
    ]

    yield
    for filepath in files_to_clean:
        if os.path.exists(filepath):
            os.remove(filepath)
