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

import pyarrow as pa
import pyarrow.parquet as pq
from . import geosoft_commons as commons


def save_array_to_parquet(data_2d, output_path, data_type) -> None:
    flattened = data_2d.flatten()

    # Create a table with N rows, one double value per row
    parquet_type = __get_parquet_type(data_type)
    table = pa.table({"data": pa.array(flattened, type=parquet_type)})

    pq.write_table(
        table,
        output_path,
        compression="gzip",
        version="2.4",
        flavor="none",
        data_page_size=None,
        encryption_properties=None,
    )


def __get_parquet_type(grid_type):
    if grid_type == commons.GS_LONG:
        return pa.int32()
    elif grid_type == commons.GS_FLOAT:
        return pa.float64()
    else:
        raise ValueError(f"Unsupported grid data type: {grid_type}")
