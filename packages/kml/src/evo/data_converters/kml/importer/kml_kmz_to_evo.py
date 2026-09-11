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
from typing import TYPE_CHECKING, Optional

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects_sync,
)
from evo.data_converters.kml.importer.implementation.kml_document_parser import KmlDocumentParser
from evo.data_converters.kml.importer.implementation.kml_evo_object_builder import KmlEvoObjectBuilder
from evo.data_converters.kml.importer.implementation.local_data import LocalDataClient
from evo.objects.data import ObjectMetadata
from evo_schemas.components.crs import Crs_V1_0_1, Crs_V1_0_1_EpsgCode
from evo_schemas.objects.line_segments import LineSegments_V2_2_0
from evo_schemas.objects.pointset import Pointset_V1_3_0

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_kml_kmz(
    filepath: str,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[Pointset_V1_3_0 | LineSegments_V2_2_0] | list[ObjectMetadata]:
    """
    Convert a Google Earth KML/KMZ file into Geoscience Objects (points and/or line segments).

    :param filepath: Path to the .kml or .kmz geometry file.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :param publish_objects: (Optional) Set False to prevent publishing and instead return Geoscience models.
    :param overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the destiation path.

    :return: list[ObjectMetadata] if publish_objects is true, otherwise list[Pointset_V1_3_0 | LineSegments_V2_2_0]

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    :raise InvalidKMLError: If the input KML/KMZ file is invalid or cannot be parsed.

    One of evo_workspace_metadata or service_manager_widget is required for publishing.
    """
    geoscience_objects: list[Pointset_V1_3_0 | LineSegments_V2_2_0] = []

    if publish_objects or evo_workspace_metadata or service_manager_widget:
        object_service_client, data_client = create_evo_object_service_and_data_client(
            evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
        )
    else:
        data_client = LocalDataClient(upload_path)

    full_tags = {
        "Source": f"{os.path.basename(filepath)} (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "KML/KMZ",
        **(tags or {}),        
    }

    crs: Crs_V1_0_1 = Crs_V1_0_1_EpsgCode(epsg_code=4326) # KML/KMZ coordinates are lon/lat in WGS84 by default

    document_parser = KmlDocumentParser(
        path=filepath,
        data_client=data_client,
        crs=crs,
        tags=full_tags,
    )
    document = document_parser.parse()

    evo_objects = KmlEvoObjectBuilder(
        data_client=data_client,
        crs=crs,
        tags=full_tags,
    ).build(document)

    geoscience_objects.extend(evo_objects)

    objects_metadata = None
    if publish_objects:
        print("Publishing KML/KMZ")
        objects_metadata = publish_geoscience_objects_sync(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
