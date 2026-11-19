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
import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Optional

from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.logging
from evo.data_converters.las.importer import utils
from evo.data_converters.las.importer.utils import DeviationFiles
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.data_converters.common.crs import crs_from_any, crs_from_epsg_code
from evo.objects.data import ObjectMetadata

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


async def convert_las(
    filepath: str | os.PathLike | Sequence[str | os.PathLike],
    epsg_code: Optional[int] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
    *,
    coordinate_reference_system: str | int | None = None,
    deviation_files: Optional[DeviationFiles] = None,
    allow_missing_deviation: bool = False,
    collection_name: Optional[str] = None,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts one or more LAS 2.0 files into a single downhole collection (one hole per file) plus a point set\n    of every log sample located along its hole trajectory.

    :param filepath: Path, or list of paths, of the LAS files. The index curve must be depth.
    :param epsg_code: (Optional, deprecated) Integer EPSG code for the coordinate reference system. Use ``coordinate_reference_system`` instead.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :param publish_objects: (Optional) Set False to return rather than publish objects.
    :param overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the upload_path.
    :param coordinate_reference_system: (Optional) Coordinate reference system: an integer or string EPSG code (e.g. ``2193`` or ``"EPSG:2193"``), an OGC WKT string, or ``None`` for unspecified.
    :param deviation_files: (Optional) Petrel deviation (.dev) files supplying each hole's collar and survey: a directory, a list of files, or a dict of hole id to file. Files are matched to holes by well name. Depths and coordinates in deviation files are assumed to be in metres. Without them each hole gets a collar at (0, 0, 0) and a vertical path.
    :param allow_missing_deviation: (Optional) Set True to give holes with no matching deviation file the default collar and vertical path, rather than raising an error, when deviation_files is provided.
    :param collection_name: (Optional) Name of the downhole collection. Defaults to the file name, or "LAS downhole collection" for several files.

    Both epsg_code and coordinate_reference_system can't be provided, otherwise a ValueError will be raised. If neither is provided, the CRS will be set to "unspecified".

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    :return: List of Geoscience Objects, or list of ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    :raise LASDataFileIOError: If the LAS file could not be opened or read.
    :raise LASInvalidDataError: If an error was detected in the LAS file.
    """

    object_service_client, data_client = await create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
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

    created = utils.get_geoscience_object_from_las(
        data_client,
        filepath,
        crs,
        tags,
        deviation_files=deviation_files,
        allow_missing_deviation=allow_missing_deviation,
        collection_name=collection_name,
    )
    geoscience_objects = list(created) if isinstance(created, list) else [created]
    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = await publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
