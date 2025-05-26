import os
from typing import TYPE_CHECKING, Optional

from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.data_converters.duf import DufCollectorContext, ObjectCollector
from ..common.duf_wrapper import Polyface, Polyline
from evo.objects.data import ObjectMetadata

from .duf_lineset_to_evo import convert_duf_lineset
from .duf_surface_to_evo import convert_duf_surface

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_duf(
    filepath: str,
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts a DUF file into Geoscience Objects.

    :param filepath: Path to the DUF file.
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    If problems are encountered while loading the DUF file, these will be logged as warnings.

    :return: List of Geoscience Objects, or list of ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """
    publish_objects = True
    geoscience_objects = []

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing objects will be skipped due to missing hub_url.")
        publish_objects = False

    with DufCollectorContext(filepath) as context:
        collector: ObjectCollector = context.collector

    converters = {Polyface: convert_duf_surface, Polyline: convert_duf_lineset}

    for klass, objs in collector.get_all_objects_by_type():
        if (converter := converters.get(klass)) is None:
            logger.warning(f"Unsupported DUF object type: {klass.__name__}, ignoring {len(objs)} objects.")
            continue

        for cat, obj in objs:
            geoscience_object = converter(obj, data_client, epsg_code)

            if geoscience_object:
                if geoscience_object.tags is None:
                    geoscience_object.tags = {}
                geoscience_object.tags["Source"] = f"{os.path.basename(filepath)} (via Evo Data Converters)"
                geoscience_object.tags["InputType"] = "DUF"
                geoscience_object.tags["Category"] = str(cat)

                # Add custom tags
                if tags:
                    geoscience_object.tags.update(tags)

                geoscience_objects.append(geoscience_object)

    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path
        )

    return objects_metadata if objects_metadata else geoscience_objects
