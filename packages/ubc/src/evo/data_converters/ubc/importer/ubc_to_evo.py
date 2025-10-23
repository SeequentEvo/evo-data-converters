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

from typing import TYPE_CHECKING, Optional

from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.data_converters.ubc.importer import utils
from evo.objects.data import ObjectMetadata

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_ubc(
    files_path: list[str],
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    overwrite_existing_objects: bool = False,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts a UBC files into Geoscience Objects.

    :param files_path: list of paths to the UBC .msh/.nev files.
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.

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

    publish_objects = True

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing objects will be skipped due to missing hub_url.")
        publish_objects = False

    geoscience_objects = [utils.get_geoscience_object_from_ubc(data_client, files_path, epsg_code, tags)]
    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
