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

from typing import TYPE_CHECKING

from evo.data_converters.ags.common import AgsContext
from evo.data_converters.ags.importer import create_downhole_collection
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
import evo.logging
from evo.objects.data import ObjectMetadata
from evo_schemas.objects import DownholeCollection_V1_3_0 as DownholeCollection
from python_ags4.AGS4 import AGS4Error

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_ags(
    filepath: str,
    evo_workspace_metadata: EvoWorkspaceMetadata | None = None,
    service_manager_widget: "ServiceManagerWidget | None" = None,
    tags: dict[str, str] | None = None,
    upload_path: str = "",
    overwrite_existing_objects: bool = False,
) -> DownholeCollection | ObjectMetadata | None:
    """
    Converts an AGS file into a Downhole Collection Geoscience Object.

    :param filepath: Path to the AGS file.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :param overwrite_existing_objects: (Optional) Whether existing objects will be overwritten with a new version.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    :return: The converted Downhole Collection object, or metadata of the published object if published.
    :rtype: DownholeCollection | ObjectMetadata | None

    :raises MissingConnectionDetailsError: If no connection details could be derived.
    :raises ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget were provided.
    """
    publish_object = True

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing will be skipped due to missing hub_url.")
        publish_object = False

    ags_context = AgsContext()
    try:
        ags_context.parse_ags(filepath)
    except AGS4Error as e:
        logger.error("Failed to parse AGS file: %s", e)
        return

    downhole_collection = create_downhole_collection(ags_context, data_client, tags)
    if downhole_collection:
        if downhole_collection.tags is None:
            downhole_collection.tags = {}
        downhole_collection.tags["Source"] = "AGS files (via Evo Data Converters)"
        downhole_collection.tags["Stage"] = "Experimental"
        downhole_collection.tags["InputType"] = "AGS"

        # Add custom tags
        if tags:
            downhole_collection.tags.update(tags)

    object_metadata = None
    if publish_object:
        logger.debug("Publishing Geoscience Object")
        object_metadata = publish_geoscience_objects(
            [downhole_collection],
            object_service_client,
            data_client,
            upload_path,
            overwrite_existing_objects,
        )

    return object_metadata[0] if object_metadata else downhole_collection
