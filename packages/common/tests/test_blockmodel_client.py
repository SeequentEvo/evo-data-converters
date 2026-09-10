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

import threading
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from evo.data_converters.common.blockmodel_client import BlockSyncClient


class TestBlockSyncClient(IsolatedAsyncioTestCase):
    async def test_get_auth_header_from_running_event_loop(self) -> None:
        environment = Mock(hub_url="https://example.com", org_id="org", workspace_id="workspace")
        authorizer = Mock()
        caller_thread_id = threading.get_ident()

        async def get_default_headers() -> dict[str, str]:
            self.assertNotEqual(threading.get_ident(), caller_thread_id)
            return {"Authorization": "Bearer token"}

        authorizer.get_default_headers = AsyncMock(side_effect=get_default_headers)
        api_connector = Mock(_authorizer=authorizer)
        client = BlockSyncClient(environment, api_connector)

        headers = client.get_auth_header()

        self.assertEqual(headers["Authorization"], "Bearer token")
        self.assertEqual(headers["API-Preview"], "opt-in")