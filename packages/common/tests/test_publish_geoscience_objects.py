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

import asyncio
import json
import sys
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from evo.common import APIConnector
from evo.common.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    StorageFileNotFoundError,
)
from evo.common.test_tools import MockResponse
from evo.data_converters.common.publish import (
    publish_geoscience_object,
    publish_geoscience_objects,
)
from evo.objects.exceptions import InvalidGeoscienceObjectError


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
    async def test_publish_geoscience_objects(
        self, mock_generate_paths: MagicMock, mock_publish_geoscience_object: AsyncMock
    ) -> None:
        expected_metadata = Mock()
        mock_publish_geoscience_object.return_value = expected_metadata
        mock_generate_paths.return_value = ["test/mock_1.json", "test/mock_2.json"]

        objects_metadata = await publish_geoscience_objects(
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
    async def test_publish_geoscience_objects_empty_list(self, mock_publish_geoscience_object: AsyncMock) -> None:
        objects_metadata = await publish_geoscience_objects([], self.mock_object_service_client, self.mock_data_client)

        self.assertEqual(objects_metadata, [])
        mock_publish_geoscience_object.assert_not_called()

    @patch("evo.data_converters.common.publish.publish_geoscience_object")
    @patch("evo.data_converters.common.publish.generate_paths")
    async def test_async_publish_geoscience_objects_concurrently(
        self, mock_generate_paths: MagicMock, mock_publish_geoscience_object: AsyncMock
    ) -> None:
        both_started = asyncio.Event()
        release = asyncio.Event()
        started = 0
        expected_metadata = [Mock(), Mock()]

        async def publish(*args: object) -> Mock:
            nonlocal started
            result = expected_metadata[started]
            started += 1
            if started == len(self.test_objects):
                both_started.set()
            await release.wait()
            return result

        mock_generate_paths.return_value = ["test/mock_1.json", "test/mock_2.json"]
        mock_publish_geoscience_object.side_effect = publish

        publish_task = asyncio.create_task(
            publish_geoscience_objects(
                self.test_objects, self.mock_object_service_client, self.mock_data_client, path_prefix="test"
            )
        )
        await asyncio.wait_for(both_started.wait(), timeout=1)
        release.set()

        self.assertEqual(await publish_task, expected_metadata)

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

    def _get_context(self, exc: BaseException, logs: Any) -> str:
        if sys.version_info >= (3, 11):
            return "\n".join(getattr(exc, "__notes__", []))
        return "\n".join(logs.output)

    async def _publish_expecting_error(self, error: Exception, overwrite: bool = False) -> str:
        self.test_object.name = "collection1"
        self.test_object.schema = "/objects/downhole-collection/1.3.1/downhole-collection.schema.json"
        with (
            self.assertLogs("evo.data_converters", level="DEBUG") as logs,
            self.assertRaises(type(error)) as cm,
        ):
            await publish_geoscience_object(
                path="test/object_1.json",
                object_model=self.test_object,
                object_service_client=self.mock_object_service_client,
                data_client=self.mock_data_client,
                overwrite_existing_object=overwrite,
            )
        self.assertIs(error, cm.exception)
        return self._get_context(cm.exception, logs)

    def _mock_new_object(self) -> None:
        self.mock_object_service_client.download_object_by_path = AsyncMock(
            side_effect=NotFoundException(404, "Not found", None, None)
        )
        self.mock_data_client.upload_referenced_data = AsyncMock()

    async def test_publish_geoscience_object_existence_check_failure_adds_context(self) -> None:
        error = ForbiddenException(403, "Forbidden", None, None)
        self.mock_object_service_client.download_object_by_path = AsyncMock(side_effect=error)

        context = await self._publish_expecting_error(error)

        self.assertIn("While checking whether geoscience object 'collection1'", context)
        self.assertIn("at path 'test/object_1.json' already exists", context)

    async def test_publish_geoscience_object_upload_failure_adds_context(self) -> None:
        error = StorageFileNotFoundError("missing")
        self._mock_new_object()
        self.mock_data_client.upload_referenced_data = AsyncMock(side_effect=error)

        context = await self._publish_expecting_error(error)

        self.assertIn("While uploading data referenced by geoscience object 'collection1'", context)
        self.mock_object_service_client.create_geoscience_object.assert_not_called()

    async def test_publish_context_preserves_existing_sdk_context(self) -> None:
        error = ConnectionError("Storage unavailable")
        sdk_context = "While uploading referenced data 'example-hash'"
        if hasattr(error, "add_note"):
            error.add_note(sdk_context)
        self._mock_new_object()
        self.mock_data_client.upload_referenced_data = AsyncMock(side_effect=error)

        context = await self._publish_expecting_error(error)

        self.assertIn("While uploading data referenced by geoscience object 'collection1'", context)
        if sys.version_info >= (3, 11):
            self.assertIn(sdk_context, context)
            self.assertEqual(2, len(getattr(error, "__notes__", [])))
        self.assertEqual("Storage unavailable", str(error))

    async def test_publish_geoscience_object_create_failure_adds_context(self) -> None:
        error = BadRequestException(400, "Bad Request", {"title": "The Geoscience Object Is Invalid."}, None)
        self._mock_new_object()
        self.mock_object_service_client.create_geoscience_object = AsyncMock(side_effect=error)

        context = await self._publish_expecting_error(error)

        self.assertIn(
            "While creating geoscience object 'collection1' "
            "(schema: /objects/downhole-collection/1.3.1/downhole-collection.schema.json) "
            "at path 'test/object_1.json'",
            context,
        )

    async def test_publish_geoscience_object_update_failure_adds_context(self) -> None:
        error = BadRequestException(400, "Bad Request", {"title": "The Geoscience Object Is Invalid."}, None)
        existing_object = Mock()
        existing_object.metadata.id = "existing-uuid-123"
        self.mock_object_service_client.download_object_by_path = AsyncMock(return_value=existing_object)
        self.mock_data_client.upload_referenced_data = AsyncMock()
        self.mock_object_service_client.update_geoscience_object = AsyncMock(side_effect=error)

        context = await self._publish_expecting_error(error, overwrite=True)

        self.assertIn("While updating existing geoscience object 'collection1'", context)
        self.assertIn("(uuid: existing-uuid-123)", context)

    async def test_publish_preserves_sdk_validation_diagnostics(self) -> None:
        detail = f"{'x' * 1000} is not valid under any of the given schemas"
        content = {
            "type": "https://seequent.com/error-codes/geoscienceobject/schemas/invalid-object",
            "title": "The Geoscience Object Is Invalid.",
            "detail": detail,
            "json_path": "$.collections[0]",
            "schema_path": ["properties", "collections", "oneOf"],
        }
        response = MockResponse(status_code=400, reason="Bad Request", content=json.dumps(content))
        self.test_object.name = "collection1"
        self.test_object.schema = "/objects/downhole-collection/1.3.1/downhole-collection.schema.json"
        self._mock_new_object()

        async def reject_object(*args: object) -> None:
            APIConnector._deserialize(response, BadRequestException)

        self.mock_object_service_client.create_geoscience_object = AsyncMock(side_effect=reject_object)
        with (
            self.assertLogs("evo.data_converters", level="DEBUG") as logs,
            self.assertRaises(InvalidGeoscienceObjectError) as cm,
        ):
            await publish_geoscience_object(
                path="test/object_1.json",
                object_model=self.test_object,
                object_service_client=self.mock_object_service_client,
                data_client=self.mock_data_client,
            )

        error = cm.exception
        self.assertIsInstance(error, BadRequestException)
        self.assertEqual(detail, error.detail)
        self.assertIn("Invalid value at: $.collections[0]", str(error))
        self.assertIn("Failed schema rule:", str(error))
        self.assertIn("[omitted]", str(error))
        self.assertIn("print(exc.detail)", str(error))
        self.assertIn("While creating geoscience object 'collection1'", self._get_context(error, logs))

    async def test_publish_logs_context_when_exception_notes_are_unavailable(self) -> None:
        class LegacyError(Exception):
            def __getattribute__(self, name: str) -> Any:
                if name == "add_note":
                    raise AttributeError(name)
                return super().__getattribute__(name)

        error = LegacyError("Storage unavailable")
        self._mock_new_object()
        self.mock_data_client.upload_referenced_data = AsyncMock(side_effect=error)

        with (
            patch("evo.data_converters.common.publish.logger") as logger,
            self.assertRaises(LegacyError) as cm,
        ):
            await publish_geoscience_object(
                path="test/object_1.json",
                object_model=self.test_object,
                object_service_client=self.mock_object_service_client,
                data_client=self.mock_data_client,
            )
        self.assertIs(error, cm.exception)
        logger.error.assert_called_once()
        self.assertIn("While uploading data referenced by geoscience object", logger.error.call_args.args[0])
