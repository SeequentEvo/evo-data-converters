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

import nest_asyncio
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.logging
from evo.objects import ObjectAPIClient
from evo.objects.data import ObjectMetadata
from evo.objects.utils import ObjectDataClient

from .generate_paths import generate_paths

logger = evo.logging.getLogger("data_converters")


def publish_geoscience_objects(
    object_models: list[BaseSpatialDataProperties_V1_0_1],
    object_service_client: ObjectAPIClient,
    data_client: ObjectDataClient,
    path_prefix: str = "",
) -> list[ObjectMetadata]:
    """
    Publishes a list of Geoscience Objects.
    """
    objects_metadata = []
    paths = generate_paths(object_models, path_prefix)

    nest_asyncio.apply()

    logger.debug(f"Preparing to publish {len(object_models)} objects to paths: {paths}")
    for obj, obj_path in zip(object_models, paths):
        object_metadata = asyncio.run(publish_geoscience_object(obj_path, obj, object_service_client, data_client))
        logger.debug(f"Got object metadata: {object_metadata}")
        objects_metadata.append(object_metadata)

    return objects_metadata


async def publish_geoscience_object(
    path: str,
    object_model: BaseSpatialDataProperties_V1_0_1,
    object_service_client: ObjectAPIClient,
    data_client: ObjectDataClient,
) -> ObjectMetadata:
    """
    Publish a single Geoscience Object
    """
    logger.debug(f"Publishing Geoscience Object: {object_model}")
    await data_client.upload_referenced_data(object_model.as_dict())
    object_metadata = await object_service_client.create_geoscience_object(path, object_model.as_dict())
    return object_metadata
