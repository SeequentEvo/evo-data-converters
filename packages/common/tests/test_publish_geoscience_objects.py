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

from evo.common.exceptions import NotFoundException
from evo.data_converters.common.publish import publish_geoscience_object, publish_geoscience_objects_sync


class TestPublishGeoscienceObjects(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.mock_object_service_client = Mock()
        self.mock_data_client = Mock()

        self.test_object = Mock()
        self.test_object.as_dict.return_value = {"test": "data"}
        self.test_object.uuid = None  # Initialize uuid attribute
        self.test_objects = [self.test_object, self.test_object]

    @patch("evo.data_converters.common.publish.publish_geoscience_object")
    @patch("evo.data_converters.common.publish.generate_paths")
    def test_publish_geoscience_objects(
        self, mock_generate_paths: MagicMock, mock_publish_geoscience_object: AsyncMock
    ) -> None:
        expected_metadata = Mock()
        mock_publish_geoscience_object.return_value = expected_metadata
        mock_generate_paths.return_value = ["test/mock_1.json", "test/mock_2.json"]

        objects_metadata = publish_geoscience_objects_sync(
            object_models=self.test_objects,
            object_service_client=self.mock_object_service_client,
            data_client=self.mock_data_client,
            path_prefix="test",
            overwrite_existing_objects=False,
        )

        self.assertEqual(len(objects_metadata), 2)
        self.assertEqual(objects_metadata, [expected_metadata, expected_metadata])

        self.assertEqual(mock_generate_paths.call_count, 1)
        self.assertEqual(mock_publish_geoscience_object.call_count, 2)

        mock_publish_geoscience_object.assert_has_calls(
            [
                call(
                    "test/mock_1.json", self.test_object, self.mock_object_service_client, self.mock_data_client, False
                ),
                call(
                    "test/mock_2.json", self.test_object, self.mock_object_service_client, self.mock_data_client, False
                ),
            ]
        )

    @patch("evo.data_converters.common.publish.publish_geoscience_object")
    def test_publish_geoscience_objects_empty_list(self, mock_publish_geoscience_object: AsyncMock) -> None:
        objects_metadata = publish_geoscience_objects_sync([], self.mock_object_service_client, self.mock_data_client)

        self.assertEqual(objects_metadata, [])
        mock_publish_geoscience_object.assert_not_called()

    async def test_publish_geoscience_object_creates_new_object(self) -> None:
        """Test publishing when object doesn't exist (404 NotFound)"""
        object_path = "test/object_1.json"
        expected_metadata = Mock()

        # Reset uuid to None
        self.test_object.uuid = None

        self.mock_data_client.upload_referenced_data = AsyncMock()
        self.mock_object_service_client.create_geoscience_object = AsyncMock(return_value=expected_metadata)
        self.mock_object_service_client.download_object_by_path = AsyncMock(
            side_effect=NotFoundException(404, "Not found", None, None)
        )

        object_metadata = await publish_geoscience_object(
            path=object_path,
            object_model=self.test_object,
            object_service_client=self.mock_object_service_client,
            data_client=self.mock_data_client,
            overwrite_existing_object=False,
        )

        assert object_metadata == expected_metadata

        # Verify the correct methods were called
        self.mock_object_service_client.download_object_by_path.assert_awaited_once_with(object_path)
        self.mock_data_client.upload_referenced_data.assert_awaited_once_with(self.test_object.as_dict())
        self.mock_object_service_client.create_geoscience_object.assert_awaited_once_with(
            object_path, self.test_object.as_dict()
        )

        # Ensure uuid was not set (should still be None)
        assert self.test_object.uuid is None

    async def test_publish_geoscience_object_updates_existing_object(self) -> None:
        """Test publishing when object exists and overwrite_existing_object is True"""
        object_path = "test/object_1.json"
        expected_metadata = Mock()
        existing_uuid = "existing-uuid-123"

        self.test_object.uuid = None

        existing_object = Mock()
        existing_object.metadata.id = existing_uuid

        self.mock_data_client.upload_referenced_data = AsyncMock()
        self.mock_object_service_client.update_geoscience_object = AsyncMock(return_value=expected_metadata)
        self.mock_object_service_client.download_object_by_path = AsyncMock(return_value=existing_object)

        object_metadata = await publish_geoscience_object(
            path=object_path,
            object_model=self.test_object,
            object_service_client=self.mock_object_service_client,
            data_client=self.mock_data_client,
            overwrite_existing_object=True,
        )

        assert object_metadata == expected_metadata

        self.mock_object_service_client.download_object_by_path.assert_awaited_once_with(object_path)

        assert self.test_object.uuid == existing_uuid

        self.mock_data_client.upload_referenced_data.assert_awaited_once_with(self.test_object.as_dict())
        self.mock_object_service_client.update_geoscience_object.assert_awaited_once_with(self.test_object.as_dict())

        self.mock_object_service_client.create_geoscience_object.assert_not_called()
