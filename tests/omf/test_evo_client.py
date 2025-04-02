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

import tempfile
from unittest import TestCase

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.objects import ObjectAPIClient
from evo.objects.utils.data import ObjectDataClient


class TestEvoClient(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()

    def test_should_create_objects_with_minimal_metadata(self) -> None:
        metadata = EvoWorkspaceMetadata(cache_root=self.cache_root_dir.name)
        object_service_client, data_client = create_evo_object_service_and_data_client(metadata)

        self.assertIsInstance(object_service_client, ObjectAPIClient)
        self.assertIsInstance(data_client, ObjectDataClient)

    def test_should_create_objects_with_detailed_metadata(self) -> None:
        metadata = EvoWorkspaceMetadata(
            hub_url="https://example.com",
            org_id="8ac3f041-b186-41f9-84ba-43d60f8683be",  # randomly generated
            workspace_id="2cf1697f-2771-485e-848d-e6674d2ac63f",  # randomly generated
            cache_root=self.cache_root_dir.name,
        )
        object_service_client, data_client = create_evo_object_service_and_data_client(metadata)

        self.assertIsInstance(object_service_client, ObjectAPIClient)
        self.assertIsInstance(data_client, ObjectDataClient)
