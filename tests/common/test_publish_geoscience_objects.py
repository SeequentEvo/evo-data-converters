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

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from evo.data_converters.common.publish import publish_geoscience_object, publish_geoscience_objects


class TestPublishGeoscienceObjects(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_object_service_client = Mock()
        self.mock_data_client = Mock()

        self.test_object = Mock()
        self.test_object.as_dict.return_value = {"test": "data"}
        self.test_objects = [self.test_object, self.test_object]

    @patch("evo.data_converters.common.publish.publish_geoscience_object")
    @patch("evo.data_converters.common.publish.generate_paths")
    def test_publish_geoscience_objects(
        self, mock_generate_paths: MagicMock, mock_publish_geoscience_object: AsyncMock
    ) -> None:
        expected_metadata = Mock()
        mock_publish_geoscience_object.return_value = expected_metadata
        mock_generate_paths.return_value = ["test/mock_1.json", "test/mock_2.json"]

        objects_metadata = publish_geoscience_objects(
            object_models=self.test_objects,
            object_service_client=self.mock_object_service_client,
            data_client=self.mock_data_client,
            path_prefix="test",
        )

        self.assertEqual(len(objects_metadata), 2)
        self.assertEqual(objects_metadata, [expected_metadata, expected_metadata])

        self.assertEqual(mock_generate_paths.call_count, 1)
        self.assertEqual(mock_publish_geoscience_object.call_count, 2)

        mock_publish_geoscience_object.assert_has_calls(
            [
                call("test/mock_1.json", self.test_object, self.mock_object_service_client, self.mock_data_client),
                call("test/mock_2.json", self.test_object, self.mock_object_service_client, self.mock_data_client),
            ]
        )

    @patch("evo.data_converters.common.publish.publish_geoscience_object")
    def test_publish_geoscience_objects_empty_list(self, mock_publish_geoscience_object: AsyncMock) -> None:
        objects_metadata = publish_geoscience_objects([], self.mock_object_service_client, self.mock_data_client)

        self.assertEqual(objects_metadata, [])
        mock_publish_geoscience_object.assert_not_called()

    async def test_publish_geoscience_object(self) -> None:
        object_path = "test/object_1.json"
        expected_metadata = Mock()

        self.mock_data_client.upload_referenced_data = AsyncMock()
        self.mock_object_service_client.create_geoscience_object = AsyncMock(return_value=expected_metadata)

        object_metadata = await publish_geoscience_object(
            path=object_path,
            object_model=self.test_object,
            object_service_client=self.mock_object_service_client,
            data_client=self.mock_data_client,
        )

        assert object_metadata == expected_metadata

        self.mock_data_client.upload_referenced_data.assert_awaited_once_with(self.test_object.as_dict())
        self.mock_object_service_client.create_geoscience_object.assert_awaited_once_with(
            object_path, self.test_object.as_dict()
        )
