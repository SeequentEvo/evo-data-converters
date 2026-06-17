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
from collections import defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Optional

from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.logging
import nest_asyncio
from evo.common.exceptions import NotFoundException
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.data_converters.ubc.importer import utils
from evo.objects.data import ObjectMetadata

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def _generate_publish_paths(object_models: list[BaseSpatialDataProperties_V1_0_1], upload_path: str) -> list[str]:
    count: defaultdict[str, int] = defaultdict(int)
    paths: list[str] = []

    for obj in object_models:
        base_name = obj.name
        obj_path = f"{base_name}.json"

        if (n := count[base_name]) > 0:
            if n == 1:
                paths[paths.index(obj_path)] = f"{base_name}_1.json"
            obj_path = f"{base_name}_{n + 1}.json"

        paths.append(obj_path)
        count[base_name] += 1

    if upload_path:
        paths = [str(PurePosixPath(upload_path, p)).lstrip("/") for p in paths]

    return paths


def _publish_ubc_objects_sync(
    geoscience_objects: list[BaseSpatialDataProperties_V1_0_1],
    object_service_client,
    data_client,
    upload_path: str,
    overwrite_existing_objects: bool,
) -> list[ObjectMetadata]:
    nest_asyncio.apply()
    objects_metadata: list[ObjectMetadata] = []

    for obj, obj_path in zip(geoscience_objects, _generate_publish_paths(geoscience_objects, upload_path)):
        obj.uuid = None

        try:
            existing_object = asyncio.run(object_service_client.download_object_by_path(obj_path))
            if overwrite_existing_objects:
                obj.uuid = existing_object.metadata.id
        except NotFoundException:
            pass

        payload = obj.as_dict()
        asyncio.run(data_client.upload_referenced_data(payload))

        if overwrite_existing_objects and obj.uuid is not None:
            object_metadata = asyncio.run(object_service_client.update_geoscience_object(payload))
        else:
            payload.pop("uuid", None)
            object_metadata = asyncio.run(object_service_client.create_geoscience_object(obj_path, payload))

        objects_metadata.append(object_metadata)

    return objects_metadata


def convert_ubc(
    files_path: list[str],
    epsg_code: Optional[int] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
    coordinate_reference_system: Optional[dict] = None,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts a UBC files into Geoscience Objects.

    :param files_path: list of paths to the UBC .msh/.nev files.
    :param epsg_code: (Optional) EPSG code for backward compatibility.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :publish_objects: (Optional) Set False to return rather than publish objects.
    :overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the upload_path.
    :param coordinate_reference_system: (Optional) Coordinate Reference System in Evo-compatible format,
                                        for example {"epsg_code": 4326} or {"ogc_wkt": "..."}.
                                        If both are provided, coordinate_reference_system takes precedence.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    :return: List of Geoscience Objects, or list of ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    :raise UBCFileIOError: If failed to read UBC file.
    :raise UBCInvalidDataError: If an error was detected within the UBC file.
    :raise UBCOOMError: If out of memory error occurred while handling the UBC file.
    """

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )

    geoscience_objects = [
        utils.get_geoscience_object_from_ubc(
            data_client,
            files_path,
            epsg_code=epsg_code,
            coordinate_reference_system=coordinate_reference_system,
            tags=tags,
        )
    ]
    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = _publish_ubc_objects_sync(
            geoscience_objects,
            object_service_client,
            data_client,
            upload_path,
            overwrite_existing_objects,
        )

    return objects_metadata if objects_metadata else geoscience_objects
