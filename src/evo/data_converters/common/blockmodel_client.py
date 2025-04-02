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
import tempfile
import time
from http import HTTPStatus
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import pyarrow as pa
import pyarrow.parquet as pq
import requests

import evo.logging
from evo.common import APIConnector, Environment, HTTPHeaderDict
from evo.data_converters.common.exceptions import ResponseError

logger = evo.logging.getLogger("data_converters")


class BlockSyncClient:
    def __init__(self, environment: Environment, api_connector: APIConnector):
        self.environment = environment
        self.api_connector = api_connector
        self.hub_url = self.environment.hub_url
        self.org_id = self.environment.org_id
        self.workspace_id = self.environment.workspace_id

    def get_auth_header(self) -> HTTPHeaderDict:
        """Get the authorisation header for all Block Model API requests.

        :return: The authorisation headers in dictionary form.
        """
        header_dict: HTTPHeaderDict = asyncio.run(self.api_connector._authorizer.get_default_headers())
        header_dict["API-Preview"] = "opt-in"  # This must be set in the headers to support CRS
        return header_dict

    def check_job_status(self, job_url: str, max_retries: int = 200, retry_delay: int = 1) -> requests.Response:
        """Check the status of a job by making HTTP GET requests to the job URL.

        :param job_url: The URL of the job.
        :param max_retries: (optional) The maximum number of retries. Defaults to 200.
        :param retry_delay: (optional) The delay between retries in seconds. Defaults to 1.

        :return: The response object of the last request if the job succeeded.

        Raises an exception if the job failed.
        """
        retry_count = 0
        has_succeeded = False
        auth_header = self.get_auth_header()

        while retry_count < max_retries:
            response = requests.get(job_url, headers=auth_header)
            response_output = json.dumps(response.json(), indent=4, sort_keys=True)
            logger.info(response_output)

            if response.status_code == HTTPStatus.OK:
                if response.json()["job_status"] == "COMPLETE":
                    logger.info("Job completed successfully!")
                    has_succeeded = True
                    break
                elif response.json()["job_status"] == "FAILED":
                    logger.warning("Job failed!")
                    break
                else:
                    logger.info("Job still in progress...")
                    time.sleep(retry_delay)
                    retry_count += 1

        if not has_succeeded:
            raise ResponseError(f"Job failed: \n Status: {response.status_code} \n Response: {response_output}")
        else:
            return response

    def create_request(self, body: dict) -> str:
        """Sends a create API request to the Block Model API.
        It creates an empty block model which is defined by the body param.

        :param body: The body of the API request which contains information about the model.

        :return: The newly created block model's ID.

        If problems are encountered while accessing the API, these will be raised as exceptions.
        """
        # Compose the URL
        url = f"{self.hub_url}/blockmodel/orgs/{self.org_id}/workspaces/{self.workspace_id}/block-models"

        # Make a POST request and include the JSON body and headers
        auth_header = self.get_auth_header()
        response = requests.post(url=url, json=body, headers=auth_header)

        if response.status_code != HTTPStatus.CREATED:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        response_output = json.dumps(response.json(), indent=4, sort_keys=True)
        response_dict = json.loads(response_output)
        self.check_job_status(job_url=response_dict["job_url"], max_retries=200, retry_delay=1)
        logger.info(f"Success, {body['name']} was created.")
        logger.info("Job url: ", response_dict["job_url"])

        bm_uuid: str = response_dict["bm_uuid"]
        return bm_uuid

    def add_columns_request(self, block_model_id: str, body: dict) -> tuple[str, str]:
        """Sends an update columns API request to the Block Model API.

        It updates a block model with the new columns as per the body param.

        :param block_model_id: The id of the block model to be added to.
        :param body: The body of the API request which contains information about the model.

        :return: The URL of the block model job to add columns, and the URL where the column
        data will be uploaded to.

        If problems are encountered while accessing the API, these will be raised as exceptions.
        """
        # Compose the URL and JSON body
        url = f"{self.hub_url}/blockmodel/orgs/{self.org_id}/workspaces/{self.workspace_id}/block-models/{block_model_id}/blocks"

        # This PATCH request prepares the BlockSync API for data upload
        auth_header = self.get_auth_header()
        response = requests.patch(url=url, json=body, headers=auth_header)

        if response.status_code != HTTPStatus.ACCEPTED:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        response_output = json.dumps(response.json(), indent=4, sort_keys=True)
        response_dict: dict[str, str] = json.loads(response_output)

        job_url: str = response_dict["job_url"]
        upload_url: str = response_dict["upload_url"]

        return job_url, upload_url

    def get_blockmodel_request(self, block_model_id: str) -> requests.Response:
        """Get the BlockModel with ID block_model_id in the current workspace.

        On success, the API will respond with HTTP status code 200 OK along with the BlockModel object in the response body.

        If the BlockModel has been soft-deleted and the query parameter deleted=true has not been provided, the API will respond with status code 410 Gone.

        :param block_model_id: The id of the block model to be retrieved.

        :raises Exception: If there is a problem with the request.
        """
        # Compose the URL and JSON body
        url = (
            f"{self.hub_url}/blockmodel/orgs/{self.org_id}/workspaces/{self.workspace_id}/block-models/{block_model_id}"
        )

        # Make a GET request and include the auth headers
        auth_header = self.get_auth_header()
        logger.info(f"Requesting blockmodel from {url}")
        response = requests.get(url=url, headers=auth_header)

        if response.status_code != HTTPStatus.OK:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        return response

    def complete_blockmodel_upload(self, job_url: str) -> None:
        """Send a POST request to notify the BlockSync API that no more data will be uploaded.

        This will move the job from queued to in progress.

        :param job_url: The job URL to move up the queue.
        """
        auth_header = self.get_auth_header()
        url = f"{job_url}/uploaded"

        # Make a POST request, including the headers
        response = requests.post(url=url, headers=auth_header)
        if response.status_code != HTTPStatus.CREATED:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        response_output = json.dumps(response.json(), indent=4, sort_keys=True)
        response_dict = json.loads(response_output)

        # Check if job completed
        self.check_job_status(job_url=response_dict["job_url"], max_retries=200, retry_delay=1)
        logger.info(f"Job {job_url} complete")

    def upload_parquet(self, upload_url: str, table: pa.Table) -> None:
        """Sends a put request containing a parquet file to the Block Model API.

        :param upload_url: The URL to upload the parquet file data to.
        :param table: The block model data in table form.

        If problems are encountered while accessing the API, these will be raised as exceptions.
        """
        # Compose the headers
        # NOTE: The Seequent ID access token is not required for this request
        headers = {"Content-Type": "application/binary", "x-ms-blob-type": "BlockBlob"}

        # Create a temporary parquet file to upload to BlockSync
        with tempfile.TemporaryDirectory() as tempdirname:
            temp_dir = Path(tempdirname)
            file_name = temp_dir / "upload_file.parquet"
            pq.write_table(table=table, where=file_name)
            # Make a PUT request - include the binary data and headers
            with open(file_name, "rb") as data_stream:
                response = requests.put(url=upload_url, data=data_stream, headers=headers)

        if response.status_code != HTTPStatus.CREATED:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

    def get_blockmodel_versions(
        self, block_model_id: str, offset: int = 0, filter_param: Optional[str] = None
    ) -> requests.Response:
        auth_header = self.get_auth_header()
        url = f"{self.hub_url}/blockmodel/orgs/{self.org_id}/workspaces/{self.workspace_id}/block-models/{block_model_id}/versions"

        params = {"offset": str(offset)}
        if filter_param:
            params["filter"] = str(filter_param)

        logger.info(f"Requesting blockmodel versions from {url}")
        response = requests.get(url=f"{url}?{urlencode(params)}", headers=auth_header)

        if response.status_code != HTTPStatus.OK:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        return response

    def get_blockmodel_columns_job_url(self, block_model_id: str, version_uuid: Optional[str] = None) -> str:
        # Compose the URL, query parameters and JSON body
        url = f"{self.hub_url}/blockmodel/orgs/{self.org_id}/workspaces/{self.workspace_id}/block-models/{block_model_id}/blocks"

        body = {"columns": ["*"], "geometry_columns": "indices"}
        if version_uuid:
            body["version_uuid"] = version_uuid

        # Make a POST request and include the JSON body and headers
        auth_header = self.get_auth_header()
        logger.info(f"Requesting blockmodel columns from {url}")
        response = requests.post(url=url, json=body, headers=auth_header)

        # Copy the `job_url` parameter from the response
        if response.status_code != HTTPStatus.OK:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        return str(response.json()["job_url"])

    def get_blockmodel_columns_download_url(self, job_url: str) -> str:
        logger.info(f"Requesting blockmodel columns download URL from {job_url}")
        response = self.check_job_status(job_url=job_url)

        if response.status_code != HTTPStatus.OK:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        return str(response.json()["payload"]["download_url"])

    def download_parquet(self, download_url: str) -> str:
        logger.info(f"Requesting blockmodel parquet file from {download_url}")
        response = requests.get(url=download_url)

        if response.status_code != 200:
            raise ResponseError(f"Request failed: \n Status: {response.status_code} \n Response: {response.content!r}")

        temp_file = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        temp_file.write(response.content)
        temp_file.close()

        return temp_file.name
