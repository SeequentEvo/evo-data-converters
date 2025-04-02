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

import json
import tempfile
from os import path
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

import requests
import requests_mock
from omf import VolumeElement, VolumeGridGeometry
from omf.data import DateTimeData, MappedData, ScalarData

from evo.data_converters.common import BlockSyncClient, EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.omf.exporter.blocksync_to_omf import blocksync_to_omf_element, export_blocksync_columns


class TestBlockSyncToOMF(TestCase):
    @patch("evo.data_converters.omf.exporter.blocksync_to_omf.export_blocksync_columns")
    def test_should_convert_blocksync_to_omf(self, mock_export_blocksync_columns: MagicMock) -> None:
        mock_export_blocksync_columns.return_value = []

        json_file = path.join(path.dirname(__file__), "data", "blockmodel.json")

        with open(json_file) as f:
            mock_data = json.load(f)

        mock_client = Mock(spec=BlockSyncClient)
        mock_response = Mock()
        mock_response.json.return_value = mock_data
        mock_client.get_blockmodel_request.return_value = mock_response

        blockmodel_uuid = "bca38684-831f-4350-9a3f-68705bb69e84"
        omf_volume = blocksync_to_omf_element(bm_uuid=blockmodel_uuid, client=mock_client)

        self.assertIsInstance(omf_volume, VolumeElement)

        self.assertIsInstance(omf_volume.geometry, VolumeGridGeometry)

        expected_origin = [296.5797985667433, 194.0760373454795, 81.20614758428184]
        self.assertListEqual(list(omf_volume.geometry.origin), expected_origin)

        expected_axis_u = [0.7712805763691759, -0.633718360861996, 0.059391174613884705]
        expected_axis_v = [0.613092022379597, 0.7146101771427565, -0.3368240888334652]
        expected_axis_w = [0.17101007166283433, 0.2961981327260238, 0.9396926207859084]

        self.assertListEqual(list(omf_volume.geometry.axis_u), expected_axis_u)
        self.assertListEqual(list(omf_volume.geometry.axis_v), expected_axis_v)
        self.assertListEqual(list(omf_volume.geometry.axis_w), expected_axis_w)

        expected_tensor_u = [10.0, 10.0, 10.0, 10.0]
        expected_tensor_v = [10.0, 10.0, 10.0]
        expected_tensor_w = [10.0, 10.0]

        self.assertListEqual(list(omf_volume.geometry.tensor_u), expected_tensor_u)
        self.assertListEqual(list(omf_volume.geometry.tensor_v), expected_tensor_v)
        self.assertListEqual(list(omf_volume.geometry.tensor_w), expected_tensor_w)

    @patch("os.unlink")
    def test_should_create_omf_elements(self, os_unlink: MagicMock) -> None:
        mock_client = Mock(spec=BlockSyncClient)
        mock_client.get_blockmodel_columns_job_url.return_value = "https://example.com/job-url"
        mock_client.get_blockmodel_columns_download_url.return_value = "https://example.com/download-url"
        mock_response = Mock()
        mock_response.json.return_value = {
            "count": 1,
            "limit": 50,
            "results": [{"version_id": 1, "version_uuid": "a71e5c2e-d1a7-43cf-95d4-a23a31ae8eb5"}],
        }
        mock_client.get_blockmodel_versions.return_value = mock_response
        download_file = path.join(path.dirname(__file__), "data", "sample_data.parquet")
        mock_client.download_parquet.return_value = download_file

        columns = export_blocksync_columns(bm_uuid="example", client=mock_client)

        self.assertIsInstance(columns[0], ScalarData)
        self.assertIsInstance(columns[3], DateTimeData)
        self.assertIsInstance(columns[5], MappedData)

        # Ensure the download file was deleted
        os_unlink.assert_called_once_with(download_file)


