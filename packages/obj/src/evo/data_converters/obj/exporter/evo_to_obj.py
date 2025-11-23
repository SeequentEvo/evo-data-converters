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

from __future__ import annotations
from typing import TYPE_CHECKING, Optional


import evo.logging
from evo.data_converters.common import (
    EvoObjectMetadata,
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)

from ..omf_metadata import OMFMetadata

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


logger = evo.logging.getLogger("data_converters")


async def export_obj(
    filepath: str,
    objects: list[EvoObjectMetadata],
    omf_metadata: Optional[OMFMetadata] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional[ServiceManagerWidget] = None,
) -> None:
    """Export an Evo Geoscience Object to an OBJ file.
    FIXME: multiple files?

    :param filepath: Path of the OBJ file to create. *Other files may be created next to it.*
    :param objects: List of EvoObjectMetadata objects containing the UUID and version of the Evo objects to export.
    :param omf_metadata: Optional project metadata to embed in the OMF file.
    :param evo_workspace_metadata: Optional Evo Workspace metadata.
    :param service_manager_widget: Optional ServiceManagerWidget for use in notebooks.

    One of evo_workspace_metadata or service_manager_widget is required.

    :raise UnsupportedObjectError: If the type of object is not supported.
    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """

    service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata, service_manager_widget
    )

    # TODO: implementation
