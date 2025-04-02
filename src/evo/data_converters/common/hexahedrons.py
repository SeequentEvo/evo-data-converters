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

"""
Utility functions for manipulating Evo Hexahedrons
"""

import numpy as np
import numpy.typing as npt
import pyarrow as pa
from evo_schemas.components import Hexahedrons_V1_1_0_Indices as HexahedronsIndices
from evo_schemas.components import Hexahedrons_V1_1_0_Vertices as HexahedronsVertices
from evo_schemas.components import OneOfAttribute_V1_1_0 as OneOfAttribute

from evo.objects.utils.data import ObjectDataClient


def build_vertices(vertices: npt.NDArray[np.float64], data_client: ObjectDataClient) -> HexahedronsVertices:
    """Build a HexahedronsVertices object containing the grid vertices.

    :param vertices: an n x 3 array of cell vertex coordinates (x, y, z)
    :param data_client: ObjectDataClient used to create the HexahedronsVertices object

    :return: An Evo HexahedronsVertices object

    """
    schema = pa.schema(
        [
            ("x", pa.float64()),
            ("y", pa.float64()),
            ("z", pa.float64()),
        ]
    )
    table = pa.Table.from_arrays([vertices[:, 0], vertices[:, 1], vertices[:, 2]], schema=schema)
    go = data_client.save_table(table)
    return HexahedronsVertices.from_dict(go)


def build_indices(
    indices: npt.NDArray[np.intp], data_client: ObjectDataClient, attributes: OneOfAttribute
) -> HexahedronsIndices:
    """Build an Evo HexahedronIndices, containing the indexes for the cell vertices
    and the associated attributes

    :param indices: a n by 8 array of indexes into vertices ,specifying the 8 corner points of each cell
    :param data_client: ObjectDataClient used to create the HexahedronsIndices object
    :param attributes: List of attributes

    :return: An Evo HexahedronsIndices object

    """
    schema = pa.schema(
        [
            ("n0", pa.uint64()),
            ("n1", pa.uint64()),
            ("n2", pa.uint64()),
            ("n3", pa.uint64()),
            ("n4", pa.uint64()),
            ("n5", pa.uint64()),
            ("n6", pa.uint64()),
            ("n7", pa.uint64()),
        ]
    )
    table = pa.Table.from_arrays(
        [
            indices[:, 0],
            indices[:, 1],
            indices[:, 2],
            indices[:, 3],
            indices[:, 4],
            indices[:, 5],
            indices[:, 6],
            indices[:, 7],
        ],
        schema=schema,
    )
    go = data_client.save_table(table)
    hi = HexahedronsIndices.from_dict(go)
    hi.attributes = attributes
    return hi
