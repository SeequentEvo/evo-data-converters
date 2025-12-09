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
import os.path
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Generator, Optional, TypeAlias

import vtk
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1
from vtk.util.data_model import ImageData, RectilinearGrid, UnstructuredGrid  # Override classes from vtk

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_context,
    
)
from evo.data_converters.common.utils import get_object_tags
from evo.data_converters.common.generate_paths import generate_paths
from evo.common import IContext
from evo.objects import ObjectReference
from evo.objects.data import ObjectMetadata
from evo.objects.typed.base import BaseObjectData, BaseObject

from .exceptions import VTKConversionError, VTKImportError
from .vtk_image_data_to_evo import convert_vtk_image_data
from .vtk_rectilinear_grid_to_evo import convert_vtk_rectilinear_grid
# from .vtk_unstructured_grid_to_evo import convert_vtk_unstructured_grid

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def _get_leaf_objects(data_object: vtk.vtkDataSet, name: str) -> Generator[tuple[str, vtk.vtkDataObject], None, None]:
    if isinstance(data_object, vtk.vtkMultiBlockDataSet):
        for i in range(data_object.GetNumberOfBlocks()):
            child_name = data_object.GetMetaData(i).Get(vtk.vtkCompositeDataSet.NAME())
            if child_name is None:
                child_name = f"{name}_{i}"
            yield from _get_leaf_objects(data_object.GetBlock(i), child_name)
    else:
        yield name, data_object


def _get_vtk_data_objects(filepath: str) -> list[tuple[str, vtk.vtkDataObject]]:
    xml_reader = vtk.vtkXMLGenericDataObjectReader()
    xml_reader.SetFileName(filepath)
    xml_reader.Update()
    data_object = xml_reader.GetOutput()
    if not data_object:
        raise VTKImportError(f"Failed to read data object from {filepath}")
    return list(_get_leaf_objects(data_object, Path(filepath).stem))


ConverterFunction: TypeAlias = Callable[
    [str, vtk.vtkDataObject, int], BaseObjectData
]

_convert_functions: dict[type[vtk.vtkDataObject], ConverterFunction] = {
    vtk.vtkImageData: convert_vtk_image_data,
    ImageData: convert_vtk_image_data,
    vtk.vtkUniformGrid: convert_vtk_image_data,
    vtk.vtkStructuredPoints: convert_vtk_image_data,
    vtk.vtkRectilinearGrid: convert_vtk_rectilinear_grid,
    RectilinearGrid: convert_vtk_rectilinear_grid,
    # vtk.vtkUnstructuredGrid: convert_vtk_unstructured_grid,
    # UnstructuredGrid: convert_vtk_unstructured_grid,
}


def extract_vtk(filepath: str, epsg_code: int, extra_tags: dict[str, str] | None=None) -> list[BaseObjectData]:
    """Extract data from a VTK file without publishing it to Geoscience Objects.

    :param filepath: Path to the VTK file.
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object
    :return: List of (name, BaseObjectData) tuples.
    :raise VTKImportError: If the VTK file could not be read.
    """
    data_objects = _get_vtk_data_objects(filepath)
    data_list = []

    tags = get_object_tags(os.path.basename(filepath), "VTK", extra_tags)
    for name, data_object in data_objects:
        convert_function = _convert_functions.get(type(data_object))
        if convert_function is None:
            logger.warning(f"{type(data_object).__name__} data object are not supported.")
            continue
        try:
            data = convert_function(name, data_object, epsg_code)
            if tags:
                old_tags = data.tags or {}
                data = dataclasses.replace(data, tags={**old_tags, **tags})
            data_list.append(data)
        except VTKConversionError as e:
            logger.warning(f"{e}, skipping this grid")
            continue
    return data_list


def convert_vtk(
    filepath: str,
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    overwrite_existing_objects: bool = False,
) -> list[BaseObjectData | ObjectMetadata]:
    """Converts an VTK file into Geoscience Objects.

    :param filepath: Path to the VTK file.
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param upload_path: (Optional) Path objects will be published under.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    Caveats:
    - Only supports XML VTK files

    :return: List of Geoscience Objects, or list of ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    :raise VTKImportError: If the VTK file could not be read.
    """

    publish_objects = True
    geoscience_objects = []

    context = create_context(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing objects will be skipped due to missing hub_url.")
        publish_objects = False

    geoscience_objects = extract_vtk(filepath, epsg_code, tags)
    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = _publish_geoscience_objects(
            context, geoscience_objects, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects


async def _publish_single_geoscience_object(
    context: IContext,
    obj: BaseObjectData,
    obj_path: str,
    overwrite_existing_objects: bool,
) -> ObjectMetadata:
    if overwrite_existing_objects:
        reference = ObjectReference(
            context.get_environment(),
            path=obj_path,
        )
        uploaded_obj = await BaseObject.create_or_replace(
            context=context,
            reference=reference,
            data=obj,
        )
    else:
        uploaded_obj = await BaseObject.create(
            context=context,
            data=obj,
            path=obj_path,
        )
    return uploaded_obj.metadata


def _publish_geoscience_objects(
    context: IContext,
    object_models: list[BaseSpatialDataProperties_V1_0_1],
    path_prefix: str = "",
    overwrite_existing_objects: bool = False,
) -> list[ObjectMetadata]:
    """
    Publishes a list of Geoscience Objects.
    """
    objects_metadata = []
    paths = generate_paths(object_models, path_prefix)

    logger.debug(f"Preparing to publish {len(object_models)} objects to paths: {paths}")
    for obj, obj_path in zip(object_models, paths):
        object_metadata = asyncio.run(
            _publish_single_geoscience_object(context, obj, obj_path, overwrite_existing_objects)
        )
        logger.debug(f"Got object metadata: {object_metadata}")
        objects_metadata.append(object_metadata)

    return objects_metadata
