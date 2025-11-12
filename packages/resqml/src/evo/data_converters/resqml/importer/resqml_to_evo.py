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
from typing import TYPE_CHECKING, Optional

import resqpy.well as rqw
from evo_schemas import DownholeIntervals_V1_0_1 as DownholeIntervals
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1
from evo_schemas.objects import TriangleMesh_V2_0_0 as TriangleMesh
from evo_schemas.objects import UnstructuredHexGrid_V1_1_0 as UnstructuredHexGrid
from resqpy.grid import Grid
from resqpy.model import Model, ModelContext
from resqpy.surface import Surface

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects_sync,
)
from evo.data_converters.resqml import convert_size
from evo.data_converters.resqml.utils import estimate_corner_points_size
from evo.objects.data import ObjectMetadata
from evo.objects.utils import ObjectDataClient

from ._downhole_intervals_to_evo import convert_downhole_intervals_for_trajectory
from ._grid_converter import convert_grid
from ._surface_converter import convert_surface
from .conversion_options import RESQMLConversionOptions

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def convert_resqml(
    filepath: str,
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    tags: Optional[dict[str, str]] = None,
    upload_path: str = "",
    options: RESQMLConversionOptions = RESQMLConversionOptions(),
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata]:
    """Converts a RESQML file into Evo Geoscience Objects.
    service_manager_widget: ServiceManagerWidget = None,
    upload_path: str = "",

    :param filepath: Path to the RESQML file.
    :param evo_workspace_metadata: Evo Workspace metadata required for creating an ObjectAPIClient and ObjectDataClient.
    :param epsg_code: The EPSG code to use when creating a Coordinate Reference System object.
    :param evo_workspace_metadata: (Optional) Evo workspace metadata.
    :param service_manager_widget: (Optional) Service Manager Widget for use in jupyter notebooks.
    :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
    :param options: (Optional) Import and conversion options for the RESQML file, if not supplied the default options are used.
    :param upload_path: (Optional) Path objects will be published under.
    :publish_objects: (Optional) Set False to return rather than publish objects.
    :overwrite_existing_objects: (Optional) Set True to overwrite any existing object at the upload_path.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:
    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.


    :return: List of Geoscience Objects, or list of ObjectMetadata if published.

    :raise MissingConnectionDetailsError: If no connections details could be derived.
    :raise ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget present.
    :raise FileNotFoundError: If the input file can not be opened.
    """

    geoscience_objects = []
    go_objects = []

    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )
    if evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        logger.debug("Publishing objects will be skipped due to missing hub_url.")
        publish_objects = False

    with ModelContext(filepath) as model:
        go_objects.extend(_convert_grids(model, data_client, epsg_code, options))
        go_objects.extend(_convert_surfaces(model, data_client, epsg_code, options))
        go_objects.extend(_convert_downhole_intervals(model, data_client, epsg_code, options))

        for geoscience_object in go_objects:
            if geoscience_object.tags is None:
                geoscience_object.tags = {}

            geoscience_object.tags["Source"] = f"{os.path.basename(filepath)} (via Evo Data Converters)"
            geoscience_object.tags["Stage"] = "Experimental"
            geoscience_object.tags["InputType"] = "RESQML"

            # Add custom tags
            if tags:
                geoscience_object.tags.update(tags)

            geoscience_objects.append(geoscience_object)

    objects_metadata = None
    if publish_objects:
        logger.debug("Publishing Geoscience Objects")
        objects_metadata = publish_geoscience_objects_sync(
            geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
        )

    return objects_metadata if objects_metadata else geoscience_objects


def _convert_grids(
    model: Model, data_client: ObjectDataClient, epsg_code: int, options: RESQMLConversionOptions
) -> list[UnstructuredHexGrid]:
    """Convert the regular IJK grids in the Model to UnstructuredHexGrids

    :param model:       The resqpy model, representation of the RESQML file
    :param data_client: Wrapper around data upload and download functionality for geoscience objects.
    :param epsg_code:   The epsg code to be used on grids without a CoordinateReference System
    :param options:     Import and conversion options for the RESQML file.

    :return: list of UnstructuredHexGrid objects
    """

    grids = []
    uuids = model.uuids(obj_type="IjkGridRepresentation")
    for uuid in uuids:
        grid = Grid(model, uuid=uuid)
        # The corner_Points array needed to calculate the cell geometry
        # can get very large. So check it against a threshold
        estimate = estimate_corner_points_size(grid)
        if estimate > options.memory_threshold:
            logger.warning(
                "Ignoring grid %s %s, as the size of the corner_points array would be %s, which exceeds the threshold of %s"
                % (
                    grid.citation_title,
                    str(grid.uuid),
                    convert_size(estimate),
                    convert_size(options.memory_threshold),
                )
            )
            continue
        go = convert_grid(model, grid, epsg_code, options, data_client)
        if go is not None:
            grids.append(go)
    return grids


def _convert_downhole_intervals(
    model: Model,
    data_client: ObjectDataClient,
    epsg_code: Optional[int] = None,
    options: Optional[RESQMLConversionOptions] = None,
) -> list[DownholeIntervals]:
    """
    Convert downhole intervals in a model to Evo DownholeIntervals objects. Based
    on the wellbore trajectories found in the model.

    :param model: The resqpy model to convert
    :param data_client: The Evo data client to use
    :param epsg_code: Optional. The EPSG code to use for the CRS, else the model CRS is used
    :param options: Optional, import and conversion options for the RESQML file

    :return: A list of Evo DownholeIntervals objects
    """
    stem = Path(model.epc_file or "None").stem
    downhole_intervals = []
    uuids = model.uuids(obj_type="WellboreTrajectoryRepresentation")
    for i, uuid in enumerate(uuids, start=1):
        trajectory = rqw.Trajectory(model, uuid=uuid)
        prefix = f"{stem}/downhole_intervals/{i}/"
        go = convert_downhole_intervals_for_trajectory(
            model=model,
            trajectory=trajectory,
            prefix=prefix,
            data_client=data_client,
            epsg_code=epsg_code,
            options=options,
        )
        if go is not None:
            downhole_intervals += go
    return downhole_intervals


def _convert_surfaces(
    model: Model, data_client: ObjectDataClient, epsg_code: int, options: RESQMLConversionOptions
) -> list[TriangleMesh]:
    """Convert TriangulatedSetRepresentations in the Model to TriangleMeshes

    :param model:       The resqpy model, representation of the RESQML file.
    :param data_client: Wrapper around data upload and download functionality for geoscience objects.
    :param epsg_code:   The EPSG code to be used on grids without a coordinate reference system.
    :param options:     Import and conversion options for the RESQML file.

    :return: list of TriangleMeshes
    """

    surfaces = []
    uuids = model.uuids(obj_type="TriangulatedSetRepresentation")
    for uuid in uuids:
        surface = Surface(model, uuid=uuid)
        go = convert_surface(model, surface, epsg_code, options, data_client)
        if go is not None:
            surfaces.append(go)
    return surfaces
