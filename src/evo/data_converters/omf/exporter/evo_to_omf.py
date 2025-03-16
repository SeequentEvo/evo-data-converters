import asyncio
import dataclasses
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import nest_asyncio
import omf
from geoscience_object_models import schema_lookup
from geoscience_object_models.objects import (
    LineSegments_V2_0_0,
    LineSegments_V2_1_0,
    Pointset_V1_1_0,
    Pointset_V1_2_0,
    TriangleMesh_V2_0_0,
    TriangleMesh_V2_1_0,
)

import evo.logging
from evo.data_converters.common import (
    EvoObjectMetadata,
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.objects.client import ObjectServiceClient
from evo.objects.data import ObjectSchema
from evo.objects.utils.data import ObjectDataClient

from ..omf_metadata import OMFMetadata
from .evo_lineset_to_omf import export_omf_lineset
from .evo_pointset_to_omf import export_omf_pointset
from .evo_surface_to_omf import export_omf_surface

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


class OmfExporterException(Exception):
    pass


class UnsupportedObjectError(OmfExporterException):
    pass


logger = evo.logging.getLogger("data_converters")


def _download_evo_object_by_id(
    service_client: ObjectServiceClient,
    object_id: UUID,
    version_id: Optional[str] = None,
) -> dict[str, Any]:
    downloaded_object = asyncio.run(service_client.download_object_by_id(object_id, version_id))
    result: dict[str, Any] = downloaded_object.as_dict()
    return result


def _export_element(
    object_metadata: EvoObjectMetadata,
    service_client: ObjectServiceClient,
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
    omf_metadata: Optional[OMFMetadata] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
) -> None:
    """Export an Evo Geoscience Object to an OMF v1 file.

    :param filepath: Path of the OMF file to create.
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
