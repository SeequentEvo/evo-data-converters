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
import hashlib
import numpy as np
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.objects.pointset import Pointset_V1_3_0, Pointset_V1_3_0_Locations
from evo_schemas.elements import FloatArray3_V1_0_1
from evo_schemas.components import BoundingBox_V1_0_1

from .xyz_reader import read_xyz
from .xyz_parquet_manager import save_array_to_parquet


def parse_xyz_file(filepath: str, data_client: ObjectDataClient) -> Pointset_V1_3_0:
    name = os.path.basename(filepath)
    filename_hash = hashlib.sha256(os.path.basename(filepath).encode()).hexdigest().lower()

    points = read_xyz(filepath)
    parquet_path = os.path.join(str(data_client.cache_location), filename_hash)
    save_array_to_parquet(points, parquet_path)

    min_x_val = float(np.min(points[:, 0]))
    max_x_val = float(np.max(points[:, 0]))
    min_y_val = float(np.min(points[:, 1]))
    max_y_val = float(np.max(points[:, 1]))
    min_z_val = float(np.min(points[:, 2]))
    max_z_val = float(np.max(points[:, 2]))

    bb = BoundingBox_V1_0_1(
        min_x=min_x_val, min_y=min_y_val, min_z=min_z_val, max_x=max_x_val, max_y=max_y_val, max_z=max_z_val
    )
    floatArr = FloatArray3_V1_0_1(data=filename_hash, length=points.shape[0])
    location = Pointset_V1_3_0_Locations(coordinates=floatArr)
    pointset = Pointset_V1_3_0(
        name=name,
        uuid=None,
        description=None,
        bounding_box=bb,
        coordinate_reference_system="unspecified",
        locations=location,
    )

    return pointset
