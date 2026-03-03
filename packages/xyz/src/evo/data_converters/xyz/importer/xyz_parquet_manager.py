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
import numpy.typing as npt
import numpy as np


def save_array_to_parquet(data_2d: npt.NDArray[np.float64] , output_path) -> None:

    # Create a table with 3 columns (x, y, z), each float64
    table = pa.table({
        "x": pa.array(data_2d[:, 0], type=pa.float64()),
        "y": pa.array(data_2d[:, 1], type=pa.float64()),
        "z": pa.array(data_2d[:, 2], type=pa.float64()),
    })

    pq.write_table(
        table,
        output_path,
        compression="gzip",
        version="2.4",
        flavor="none",
        data_page_size=None,
        encryption_properties=None,
    )