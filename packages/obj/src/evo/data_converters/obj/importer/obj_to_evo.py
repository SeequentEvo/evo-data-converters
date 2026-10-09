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

import gc
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.data_converters.common.crs import crs_from_any, crs_from_epsg_code
from evo.objects.data import ObjectMetadata

from .implementation.base import ObjImporterBase

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


async def convert_obj(
    filepath: str,
    epsg_code: Optional[int] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional[ServiceManagerWidget] = None,
    tags: Optional[dict[str, str]] = None,
    implementation: str = "trimesh",
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
    *,
    coordinate_reference_system: str | int | None = None,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata | dict]:
    """Converts an OBJ file into Geoscience Objects.

    :param filepath: Path to the OBJ file. *Other adjacent files may also be read, eg. MTL file *
    :param epsg_code: (Optional, deprecated) Integer EPSG code for the coordinate reference system. Use ``coordinate_reference_system`` instead.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :param publish_objects: (Optional) Set False to prevent publishing and instead return Geoscience models.
    :param overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the destiation path.
    :param implementation: (Optional) The implementation to use for the conversion, either "trimesh" or "tinyobj". Default is "trimesh".
    :param coordinate_reference_system: (Optional) Coordinate reference system: an integer or string EPSG code (e.g. ``2193`` or ``"EPSG:2193"``), an OGC WKT string, or ``None`` for unspecified.

    Both epsg_code and coordinate_reference_system can't be provided, otherwise a ValueError will be raised. If neither is provided, the CRS will be set to "unspecified".

    One of evo_workspace_metadata or service_manager_widget is required.

    :return: List of Geoscience Objects and Block Models, or list of ObjectMetadata and Block Models if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    :raise InvalidOBJError: If the input OBJ file is invalid or cannot be parsed.
    :raise InvalidCRSError: If the input CRS information is invalid.
    """
    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )

    if epsg_code is not None:
        if coordinate_reference_system is not None:
            raise ValueError("Both epsg_code and coordinate_reference_system were provided. Please provide only one.")
        warnings.warn(
            "The epsg_code parameter is deprecated, please use coordinate_reference_system instead.", DeprecationWarning
        )
        crs = crs_from_epsg_code(epsg_code)
    else:
        crs = crs_from_any(coordinate_reference_system)

    impl_class: type[ObjImporterBase]
    if implementation == "trimesh":
        from .implementation.trimesh import TrimeshObjImporter

        impl_class = TrimeshObjImporter
    elif implementation == "tinyobj":
        from .implementation.tinyobj import TinyobjObjImporter

        impl_class = TinyobjObjImporter
    else:
        raise ValueError(f"Unknown implementation {implementation}, possible options: trimesh, tinyobj")

    importer = impl_class(obj_file=filepath, crs=crs, data_client=data_client)

    triangle_mesh_go = importer.convert_file()

    # Deallocate the parser's memory to shorten the memory peak during a conversion.
    del importer
    gc.collect()

    filepath_p = Path(filepath)

    triangle_mesh_go.tags = {
        "Source": f"{filepath_p.name} (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "OBJ",
        **(tags or {}),
    }

    geoscience_objects = [triangle_mesh_go]

    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = await publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
