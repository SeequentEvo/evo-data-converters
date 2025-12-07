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

from unittest.mock import patch
from uuid import UUID
from typing import Any

import pyarrow as pa

from evo.objects.parquet import ParquetLoader
from evo.common.test_tools import (
    TestWithConnector,
    TestWithStorage,
)

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
)


class EvoDataConvertersTestCase(TestWithConnector, TestWithStorage):
    def setUp(self) -> None:
        TestWithConnector.setUp(self)
        TestWithStorage.setUp(self)

        self.workspace_metadata = EvoWorkspaceMetadata(
            hub_url=self.environment.hub_url,
            org_id=str(self.environment.org_id),
            workspace_id=str(self.environment.workspace_id),
            cache_root=self.CACHE_DIR,
        )

        self.evo_client_patches = [
            patch(
                "evo.objects.utils.data.ObjectDataClient.download_table",
                side_effect=self._fake_data_client_download_table,
            )
        ]
        [p.start() for p in self.evo_client_patches]

    def tearDown(self) -> None:
        [p.stop() for p in self.evo_client_patches]

    async def _fake_data_client_download_table(
        self, object_id: UUID, version_id: str, table_info: dict, fb: Any = None
    ) -> pa.Table:
        """
        download_table() historically consulted the cache before downloading the parent object.
        This mock shortcuts the reference to the parent Geoscience Object to open the cached file only.
        """
        cache_path = self.cache.get_location(self.environment, "geoscience-object")
        parquet_file = cache_path / str(table_info["data"])
        assert parquet_file.exists(), f"Require pre-existence of {parquet_file}"
        with pa.OSFile(str(parquet_file), "r") as paf:
            with ParquetLoader(paf) as loader:
                return loader.load_as_table()
