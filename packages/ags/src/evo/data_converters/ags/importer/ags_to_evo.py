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

from evo_schemas.objects import DownholeCollection_V1_3_1
from python_ags4.AGS4 import AGS4Error

import evo.logging
from evo.data_converters.ags.common import AgsContext, AgsFileInvalidException
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.data_converters.common.objects import DownholeCollection, DownholeCollectionToGeoscienceObject
from evo.objects.data import ObjectMetadata

from .ags_to_downhole_collection import create_from_parsed_ags
from .parse_ags_files import parse_ags_files

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_ags(
    filepaths: list[str],
    evo_workspace_metadata: EvoWorkspaceMetadata | None = None,
    service_manager_widget: "ServiceManagerWidget | None" = None,
    tags: dict[str, str] | None = None,
    upload_path: str = "",
    overwrite_existing_objects: bool = False,
) -> list[DownholeCollection_V1_3_1] | list[ObjectMetadata]:
    """Converts one or more AGS files into a list of Downhole Collection Geoscience Objects.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:

    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    :param filepaths: List of paths to one or more AGS files.
    :param evo_workspace_metadata: Evo workspace metadata (optional).
    :param service_manager_widget: Service Manager Widget for use in jupyter notebooks (optional).
    :param tags: Dict of tags to add to the Geoscience Object(s) (optional).
    :param upload_path: Path objects will be published under (optional).
    :param overwrite_existing_objects: Whether existing objects will be overwritten with a new version
        (optional, default False).
    :return: The converted Downhole Collection object, or metadata of the published object if published.
    :rtype: DownholeCollection_V1_3_1 | ObjectMetadata
    :raises MissingConnectionDetailsError: If no connection details could be derived.
    :raises ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget
        were provided.
    """
    publish_objects = True

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing will be skipped due to missing hub_url.")
        publish_objects = False

    try:
        ags_contexts: list[AgsContext] = list(parse_ags_files(filepaths).values())
    except (AGS4Error, AgsFileInvalidException) as e:
        logger.error("Failed to parse AGS file(s): %s", e)
        return []

    default_tags: dict[str, str] = {
        "Source": "AGS files (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "AGS",
    }
    merged_tags: dict[str, str] = {**default_tags, **(tags or {})}

    downhole_collections: list[DownholeCollection] = [
        create_from_parsed_ags(context, merged_tags) for context in ags_contexts
    ]

    object_metadata: None | list[ObjectMetadata] = None
    geoscience_objects: list[DownholeCollection_V1_3_1] = [
        DownholeCollectionToGeoscienceObject(dhc, data_client).convert() for dhc in downhole_collections
    ]

    if publish_objects:
        logger.debug("Publishing Geoscience Object")
        object_metadata = publish_geoscience_objects(
            object_models=geoscience_objects,
            object_service_client=object_service_client,
            data_client=data_client,
            path_prefix=upload_path,
            overwrite_existing_objects=overwrite_existing_objects,
        )

    return object_metadata if object_metadata else geoscience_objects
