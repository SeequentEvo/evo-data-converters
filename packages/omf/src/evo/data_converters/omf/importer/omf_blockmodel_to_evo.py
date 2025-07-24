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
from typing import Any

import nest_asyncio
import omf2
import pyarrow as pa

import evo.logging
from evo.common import APIConnector, Environment
from evo.data_converters.common import BlockSyncClient
from evo.objects import ObjectAPIClient

from .blockmodel.omf_blockmodel_to_blocksync import (
    add_blocks_and_columns,
    convert_omf_regular_block_model,
    convert_omf_regular_subblock_model,
    convert_omf_tensor_grid_model,
)

logger = evo.logging.getLogger("data_converters")


def _create_block_sync_client(environment: Environment, api_connector: APIConnector) -> BlockSyncClient:
    return BlockSyncClient(environment, api_connector)


def convert_omf_blockmodel(
    object_service_client: ObjectAPIClient, element: omf2.Element, reader: omf2.Reader, epsg_code: int
) -> list[dict[str, Any]]:
    """Converts an OMF file to BlockSync Objects and creates an empty model on BlockSync.

    :param object_service_client: Client which holds the metadata for connecting to the Evo service.
    :param element: The block model element to be processed.
    :param reader: The project reader.
    :param epsg_code: The EPSG code for the coordinate reference system.

    If problems are encountered while loading the OMF project, these will be logged as warnings.
    """
    environment = object_service_client._environment
    api_connector = object_service_client._connector
    nest_asyncio.apply()
    block_model_metadata = []

    if environment.hub_url == "":
        # This should only apply when running the convert-omf notebook
        logger.warning("Skipping block models")
    else:
        client = _create_block_sync_client(environment, api_connector)
        geometry = element.geometry()

        match geometry.grid:
            case omf2.Grid3Tensor():
                block_sync_model = convert_omf_tensor_grid_model(element, client, reader, epsg_code)
                if block_sync_model:
                    block_model_id, block_model, block_table = block_sync_model
                    upload_block_data_to_blockmodels(client, block_model, block_table, block_model_id)
                    block_model_metadata.append(client.get_blockmodel_metadata(block_model_id))
            case omf2.Grid3Regular():
                if geometry.subblocks:
                    match geometry.subblocks:
                        case omf2.FreeformSubblocks():
                            logger.warning(
                                "BlockSync does not support freeform subblock models where blocks do not have to align with any grid."
                            )
                        case omf2.RegularSubblocks():
                            block_model_id, block_model, block_table = convert_omf_regular_subblock_model(
                                element, client, reader, epsg_code
                            )
                            upload_block_data_to_blockmodels(client, block_model, block_table, block_model_id)
                            block_model_metadata.append(client.get_blockmodel_metadata(block_model_id))
                        case _:
                            logger.warning(
                                f"Skipping block model with unsupported subblocks type '{geometry.subblocks.__class__.__name__}'"
                            )
                else:
                    # Block model does not contain sub blocks
                    block_model_id, block_model, block_table = convert_omf_regular_block_model(
                        element, client, reader, epsg_code
                    )
                    upload_block_data_to_blockmodels(client, block_model, block_table, block_model_id)
                    block_model_metadata.append(client.get_blockmodel_metadata(block_model_id))

    return block_model_metadata


def upload_block_data_to_blockmodels(
    client: BlockSyncClient, block_model: dict, block_table: pa.Table, block_model_id: str
) -> None:
    """Upload block data to the newly created block models.

    :param client: The BlockSync API client.
    :param block_model: The block model metadata as a JSON dict.
    :param block_table: The block model data as a pyarrow table.
    :param block_model_id: The block model uuid on BlockSync, required to reference the specific model.
    """
    is_octree = block_model["size_options"]["model_type"] == "variable-octree"
    job_url = add_blocks_and_columns(
        client=client, block_model_uuid=block_model_id, table=block_table, is_octree=is_octree
    )
    if job_url:
        client.complete_blockmodel_upload(job_url)
