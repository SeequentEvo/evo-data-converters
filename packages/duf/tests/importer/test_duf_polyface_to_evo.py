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

from os import path
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Crs_V1_0_1_EpsgCode,
)
from evo_schemas.objects import TriangleMesh_V2_1_0

from evo.data_converters.duf import DufCollectorContext, Polyface
from evo.data_converters.duf.importer import convert_duf_polyface


@pytest.fixture(scope="module")
def polyface_obj():
    duf_file = str((Path(__file__).parent.parent / "data" / "polyface.duf").resolve())
    with DufCollectorContext(duf_file) as context:
        return context.collector.get_objects_of_type(Polyface)[0][1]


def test_should_convert_duf_polyface_geometry(polyface_obj, data_client):
    epsg_code = 32650
    triangle_mesh_go = convert_duf_polyface(polyface_obj, data_client, epsg_code)

    expected_triangle_mesh_go = TriangleMesh_V2_1_0(
        name="0_FACELAYER-dwPolyface-1c14ef99-e5e3-4388-bbe6-6120344712b1",  # layer name - type - object guid
        uuid=None,
        coordinate_reference_system=Crs_V1_0_1_EpsgCode(epsg_code=epsg_code),
        bounding_box=triangle_mesh_go.bounding_box,  # Tested later
        triangles=triangle_mesh_go.triangles,  # Tested later
    )
    assert triangle_mesh_go == expected_triangle_mesh_go

    expected_bounding_box = BoundingBox_V1_0_1(
        min_x=0.0,
        max_x=10.0,
        min_y=0.0,
        max_y=10.0,
        min_z=0.0,
        max_z=0.0,
    )
    assert triangle_mesh_go.bounding_box == expected_bounding_box

    vertices_parquet_file = path.join(str(data_client.cache_location), triangle_mesh_go.triangles.vertices.data)
    indices_parquet_file = path.join(str(data_client.cache_location), triangle_mesh_go.triangles.indices.data)

    vertices = pq.read_table(vertices_parquet_file)
    indices = pq.read_table(indices_parquet_file)

    expected_vertices = np.array([[0.0, 0.0, 0.0], [0, 10.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]])
    np.testing.assert_allclose(vertices.to_pandas(), expected_vertices)

    expected_indices = np.array(
        [
            [1, 0, 2],
            [2, 3, 1],
        ]
    )
    np.testing.assert_equal(indices.to_pandas(), expected_indices)
