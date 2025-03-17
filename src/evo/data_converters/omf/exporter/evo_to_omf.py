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

import asyncio
import dataclasses
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import nest_asyncio
import omf
from evo_schemas import schema_lookup
from evo_schemas.objects import (
    LineSegments_V2_0_0,
    LineSegments_V2_1_0,
    Pointset_V1_1_0,
    Pointset_V1_2_0,
    TriangleMesh_V2_0_0,
    TriangleMesh_V2_1_0,
)

import evo.logging
from evo.common.utils.cache import Cache
from evo.data_converters.common import (
    EvoObjectMetadata,
)
from evo.objects.client import ObjectAPIClient
from evo.objects.data import ObjectSchema
from evo.objects.utils.data import ObjectDataClient

from ..omf_metadata import OMFMetadata
from .evo_lineset_to_omf import export_omf_lineset
from .evo_pointset_to_omf import export_omf_pointset
from .evo_surface_to_omf import export_omf_surface


class OmfExporterException(Exception):
    pass


class UnsupportedObjectError(OmfExporterException):
    pass


logger = evo.logging.getLogger("data_converters")


def _download_evo_object_by_id(
    service_client: ObjectAPIClient,
    object_id: UUID,
    version_id: Optional[str] = None,
) -> dict[str, Any]:
    downloaded_object = asyncio.run(service_client.download_object_by_id(object_id, version_id))
    result: dict[str, Any] = downloaded_object.as_dict()
    return result


def _export_element(
    object_metadata: EvoObjectMetadata,
    service_client: ObjectAPIClient,
    data_client: ObjectDataClient,
) -> tuple[omf.base.ProjectElement, ObjectSchema]:
    object_id = object_metadata.object_id
    version_id = object_metadata.version_id

    # Download object
    geoscience_object_dict = _download_evo_object_by_id(service_client, object_id, version_id)

    # Check if this is a known geoscience object schema type
    schema = ObjectSchema.from_id(geoscience_object_dict["schema"])
    object_class = schema_lookup.get(str(schema))

    if not object_class:
        raise UnsupportedObjectError(f"Unknown Geoscience Object schema '{schema}'")

    geoscience_object = object_class.from_dict(geoscience_object_dict)

    # Convert to OMF element
    match geoscience_object:
        case TriangleMesh_V2_0_0() | TriangleMesh_V2_1_0():
            element = export_omf_surface(object_id, version_id, geoscience_object, data_client)
        case LineSegments_V2_0_0() | LineSegments_V2_1_0():
            element = export_omf_lineset(object_id, version_id, geoscience_object, data_client)
        case Pointset_V1_1_0() | Pointset_V1_2_0():
            element = export_omf_pointset(object_id, version_id, geoscience_object, data_client)
        case _:
            raise UnsupportedObjectError(
                f"Exporting {geoscience_object.__class__.__name__} Geoscience Objects to OMF is not supported"
            )

    return element, schema


def export_omf(
    filepath: str,
    objects: list[EvoObjectMetadata],
    service_client: ObjectServiceClient,
    omf_metadata: Optional[OMFMetadata] = None,
    cache: Optional[Cache] = None,
) -> None:
    """Export an Evo Geoscience Object to an OMF v1 file.

    :param filepath: Path of the OMF file to create.
    :param objects: List of EvoObjectMetadata objects containing the UUID and version of the Evo objects to export.
    :param service_client: Connection to the Objects Service to access Evo.
    :param omf_metadata: Optional project metadata to embed in the OMF file.
    :param cache: (Optional) The cache to use for data downloads. Defaults to `.data/cache` dir.


    :raise UnsupportedObjectError: If the type of object is not supported.
    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """

    data_client = service_client.get_data_client(cache if cache is not None else Cache(root="./data/cache", mkdir=True))

    nest_asyncio.apply()

    omf_metadata = dataclasses.replace(omf_metadata) if omf_metadata else OMFMetadata()

    if len(objects) == 1:
        object_metadata = objects[0]
        element, schema = _export_element(object_metadata, service_client, data_client)
        elements = [element]

        # infer project attributes from data
        omf_metadata.name = omf_metadata.name or element.name or "EvoObject"
        omf_metadata.revision = omf_metadata.revision or object_metadata.version_id or ""
        omf_metadata.description = (
            omf_metadata.description
            or f"{schema.sub_classification.capitalize()} object with ID {object_metadata.object_id}"
        )
    else:
        elements = [_export_element(object_metadata, service_client, data_client)[0] for object_metadata in objects]

        omf_metadata.name = omf_metadata.name or "EvoObjects"
        omf_metadata.description = omf_metadata.description or "Objects with IDs " + ", ".join(
            str(object_metadata.object_id) for object_metadata in objects
        )

    project = omf_metadata.to_project(elements)

    # Write file
    omf.OMFWriter(project, filepath)
