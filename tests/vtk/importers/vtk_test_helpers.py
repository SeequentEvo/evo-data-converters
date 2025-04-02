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

import uuid
from typing import Any

import numpy as np
import pyarrow as pa
import vtk
from vtk.util.numpy_support import numpy_to_vtk

_dtype_names = {
    pa.float64(): "float64",
}


class MockDataClient:
    def __init__(self) -> None:
        self.tables: dict[uuid.UUID, pa.Table] = {}

    def save_table(self, table: pa.Table) -> dict[str, Any]:
        table_id = uuid.uuid4()
        self.tables[table_id] = table
        column = table[0]

        column_types = [_dtype_names.get(col.type, str(col.type)) for col in table]
        if column_types == ["int32", "string"] or column_types == ["int64", "string"]:
            return {
                "data": table_id,
                "length": len(column),
                "keys_data_type": column_types[0],
                "values_data_type": "string",
            }
        if len(set(column_types)) > 1:
            data_type = "/".join(column_types)
        else:
            data_type = column_types[0]

        return {
            "data": table_id,
            "length": len(column),
            "data_type": data_type,
        }


def add_ghost_value(vtk_data: vtk.vtkDataSet, geometry: int, ghost_value: int, index: int = 3) -> None:
    arrays = vtk_data.GetAttributes(geometry)
    ghost_array = np.zeros(vtk_data.GetNumberOfElements(geometry), dtype=np.uint8)
    ghost_array[index] = ghost_value
    vtk_ghost_array = numpy_to_vtk(ghost_array, deep=True)
    vtk_ghost_array.SetName("vtkGhostType")
    arrays.AddArray(vtk_ghost_array)
