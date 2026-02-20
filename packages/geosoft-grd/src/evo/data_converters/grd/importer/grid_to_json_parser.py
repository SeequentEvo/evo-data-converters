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

import math
import hashlib
import os

from evo.objects.utils.data import ObjectDataClient
from evo_schemas.objects.regular_2d_grid import Regular2DGrid_V1_2_0
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    ContinuousAttribute_V1_1_0,
    Crs_V1_0_1_EpsgCode,
    Crs_V1_0_1_OgcWkt,
    NanContinuous_V1_0_1,
    Rotation_V1_1_0
)
from evo_schemas.elements import FloatArray1_V1_0_1

from . import loadgrid as GridLoader
from . import load_projection as ProjectionReader

from . import array_to_parquet_parser as ParquetParser

class GRID_PARSER:
    def __init__(self, gridPath : str, client_data: ObjectDataClient):
        self.gridPath = gridPath
        self.client_data = client_data

    def parse_grid(self) -> Regular2DGrid_V1_2_0:
        grid = GridLoader.load_grid(self.gridPath)
        gridGiPath = self.gridPath + ".gi"
        projection = ProjectionReader.load_projection(gridGiPath)

        # Save grid data to parquet (flattened row-major order)
        filename_hash = hashlib.sha256(os.path.basename(self.gridPath).encode()).hexdigest().lower()
        parquet_path = os.path.join(str(self.client_data.cache_location), filename_hash)
        ParquetParser.save_array_to_parquet(grid.data, parquet_path)

        #Save the schema JSON file
        bounding_box = self.__get_bounding_box(grid)

        if(projection.authority_struc is not None):
            if(projection.authority_struc.szAuthority == "EPSG"):
                coordinate_reference_system =  Crs_V1_0_1_EpsgCode(epsg_code = projection.authority_struc.lAuthoritativeID)
            else:
                coordinate_reference_system = Crs_V1_0_1_OgcWkt(ogc_wkt = projection.wkt)
        else:
            coordinate_reference_system = None

        rot_value = grid.rotation if grid.rotation == 0 else 360 - grid.rotation
        rotation = Rotation_V1_1_0(dip=0.0, dip_azimuth=rot_value, pitch=0.0)

        name, extension = os.path.splitext(os.path.basename(self.gridPath))

        # Create the cell attribute for the grid data
        cell_attribute = ContinuousAttribute_V1_1_0(
            name="2d-grid-data-continuous",
            key=filename_hash,
            nan_description=NanContinuous_V1_0_1(
                values=[-1.0000000331813535e+32, -1e+32]
            ),
            values=FloatArray1_V1_0_1(
                data=filename_hash,
                data_type="float64",
                length=grid.nx * grid.ny,
                width=1
            )
        )

        grid_schema = Regular2DGrid_V1_2_0(
            name=name,
            uuid=None,
            bounding_box=bounding_box,
            coordinate_reference_system=coordinate_reference_system,
            origin=[grid.x_origin, grid.y_origin, 0.0],
            size=[grid.nx, grid.ny],
            cell_size=[grid.dx, grid.dy],
            rotation=rotation,
            cell_attributes=[cell_attribute],
            vertex_attributes=None
        )

        return grid_schema

    def __get_bounding_box(self, grid : GridLoader.Img)->BoundingBox_V1_0_1:
        cos = math.cos(grid.rotation * math.pi / 180)
        sin = math.sin(grid.rotation * math.pi / 180)
        dx = (grid.nx - 1) * grid.dx
        dy = (grid.ny - 1) * grid.dy
        boundary_min_x = grid.x_origin
        boundary_min_y = grid.y_origin
        boundary_max_x = grid.x_origin
        boundary_max_y = grid.y_origin
        x_elements = []
        y_elements = []
        y_elements.append(grid.y_origin);
        y_elements.append(grid.y_origin + (dx * sin))
        y_elements.append(y_elements[1] + (dy * cos))
        y_elements.append(grid.y_origin + (dy * cos))

        x_elements.append(grid.x_origin);
        x_elements.append(grid.x_origin + (dx * cos))
        x_elements.append(x_elements[1] - (dy * sin))
        x_elements.append(grid.x_origin - (dy * sin))

        for i in range(4):
            if(x_elements[i] < boundary_min_x):
                boundary_min_x = x_elements[i]
            if(x_elements[i] > boundary_max_x):
                boundary_max_x = x_elements[i]
            if(y_elements[i] < boundary_min_y):
                boundary_min_y = y_elements[i]
            if(y_elements[i] > boundary_max_y):
                boundary_max_y = y_elements[i]
        
        return BoundingBox_V1_0_1(min_x=boundary_min_x, 
                           max_x=boundary_max_x, 
                           min_y=boundary_min_y, 
                           max_y=boundary_max_y, 
                           min_z=0.0, 
                           max_z=0.0)
