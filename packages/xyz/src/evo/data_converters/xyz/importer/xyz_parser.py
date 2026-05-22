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
from evo_schemas.elements.float_array_1 import FloatArray1_V1_0_1
from evo_schemas.components import BoundingBox_V1_0_1
from evo_schemas.components.continuous_attribute import ContinuousAttribute_V1_1_0
from evo_schemas.components.nan_continuous import NanContinuous_V1_0_1

from .xyz_reader import read_xyz
from .xyz_parquet_manager import save_array_to_parquet, save_1d_array_to_parquet


def parse_xyz_file(
    filepath: str,
    data_client: ObjectDataClient,
    x_index: int = -1,
    y_index: int = -1,
    z_index: int = -1,
    data_index: int = -1,
) -> Pointset_V1_3_0:
    name = os.path.basename(filepath)
    filename_hash = hashlib.sha256(os.path.basename(filepath).encode()).hexdigest().lower()

    xyz = read_xyz(filepath, x_index=x_index, y_index=y_index, z_index=z_index, data_index=data_index)
    parquet_path = os.path.join(str(data_client.cache_location), filename_hash)
    save_array_to_parquet(xyz.points, parquet_path)

    min_x_val = float(np.min(xyz.points[:, 0]))
    max_x_val = float(np.max(xyz.points[:, 0]))
    min_y_val = float(np.min(xyz.points[:, 1]))
    max_y_val = float(np.max(xyz.points[:, 1]))
    min_z_val = float(np.min(xyz.points[:, 2]))
    max_z_val = float(np.max(xyz.points[:, 2]))

    bb = BoundingBox_V1_0_1(
        min_x=min_x_val, min_y=min_y_val, min_z=min_z_val, max_x=max_x_val, max_y=max_y_val, max_z=max_z_val
    )
    floatArr = FloatArray3_V1_0_1(data=filename_hash, length=xyz.points.shape[0])

    attributes = None
    if len(xyz.data) > 0:
        data_hash = hashlib.sha256((os.path.basename(filepath) + "_data").encode()).hexdigest().lower()
        data_parquet_path = os.path.join(str(data_client.cache_location), data_hash)
        save_1d_array_to_parquet(xyz.data, data_parquet_path)
        data_values = FloatArray1_V1_0_1(data=data_hash, length=len(xyz.data))
        attributes = [
            ContinuousAttribute_V1_1_0(
                name="data",
                key="data",
                nan_description=NanContinuous_V1_0_1(values=[-1.0e32]),
                values=data_values,
            )
        ]

    location = Pointset_V1_3_0_Locations(coordinates=floatArr, attributes=attributes)

    pointset = Pointset_V1_3_0(
        name=name,
        uuid=None,
        description=None,
        bounding_box=bb,
        coordinate_reference_system="unspecified",
        locations=location,
    )

    return pointset