class TestBlockSyncClient(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.metadata = EvoWorkspaceMetadata(
            workspace_id="860be2f5-fe06-4c1b-ac8b-7d34d2b6d2ef",
            hub_url="mock://localhost",
            cache_root=self.cache_root_dir.name,
            org_id="bf1a040c-8c58-4bc2-bec2-c5ae7de8bd84",
        )
        service_client, _ = create_evo_object_service_and_data_client(evo_workspace_metadata=self.metadata)
        environment = service_client._environment
        api_connector = service_client._connector
        self.client = BlockSyncClient(environment, api_connector)

    @patch.object(BlockSyncClient, "get_auth_header")
    def test_should_get_blockmodel(self, mock_get_auth_header: MagicMock) -> None:
        mock_get_auth_header.return_value = {"Authorisation": "token"}

        with requests_mock.Mocker() as mock:
            test_blockmodel_id = "testdummy"
            blockmodel_req_url = f"{self.metadata.hub_url}/blockmodel/orgs/{self.metadata.org_id}/workspaces/{self.metadata.workspace_id}/block-models/{test_blockmodel_id}"
            blockmodel_response = {"bm_uuid": test_blockmodel_id}

            mock.register_uri(
                method="GET",
                url=blockmodel_req_url,
                json=blockmodel_response,
                status_code=200,
            )

            response = self.client.get_blockmodel_request(block_model_id=test_blockmodel_id)
            self.assertIsInstance(response, requests.Response)
            self.assertEqual(response.json()["bm_uuid"], blockmodel_response["bm_uuid"])

            self.assertEqual(mock.call_count, 1)

    @patch.object(BlockSyncClient, "get_auth_header")
    def test_should_get_blockmodel_versions(self, mock_get_auth_header: MagicMock) -> None:
        mock_get_auth_header.return_value = {"Authorisation": "token"}

        with requests_mock.Mocker() as mock:
            test_blockmodel_id = "testdummy"
            versions_req_url = f"{self.metadata.hub_url}/blockmodel/orgs/{self.metadata.org_id}/workspaces/{self.metadata.workspace_id}/block-models/{test_blockmodel_id}/versions"
            mock_versions_response = {"results": [1, 2, 3]}

            mock.register_uri(
                method="GET",
                url=versions_req_url,
                json=mock_versions_response,
                status_code=200,
            )

            response = self.client.get_blockmodel_versions(
                block_model_id=test_blockmodel_id, offset=0, filter_param="latest"
            )
            self.assertIsInstance(response, requests.Response)
            self.assertListEqual(response.json()["results"], mock_versions_response["results"])

            self.assertEqual(mock.call_count, 1)
            self.assertEqual(mock.last_request.query, "offset=0&filter=latest")

            response = self.client.get_blockmodel_versions(block_model_id=test_blockmodel_id, offset=50)
            self.assertEqual(mock.call_count, 2)
            self.assertEqual(mock.last_request.query, "offset=50")

    @patch.object(BlockSyncClient, "get_auth_header")
    def test_should_get_blockmodel_blocks_job_url(self, mock_get_auth_header: MagicMock) -> None:
        mock_get_auth_header.return_value = {"Authorisation": "token"}

        with requests_mock.Mocker() as mock:
            test_blockmodel_id = "testdummy"
            test_version_uuid = "test-version-uuid"
            blocks_job_url_req_url = f"{self.metadata.hub_url}/blockmodel/orgs/{self.metadata.org_id}/workspaces/{self.metadata.workspace_id}/block-models/{test_blockmodel_id}/blocks"
            blocks_job_url_response = {"job_url": "dummy_url"}

            mock.register_uri(
                method="POST",
                url=blocks_job_url_req_url,
                json=blocks_job_url_response,
                status_code=200,
            )

            job_url1 = self.client.get_blockmodel_columns_job_url(block_model_id=test_blockmodel_id)
            self.assertEqual(mock.call_count, 1)
            self.assertEqual(job_url1, blocks_job_url_response["job_url"])

            job_url2 = self.client.get_blockmodel_columns_job_url(
                block_model_id=test_blockmodel_id, version_uuid=test_version_uuid
            )
            expected_payload = '{"columns": ["*"], "geometry_columns": "indices", "version_uuid": "test-version-uuid"}'
            self.assertEqual(mock.call_count, 2)
            self.assertEqual(job_url2, blocks_job_url_response["job_url"])
            self.assertEqual(expected_payload, mock.last_request.text)
