#  Copyright © 2026 Bentley Systems, Incorporated
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
from .xyz_parser import parse_xyz_file

from evo_schemas.objects.pointset import Pointset_V1_3_0
from typing import TYPE_CHECKING, Optional

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects_sync,
)

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_xyz(
    filepath: str,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[Pointset_V1_3_0]:
    geoscience_objects = []

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )

    pointset = parse_xyz_file(filepath, data_client)

    pointset.tags = {
        "Source": f"{os.path.basename(filepath)} (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "XYZ",
        **(tags or {}),
    }

    geoscience_objects = [pointset]

    objects_metadata = None
    if publish_objects:
        print("Publishing XYZ file")
        objects_metadata = publish_geoscience_objects_sync(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
