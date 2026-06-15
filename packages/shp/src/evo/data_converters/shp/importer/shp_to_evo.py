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
from evo.data_converters.shp.importer.implementation.prj_parser import prj_to_crs
from evo.data_converters.shp.importer.implementation.shp_parser import ShpParser
from evo.objects.data import ObjectMetadata
from evo_schemas.objects.triangle_mesh import TriangleMesh_V2_2_0

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_shp(
    filepath: str,
    filepath_shx: str,
    filepath_dbf: str,
    filepath_prj: Optional[str] = None,
    filepath_cpg: Optional[str] = None,
    filepath_sbn: Optional[str] = None,
    filepath_sbx: Optional[str] = None,
    filepath_xml: Optional[str] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[TriangleMesh_V2_2_0] | list[ObjectMetadata]:
    """
    Convert an ESRI shapefile (.shp, .shx, and .dbf) to a triangle-mesh geoscience object.

    :param filepath: Path to the .shp geometry file.
    :param filepath_shx: Path to the .shx spatial index file.
    :param filepath_dbf: Path to the .dbf attribute file.
    :param filepath_prj: (Optional) Path to the .prj projection file. If not provided,
     the CRS will be set to "unspecified".
    :param filepath_cpg: (Optional) Path to the .cpg code page file. If provided, the encoding
     specified in the file will be used when reading the .dbf attribute data.
    :param filepath_sbn: (Optional) Path to the .sbn spatial index file. Accepted but not currently used.
    :param filepath_sbx: (Optional) Path to the .sbx spatial index file. Accepted but not currently used.
    :param filepath_xml: (Optional) Path to the .shp.xml metadata file. Accepted but not currently used.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :param publish_objects: (Optional) Set False to prevent publishing and instead return Geoscience models.
    :param overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the destiation path.

    :return: list[ObjectMetadata] if publish_objects is true, otherwise list[TriangleMesh_V2_2_0]

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    :raise InvalidOBJError: If the input shapefile is invalid or cannot be parsed.
    :raise InvalidCRSError: If the input CRS information is invalid.

    One of evo_workspace_metadata or service_manager_widget is required for publishing.
    """
    geoscience_objects = []

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )

    full_tags = {
        "Source": f"{os.path.basename(filepath)} (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "SHP",
        **(tags or {}),
    }

    crs = prj_to_crs(filepath_prj)

    parser = ShpParser(
        path=filepath,
        shx_path=filepath_shx,
        dbf_path=filepath_dbf,
        data_client=data_client,
        crs=crs,
        tags=full_tags,
        cpg_path=filepath_cpg,
        sbn_path=filepath_sbn,
        sbx_path=filepath_sbx,
        xml_path=filepath_xml,
    )
    mesh = parser.parse_shp()

    geoscience_objects.append(mesh)

    objects_metadata = None
    if publish_objects:
        print("Publishing Shapefile")
        objects_metadata = publish_geoscience_objects_sync(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
