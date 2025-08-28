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
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

import evo.logging
from evo.objects.utils import ObjectDataClient

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.objects.data import ObjectMetadata
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

import evo.data_converters.duf.common.deswik_types as dw
from ..common import ObjectCollector
from ..duf_reader_context import DUFCollectorContext
from .duf_polyface_to_evo import convert_duf_polyface, combine_duf_polyfaces
from .duf_polyline_to_evo import convert_duf_polyline, combine_duf_polylines
from evo.data_converters.common.utils import get_object_tags

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


CONVERTERS = {dw.Polyface: convert_duf_polyface, dw.Polyline: convert_duf_polyline}

COMBINING_CONVERTERS = {
    dw.Polyface: combine_duf_polyfaces,
    dw.Polyline: combine_duf_polylines,
}


def _get_converter(klass, options, count=1, warn=True):
    converter = next((conv for conv_klass, conv in options.items() if issubclass(klass, conv_klass)), None)
    if converter is None and warn:
        logger.warning(
            f"Unsupported DUF object type: {klass.__name__}, ignoring {count} object{'s' if count > 1 else ''}."
        )
    return converter


def _convert_object_list(klass, objs, data_client, epsg_code, tags):
    if (converter := _get_converter(klass, CONVERTERS, len(objs))) is None:
        return []

    geoscience_objects = []
    for obj in objs:
        geoscience_object = converter(obj, data_client, epsg_code)

        if geoscience_object:
            if geoscience_object.tags is None:
                geoscience_object.tags = {}

            geoscience_object.tags.update(tags)

            geoscience_objects.append(geoscience_object)
    return geoscience_objects


def _convert_and_combine_duf_objects(
    collector: ObjectCollector, data_client: ObjectDataClient, epsg_code: int, tags: dict[str, str]
):
    geoscience_objects = []
    for layer, objs in collector.get_objects_with_category_by_layer(dw.Category.ModelEntities).items():
        layer_by_type = defaultdict(list)
        for obj in objs:
            layer_by_type[type(obj)].append(obj)
        layer_converter = None

        # Try and find a single converter for the layer
        for klass, _ in layer_by_type.items():
            converter = _get_converter(klass, COMBINING_CONVERTERS, warn=False)
            if converter is None or (layer_converter is not None and converter is not layer_converter):
                # Either no converter found, or multiple converters found for the layer
                layer_converter = None
                break
            layer_converter = converter

        if layer_converter is None:
            # Multiple types or non-combinable types, don't combine layer
            for klass, objs in layer_by_type.items():
                geoscience_objects.extend(_convert_object_list(klass, objs, data_client, epsg_code, tags))
        else:
            geoscience_object = layer_converter(objs, data_client, epsg_code)

            if geoscience_object:
                if geoscience_object.tags is None:
                    geoscience_object.tags = {}
                geoscience_object.tags.update(tags)

                geoscience_objects.append(geoscience_object)
    return geoscience_objects


def _convert_duf_objects(
    collector: ObjectCollector, data_client: ObjectDataClient, epsg_code: int, tags: dict[str, str]
):
    geoscience_objects = []
    for klass, objs in collector.get_objects_with_category_by_type(dw.Category.ModelEntities).items():
        geoscience_objects.extend(_convert_object_list(klass, objs, data_client, epsg_code, tags))
    return geoscience_objects


def convert_duf(
    filepath: str,
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    combine_objects_in_layers: bool = False,
    upload_path: str = "",
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts a DUF file into Geoscience Objects.

    :param filepath: Path to the DUF file.
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param combine_objects_in_layers: (Optional) If True, objects in the same layer will be combined if possible.
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

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing objects will be skipped due to missing hub_url.")
        publish_objects = False

    had_stage = ("Stage" in tags) if tags is not None else False
    tags = get_object_tags(os.path.basename(filepath), "DUF", tags)
    tags["Category"] = "ModelEntities"
    if not had_stage:
        tags.pop("Stage", None)

    with DUFCollectorContext(filepath) as context:
        collector: ObjectCollector = context.collector

    if not combine_objects_in_layers:
        geoscience_objects = _convert_duf_objects(collector, data_client, epsg_code, tags)
    else:
        geoscience_objects = _convert_and_combine_duf_objects(collector, data_client, epsg_code, tags)

    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path
        )

    return objects_metadata if objects_metadata else geoscience_objects
