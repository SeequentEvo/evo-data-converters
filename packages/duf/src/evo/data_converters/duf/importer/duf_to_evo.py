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
from collections import defaultdict
from typing import TYPE_CHECKING, Optional, Any
import warnings

import evo.logging
from evo.objects.utils import ObjectDataClient

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
    crs_from_epsg_code,
    crs_from_any,
)
from evo.objects.data import ObjectMetadata
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1, Crs_V1_0_1

import evo.data_converters.duf.common.deswik_types as dw
from .utils import ResolveObjectNameOption, ResolveObjectNameType, ConvertOptions
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


def _validate_entity(entity: dw.Polyface | dw.Polyline) -> bool:
    if isinstance(entity, dw.Polyline):
        if entity.VertexList is None:
            logger.warning(f"Polyline {entity.Label} has no vertices, skipping.")
            return False
        else:
            return True
    elif isinstance(entity, dw.Polyface):
        if entity.FaceList is None or entity.VertexList is None:
            logger.warning(f"Polyface {entity.Label} has no faces or vertices, skipping.")
            return False
        else:
            return True

    return False


def _get_converter(klass, options, count=1, warn=True):
    converter = next((conv for conv_klass, conv in options.items() if issubclass(klass, conv_klass)), None)
    if converter is None and warn:
        logger.warning(
            f"Unsupported DUF object type: {klass.__name__}, ignoring {count} object{'s' if count > 1 else ''}."
        )
    return converter


def _convert_object_list(klass, objs, data_client, crs: Crs_V1_0_1, tags, options: ConvertOptions):
    if (converter := _get_converter(klass, CONVERTERS, len(objs))) is None:
        return []

    objs = [obj for obj in objs if _validate_entity(obj)]

    logger.info(f"Converting {len(objs)} objects individually using {converter}.")

    geoscience_objects = []
    for i, obj in enumerate(objs):
        geoscience_object = converter(obj, data_client, crs, options)

        if geoscience_object:
            if geoscience_object.tags is None:
                geoscience_object.tags = {}

            geoscience_object.tags.update(tags)

            geoscience_objects.append(geoscience_object)

        if i % 100 == 0:
            logger.info(f"Converted {i} objects")
    return geoscience_objects


def _convert_and_combine_duf_objects(
    collector: ObjectCollector,
    data_client: ObjectDataClient,
    crs: Crs_V1_0_1,
    tags: dict[str, str],
    options: ConvertOptions,
):
    geoscience_objects = []
    for layer, objs in collector.get_objects_with_category_by_layer(dw.Category.ModelEntities).items():
        layer_by_type = defaultdict(list)
        for obj in objs:
            layer_by_type[type(obj)].append(obj)

        objs_to_convert_as_group: dict[Any, list] = {}

        # Try and find a single converter for the layer
        for klass, layer_type_objs in layer_by_type.items():
            converter = _get_converter(klass, COMBINING_CONVERTERS, warn=False)
            if converter is None:
                continue

            valid_objs = [obj for obj in layer_type_objs if _validate_entity(obj)]

            objs_so_far = objs_to_convert_as_group.setdefault(converter, [])
            objs_so_far.extend(valid_objs)

        for layer_converter, objs_to_convert in objs_to_convert_as_group.items():
            if len(objs_to_convert) == 0:
                logger.warning(f"Skipping conversion for converter {layer_converter} because there are 0 entities")
                continue
            logger.info(f"Converting and combining {len(objs_to_convert)} objects using {layer_converter}.")
            geoscience_object = layer_converter(objs_to_convert, data_client, crs, options)

            if geoscience_object:
                if geoscience_object.tags is None:
                    geoscience_object.tags = {}
                geoscience_object.tags.update(tags)

                geoscience_objects.append(geoscience_object)
    return geoscience_objects


def _convert_duf_objects(
    collector: ObjectCollector,
    data_client: ObjectDataClient,
    crs: Crs_V1_0_1,
    tags: dict[str, str],
    options: ConvertOptions,
):
    geoscience_objects = []
    for klass, objs in collector.get_objects_with_category_by_type(dw.Category.ModelEntities).items():
        geoscience_objects.extend(_convert_object_list(klass, objs, data_client, crs, tags, options))
    return geoscience_objects


async def convert_duf(
    filepath: str,
    epsg_code: Optional[int] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    combine_objects_in_layers: bool = False,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
    *,
    coordinate_reference_system: str | int | None = None,
    resolve_object_name: ResolveObjectNameOption | ResolveObjectNameType = ResolveObjectNameOption.DEFAULT,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts a DUF file into Geoscience Objects.

    :param filepath: Path to the DUF file.
    :param epsg_code: (Optional, deprecated) Integer EPSG code for the coordinate reference system. Use ``coordinate_reference_system`` instead.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param combine_objects_in_layers: (Optional) If True, objects in the same layer will be combined if possible.
    :param upload_path: (Optional) Path objects will be published under.
    :param publish_objects: (Optional) Set False to return rather than publish objects.
    :param overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the upload_path.
    :param coordinate_reference_system: (Optional) Coordinate reference system: an integer or string EPSG code (e.g. ``2193`` or ``"EPSG:2193"``), an OGC WKT string, or ``None`` for unspecified.
    :param resolve_object_name: (Optional) See description below

    Both epsg_code and coordinate_reference_system can't be provided, otherwise a ValueError will be raised. If neither is provided, the CRS will be set to "unspecified".

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    If problems are encountered while loading the DUF file, these will be logged as warnings.

    `resolve_object_name` controls how names are generated for any Evo objects that get generated. The way it works
    depends on the `combine_objects_in_layers` options.
    - DEFAULT and combine_objects_in_layers=True -> Object gets the name of the imediately enclosing Deswik layer
    - CONCATENATE and combine_objects_in_layers=True -> As above, but the name includes all layers in the hierarchy
    - DEFAULT and combine_objects_in_layers=False -> Each object gets the name of the Deswik entity
    - CONCATENATE and combine_objects_in_layers=False -> As above, but the names include all layers in the hierarchy
    - A custom resolver can also be provided

    :return: List of Geoscience Objects, or list of ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    """
    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )

    had_stage = ("Stage" in tags) if tags is not None else False
    tags = get_object_tags(os.path.basename(filepath), "DUF", tags)
    tags["Category"] = "ModelEntities"
    if not had_stage:
        tags.pop("Stage", None)

    if epsg_code is not None:
        if coordinate_reference_system is not None:
            raise ValueError("Both epsg_code and coordinate_reference_system were provided. Please provide only one.")
        warnings.warn(
            "The epsg_code parameter is deprecated, please use coordinate_reference_system instead.", DeprecationWarning
        )
        crs = crs_from_epsg_code(epsg_code)
    else:
        crs = crs_from_any(coordinate_reference_system)

    with DUFCollectorContext(filepath) as context:
        collector: ObjectCollector = context.collector

    options = ConvertOptions(
        combined=combine_objects_in_layers,
        resolve_object_name=resolve_object_name,
    )
    if not combine_objects_in_layers:
        geoscience_objects = _convert_duf_objects(collector, data_client, crs, tags, options)
    else:
        geoscience_objects = _convert_and_combine_duf_objects(collector, data_client, crs, tags, options)

    objects_metadata = None
    if publish_objects:
        logger.debug(f"Publishing {len(geoscience_objects)} Geoscience Objects")
        objects_metadata = await publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
