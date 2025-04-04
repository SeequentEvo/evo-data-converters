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

import os
from typing import Optional

import omf2
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.logging
from evo.common.utils.cache import Cache
from evo.data_converters.common import (
    publish_geoscience_objects,
)
from evo.data_converters.omf import OmfReaderContext
from evo.objects.data import ObjectMetadata, ObjectServiceClient

from .omf_blockmodel_to_evo import convert_omf_blockmodel
from .omf_lineset_to_evo import convert_omf_lineset
from .omf_pointset_to_evo import convert_omf_pointset
from .omf_surface_to_evo import convert_omf_surface

logger = evo.logging.getLogger("data_converters")


def convert_omf(
    filepath: str,
    epsg_code: int,
    object_service_client: ObjectServiceClient,
    cache: Optional[Cache] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts an OMF file into Geoscience Objects.

    :param filepath: Path to the OMF file.
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param object_service_client: Connection to the Objects Service to access Evo.
    :param cache: (Optional) The cache to use for data downloads. Defaults to `.data/cache` dir.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.
    :param publish_objects: (Optional) Whether to publish the object to Evo.

    Converted objects will be published to the workspace specified in the object_service_client.

    If problems are encountered while loading the OMF project, these will be logged as warnings.

    Caveats: For some OMF geometry types there is more one possible way they could be converted to Geoscience Objects.
    An OMF LineSet can be used to represent more than one thing (e.g. poly-lines, drillholes, a wireframe mesh, etc).
    In this library they are converted to LineSegments. You may want to convert them to a different Geoscience Object
    depending on your use case.

    :return: List of Geoscience Objects, or list of ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """
    geoscience_objects = []

    data_client = object_service_client.get_data_client(cache if cache is not None else Cache(root="./data/cache", mkdir=True))

    context = OmfReaderContext(filepath)
    reader = context.reader()

    project, problems = reader.project()

    if problems:
        logger.warning("Problems returned reading OMF project:")
        for problem in problems:
            logger.warning(problem)

    for element in project.elements():
        geoscience_object = None
        try:
            geometry = element.geometry()
        except omf2.OmfNotSupportedException:
            logger.warning(f"Trying to load an unsupported geometry type: {element.name}")
            continue

        match geometry:
            case omf2.PointSet():
                geoscience_object = convert_omf_pointset(element, project, reader, data_client, epsg_code)
            case omf2.Surface():
                geoscience_object = convert_omf_surface(element, project, reader, data_client, epsg_code)
            case omf2.LineSet():
                geoscience_object = convert_omf_lineset(element, project, reader, data_client, epsg_code)
            case omf2.BlockModel():
                convert_omf_blockmodel(object_service_client, element, reader, epsg_code)
            case _:
                continue

        if geoscience_object:
            if geoscience_object.tags is None:
                geoscience_object.tags = {}
            geoscience_object.tags["Source"] = f"{os.path.basename(filepath)} (via Evo Data Converters)"
            geoscience_object.tags["Stage"] = "Experimental"
            geoscience_object.tags["InputType"] = "OMF"

            # Add custom tags
            if tags:
                geoscience_object.tags.update(tags)

            geoscience_objects.append(geoscience_object)

    objects_metadata = None
    logger.debug("Publishing Geoscience Objects")
    objects_metadata = publish_geoscience_objects(
        geoscience_objects, object_service_client, data_client, upload_path
    )

    return objects_metadata if objects_metadata else geoscience_objects
