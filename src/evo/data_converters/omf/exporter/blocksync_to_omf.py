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
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import nest_asyncio
import numpy as np
import numpy.typing as npt
import omf
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.types as patypes
from omf import VolumeElement, VolumeGridGeometry
from omf.data import DateTimeData, Legend, MappedData, ProjectElementData, ScalarData
from scipy.spatial.transform import Rotation as R

import evo.logging
from evo.common import APIConnector, Environment
from evo.data_converters.common import BlockSyncClient, EvoWorkspaceMetadata, create_evo_object_service_and_data_client

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def _create_block_sync_client(environment: Environment, api_connector: APIConnector) -> BlockSyncClient:
    return BlockSyncClient(environment, api_connector)


def export_blocksync_omf(
    filepath: str,
    object_id: UUID,
    version_id: Optional[int] = None,
    evo_workspace_metadata: EvoWorkspaceMetadata = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
) -> None:
    nest_asyncio.apply()

    logger.info("Creating service and data clients for interacting with BlockSync.")
    service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata, service_manager_widget
    )

    environment = service_client._environment
    api_connector = service_client._connector

    client = _create_block_sync_client(environment, api_connector)

    project_name = str(object_id)
    description = "BlockSync Object"
    revision = version_id if version_id else ""

    project = omf.Project(name=project_name, description=description, revision=revision)

    project.elements = [blocksync_to_omf_element(str(object_id), client, version_id)]
    assert project.validate()

    logger.info("Writing OMF project to {filepath}")
    omf.OMFWriter(project, filepath)


def blocksync_to_omf_element(bm_uuid: str, client: BlockSyncClient, version_id: Optional[int] = None) -> VolumeElement:
    logger.info("Fetching JSON data for {bm_uuid}, version: {version_id}")
    json = client.get_blockmodel_request(bm_uuid).json()

    logger.info("Converting JSON data to OMF Volume Geometry and Volume Element")
    if (size_options := json.get("size_options")) and "model_type" in size_options:
        match size_options["model_type"].lower():
            case "regular":
                tensor_u, tensor_v, tensor_w = regular_size_options_to_volume_tensor(size_options)
            case _:
                raise ValueError(f"Unsupported value for model_type: {size_options['model_type']}")
    else:
        raise KeyError('Missing expected key in json["size_options"]["model_type"]')

    origin = [json["model_origin"]["x"], json["model_origin"]["y"], json["model_origin"]["z"]]

    orient_u, orient_v, orient_w = block_rotations_to_orientation(json["block_rotation"])

    geometry = VolumeGridGeometry(
        axis_u=orient_u,
        axis_v=orient_v,
        axis_w=orient_w,
        origin=origin,
        tensor_u=tensor_u,
        tensor_v=tensor_v,
        tensor_w=tensor_w,
    )
    data = export_blocksync_columns(bm_uuid=bm_uuid, version_id=version_id, client=client)
    volume = VolumeElement(name=json["name"], description=json["description"] or "", geometry=geometry, data=data)

    return volume


def export_blocksync_columns(
    bm_uuid: str, client: BlockSyncClient, version_id: Optional[int] = None
) -> list[ProjectElementData]:
    columns: list[ProjectElementData] = []

    version = get_current_or_matching_version(bm_uuid=bm_uuid, version_id=version_id, client=client)

    logger.info(f"Fetching columns for blockmodel {bm_uuid}, version: {version['version_id']}")
    job_url = client.get_blockmodel_columns_job_url(bm_uuid, version["version_uuid"])
    download_url = client.get_blockmodel_columns_download_url(job_url)
    downloaded_file_path = client.download_parquet(download_url)

    attribute_location = "cells"
    default_datetime = datetime(1000, 1, 1, tzinfo=timezone.utc)

    table = pq.read_table(downloaded_file_path)
    if all(column_name in table.column_names for column_name in ["i", "j", "k"]):
        table = table.sort_by([("i", "ascending"), ("j", "ascending"), ("k", "ascending")])

    logger.info("Converting downloaded columns to OMF Data attributes")
    for column in table.column_names:
        column_type = table.schema.field(column).type
        if patypes.is_floating(column_type) or patypes.is_integer(column_type):
            columns.append(ScalarData(name=column, array=table[column].to_numpy(), location=attribute_location))
        elif patypes.is_string(column_type):
            df = table.to_pandas()
            categorical = pd.Categorical(df[column])
            legend = Legend(name=column, description="", values=categorical.categories.to_list())
            columns.append(
                MappedData(name=column, legends=[legend], array=categorical.codes.tolist(), location=attribute_location)
            )
        elif patypes.is_date(column_type):
            datetime_list = [
                datetime.combine(date, time()).astimezone(timezone.utc) if date is not None else default_datetime
                for date in table[column].to_pylist()
            ]
            columns.append(DateTimeData(name=column, array=datetime_list, location=attribute_location))
        elif patypes.is_timestamp(column_type):
            columns.append(
                DateTimeData(
                    name=column,
                    array=[
                        timestamp.astimezone(timezone.utc) if timestamp is not None else default_datetime
                        for timestamp in table[column].to_pylist()
                    ],
                    location=attribute_location,
                )
            )

    os.unlink(downloaded_file_path)
    return columns


def regular_size_options_to_volume_tensor(
    size_options: dict,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    size_x = size_options["block_size"]["x"]
    nx = size_options["n_blocks"]["nx"]
    tensor_u = np.full(nx, size_x, dtype=float)

    size_y = size_options["block_size"]["y"]
    ny = size_options["n_blocks"]["ny"]
    tensor_v = np.full(ny, size_y, dtype=float)

    size_z = size_options["block_size"]["z"]
    nz = size_options["n_blocks"]["nz"]
    tensor_w = np.full(nz, size_z, dtype=float)

    return tensor_u, tensor_v, tensor_w


def block_rotations_to_orientation(
    block_rotations: list,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    # Base vectors
    u = np.array([1, 0, 0])
    v = np.array([0, 1, 0])
    w = np.array([0, 0, 1])

    if not block_rotations:
        return u, v, w

    axes = "".join(br["axis"].upper() for br in block_rotations)
    angles = [br["angle"] for br in block_rotations]

    rotation = R.from_euler(axes, angles, degrees=True)

    # Reflection matrices
    reflection = np.array([[1, 0, 0], [0, -1, 0], [0, 0, 1]])

    v_reflection = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]])

    return reflection @ rotation.apply(u), v_reflection @ rotation.apply(v), reflection @ rotation.apply(w)


def get_current_or_matching_version(
    bm_uuid: str, client: BlockSyncClient, version_id: Optional[int] = None, offset: int = 0
) -> dict:
    logger.info(f"Fetching version info for blockmodel {bm_uuid}, starting at offset {offset}")
    filter_param = "latest" if version_id is None else None
    versions = client.get_blockmodel_versions(bm_uuid, offset, filter_param).json()

    if versions["count"] <= 0:
        raise Exception(f"Requested versions for {bm_uuid} and got no results")

    for result in versions["results"]:
        if not isinstance(result, dict):
            result_type = str(type(result))
            raise TypeError(f"Version details expected to be a dict, {result_type} found instead")
        if not version_id:
            return result
        if result["version_id"] == int(version_id):
            return result

    return get_current_or_matching_version(bm_uuid, client, version_id, (offset + int(versions["limit"])))
