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
import re
from typing import Optional

import numpy
import pyarrow as pa
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0,
    Crs_V1_0_1_OgcWkt,
    NanContinuous_V1_0_1,
    Rotation_V1_1_0,
)
from evo_schemas.elements import FloatArray1_V1_0_1
from evo_schemas.objects import Tensor3DGrid_V1_2_0, Tensor3DGrid_V1_2_0_GridCells3D

import evo.logging
from evo.data_converters.common import crs_from_epsg_code
from evo.data_converters.common.utils import get_object_tags, grid_bounding_box

from evo.data_converters.ubc.importer.ubc_reader import UBCMeshFileImporter, UBCPropertyFileImporter
from evo.objects.utils.data import ObjectDataClient

logger = evo.logging.getLogger("data_converters")


def _derive_epsg_from_wkt(wkt: str) -> Optional[int]:
    """
    Attempt to derive an EPSG code from a WKT string using regex pattern matching.

    Supports common coordinate systems like:
    - GDA94/MGA zones
    - GDA2020/MGA zones
    - WGS84/UTM zones
    - NAD83/UTM zones

    :param wkt: WKT projection string
    :return: EPSG code if found, None otherwise
    """
    if not wkt:
        return None

    name_patterns = [
        (
            r"GDA94\s*/\s*MGA\s*zone\s*(\d{1,2})",
            lambda zone: 28300 + zone,
        ),
        (
            r"GDA2020\s*/\s*MGA\s*zone\s*(\d{1,2})",
            lambda zone: 7800 + zone,
        ),
        (
            r"WGS\s*84\s*/\s*UTM\s*zone\s*(\d{1,2})\s*([NS])",
            lambda zone, hemi: (32600 if hemi == "N" else 32700) + zone,
        ),
        (
            r"NAD83\s*/\s*UTM\s*zone\s*(\d{1,2})\s*N",
            lambda zone: 26900 + zone,
        ),
    ]

    for pattern, resolver in name_patterns:
        match = re.search(pattern, wkt, flags=re.IGNORECASE)
        if not match:
            continue

        groups = match.groups()
        try:
            if len(groups) == 1:
                zone = int(groups[0])
                return resolver(zone)
            zone = int(groups[0])
            hemi = groups[1].upper()
            return resolver(zone, hemi)
        except (TypeError, ValueError):
            continue

    return None


def _create_continuous_attributes(
    data_client: ObjectDataClient, label_to_values: dict
) -> list[ContinuousAttribute_V1_1_0]:
    cell_attributes = []
    for name, values in label_to_values.items():
        table = pa.table({"values": values})
        cell_attributes.append(
            ContinuousAttribute_V1_1_0(
                name=name,
                key=name,
                nan_description=NanContinuous_V1_0_1(values=[]),
                values=FloatArray1_V1_0_1(**data_client.save_table(table)),
            )
        )
    return cell_attributes


def _handle_ubc_files_list(files_path: list[str]) -> tuple[str, list[str]]:
    ubc_mesh_file: str | None = None
    ubc_numeric_values_files: list[str] = []
    for f in files_path:
        if f.endswith(".msh"):
            if ubc_mesh_file:
                raise ValueError("Multiple UBC mesh files provided.")
            ubc_mesh_file = f
        else:  # assuming that all other files are numeric values files
            ubc_numeric_values_files.append(f)

    if not ubc_mesh_file:
        raise ValueError("No UBC mesh file provided.")

    return ubc_mesh_file, ubc_numeric_values_files


def get_geoscience_object_from_ubc(
    data_client: ObjectDataClient, files_path: list[str], epsg_code: int = -1, tags: Optional[dict[str, str]] = None
) -> Tensor3DGrid_V1_2_0:
    ubc_mesh_file, ubc_numeric_values_files = _handle_ubc_files_list(files_path)
    name = os.path.splitext(os.path.basename(ubc_mesh_file))[0]
    origin, spacings, size_of_dimensions, wkt_string = UBCMeshFileImporter(ubc_mesh_file).execute()

    # Determine the CRS to use
    coordinate_reference_system = None

    if epsg_code > 0:
        # Use provided EPSG code
        logger.debug(f"Using provided EPSG code: {epsg_code}")
        coordinate_reference_system = crs_from_epsg_code(epsg_code)
    elif wkt_string:
        # Try to infer EPSG from WKT
        inferred_epsg = _derive_epsg_from_wkt(wkt_string)
        if inferred_epsg is not None and inferred_epsg > 0:
            logger.debug(f"Inferred EPSG code {inferred_epsg} from WKT string in UBC file")
            coordinate_reference_system = crs_from_epsg_code(inferred_epsg)
        else:
            # Fallback to WKT-based CRS
            logger.debug("Using WKT projection from UBC file (no EPSG code could be inferred)")
            coordinate_reference_system = Crs_V1_0_1_OgcWkt(ogc_wkt=wkt_string)
    else:
        # No EPSG code provided and no WKT string found
        logger.warning(f"No coordinate system found in UBC file '{os.path.basename(ubc_mesh_file)}'")
        coordinate_reference_system = "unspecified"

    n_blocks = size_of_dimensions[0] * size_of_dimensions[1] * size_of_dimensions[2]
    numerical_values = {}
    for value_file in ubc_numeric_values_files:
        values = UBCPropertyFileImporter(value_file).execute(n_blocks, size_of_dimensions)
        numerical_values[os.path.splitext(os.path.basename(value_file))[0]] = values

    bbox = grid_bounding_box(origin, numpy.identity(3), numpy.array([numpy.sum(d) for d in spacings]))
    cell_attributes = _create_continuous_attributes(data_client, numerical_values)

    grid_cells_3d = Tensor3DGrid_V1_2_0_GridCells3D(
        cell_sizes_x=spacings[0].tolist(), cell_sizes_y=spacings[1].tolist(), cell_sizes_z=spacings[2].tolist()
    )

    return Tensor3DGrid_V1_2_0(
        name=name,
        origin=origin.tolist(),
        size=size_of_dimensions,
        grid_cells_3d=grid_cells_3d,
        coordinate_reference_system=coordinate_reference_system,
        bounding_box=bbox,
        rotation=Rotation_V1_1_0(dip_azimuth=0.0, dip=0.0, pitch=0.0),
        cell_attributes=cell_attributes,
        uuid=None,
        tags=get_object_tags(path=os.path.basename(ubc_mesh_file), input_type="UBC", extra_tags=tags),
    )
