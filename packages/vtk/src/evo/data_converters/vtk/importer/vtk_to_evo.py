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
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Generator, Optional, TypeAlias

import vtk
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1
from vtk.util.data_model import ImageData, RectilinearGrid, UnstructuredGrid  # Override classes from vtk

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)
from evo.objects.data import ObjectMetadata
from evo.objects.utils import ObjectDataClient

from .exceptions import VTKConversionError, VTKImportError
from .vtk_image_data_to_evo import convert_vtk_image_data
from .vtk_rectilinear_grid_to_evo import convert_vtk_rectilinear_grid
from .vtk_unstructured_grid_to_evo import convert_vtk_unstructured_grid

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


def _get_data_objects(filepath: str) -> list[tuple[str, vtk.vtkDataObject]]:
    xml_reader = vtk.vtkXMLGenericDataObjectReader()
    xml_reader.SetFileName(filepath)
    xml_reader.Update()
    data_object = xml_reader.GetOutput()
    if not data_object:
        raise VTKImportError(f"Failed to read data object from {filepath}")
    return list(_get_leaf_objects(data_object, Path(filepath).stem))


ConverterFunction: TypeAlias = Callable[
    [str, vtk.vtkDataObject, ObjectDataClient, int], BaseSpatialDataProperties_V1_0_1
]

_convert_functions: dict[type[vtk.vtkDataObject], ConverterFunction] = {
    vtk.vtkImageData: convert_vtk_image_data,
    ImageData: convert_vtk_image_data,
    vtk.vtkUniformGrid: convert_vtk_image_data,
    vtk.vtkStructuredPoints: convert_vtk_image_data,
    vtk.vtkRectilinearGrid: convert_vtk_rectilinear_grid,
    RectilinearGrid: convert_vtk_rectilinear_grid,
    vtk.vtkUnstructuredGrid: convert_vtk_unstructured_grid,
    UnstructuredGrid: convert_vtk_unstructured_grid,
}


def convert_vtk(
    filepath: str,
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    overwrite_existing_objects: bool = False,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
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

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing objects will be skipped due to missing hub_url.")
        publish_objects = False

    data_objects = _get_data_objects(filepath)
    for name, data_object in data_objects:
        try:
            convert_function = _convert_functions.get(type(data_object))
            if convert_function is None:
                logger.warning(f"{type(data_object).__name__} data object are not supported.")
                continue
            geoscience_object = convert_function(name, data_object, data_client, epsg_code)
        except VTKConversionError as e:
            logger.warning(f"{e}, skipping this grid")
            continue

        if geoscience_object.tags is None:
            geoscience_object.tags = {}
        geoscience_object.tags["Source"] = f"{os.path.basename(filepath)} (via Evo Data Converters)"
        geoscience_object.tags["Stage"] = "Experimental"
        geoscience_object.tags["InputType"] = "VTK"

        # Add custom tags
        if tags:
            geoscience_object.tags.update(tags)

        geoscience_objects.append(geoscience_object)

    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = publish_geoscience_objects(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects
