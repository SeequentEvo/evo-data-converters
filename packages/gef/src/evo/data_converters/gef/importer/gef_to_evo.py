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

from pathlib import Path
from typing import TYPE_CHECKING

import evo.logging
from evo.common.context import StaticContext
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.data_converters.gef.converter import parse_gef_files
from evo.data_converters.gef.converter.gef_to_downhole_collection import build_downhole_collection, process_cpt_files
from evo.data_converters.gef.objects import DownholeCollection
from evo.objects import ObjectReference
from evo.objects.data import ObjectMetadata

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


async def convert_gef(
    filepaths: list[str | Path],
    epsg_code: int | None = None,
    evo_workspace_metadata: EvoWorkspaceMetadata | None = None,
    service_manager_widget: "ServiceManagerWidget | None" = None,
    name: str | None = None,
    tags: dict[str, str] | None = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[ObjectMetadata] | None:
    """Converts a collection of GEF-CPT files into a Downhole Collection Geoscience Object.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted object will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    :param filepaths: List of Paths to the GEF files.
    :param epsg_code: (Optional) The default EPSG code to use when creating a Coordinate Reference System object.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param name (Optional) Name for DownholeCollection, auto-generated from hole IDs if not provided.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object.
    :param upload_path: (Optional) Path object will be published under.
    :publish_objects: (Optional) Set False to return rather than publish objects.
    :param overwrite_existing_objects: (Optional) Whether existing objects will be overwritten with a new version.

    :return: Geoscience Object or ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )

    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing will be skipped due to missing hub_url.")
        publish_objects = False

    tags = {
        "Source": "GEF-CPT files (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "GEF-CPT",
        **(tags or {}),
    }

    gef_cpt_data = parse_gef_files(filepaths)
    processed_gef_cpt_data = process_cpt_files(gef_cpt_data)
    downhole_collection_data = build_downhole_collection(
        processed_gef_cpt_data, name=name, tags=tags, epsg_code=epsg_code
    )

    # TODO - Need to find a better way to do this
    context = StaticContext(
        connector=data_client._connector,
        cache=data_client._cache,
        org_id=data_client._environment.org_id,
        workspace_id=data_client._environment.workspace_id,
    )

    # TODO - Does this make sense using the "typed" objects? What is expected to happen if publish_objects=False?
    if publish_objects:
        logger.debug("Publishing Geoscience Object")
        if overwrite_existing_objects:
            if not upload_path.lower().endswith(".json"):
                upload_path += ".json"
            ref = ObjectReference.new(data_client._environment, object_path=upload_path)
            return [(await DownholeCollection.create_or_replace(context, ref, downhole_collection_data)).metadata]
        else:
            return [(await DownholeCollection.create(context, downhole_collection_data, path=upload_path)).metadata]
