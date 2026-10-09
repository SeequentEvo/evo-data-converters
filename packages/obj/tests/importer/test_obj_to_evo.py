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

import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

import pytest
from evo_schemas.components import Crs_V1_0_1_EpsgCode, Crs_V1_0_1_OgcWkt
from evo_schemas.objects import TriangleMesh_V2_2_0
from pyproj import CRS

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)
from evo.data_converters.obj.importer.obj_to_evo import convert_obj

this_dir = Path(__file__).parent

_WKT2_EXAMPLE = """\
GEOGCRS["WGS 84",
    DATUM["World Geodetic System 1984",
        ELLIPSOID["WGS 84", 6378137, 298.257223563,
            LENGTHUNIT["metre", 1]]],
    PRIMEM["Greenwich", 0,
        ANGLEUNIT["degree", 0.0174532925199433]],
    CS[ellipsoidal, 2],
        AXIS["geodetic latitude", north,
            ORDER[1],
            ANGLEUNIT["degree", 0.0174532925199433]],
        AXIS["geodetic longitude", east,
            ORDER[2],
            ANGLEUNIT["degree", 0.0174532925199433]],
    ID["EPSG", 4326]]"""


class TestObjToEvoConverter(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.metadata = EvoWorkspaceMetadata(
            workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=self.cache_root_dir.name
        )
        _, data_client = create_evo_object_service_and_data_client(self.metadata)
        self.data_client = data_client

    async def test_should_add_expected_tags(self) -> None:
        obj_file = this_dir.parent / "data" / "simple_shapes" / "simple_shapes.obj"
        tags = {"First tag": "first tag value", "Second tag": "second tag value"}

        go_objects = await convert_obj(
            filepath=obj_file, evo_workspace_metadata=self.metadata, epsg_code=4326, tags=tags, publish_objects=False
        )

        expected_tags = {
            "Source": "simple_shapes.obj (via Evo Data Converters)",
            "Stage": "Experimental",
            "InputType": "OBJ",
            **tags,
        }
        self.assertEqual(go_objects[0].tags, expected_tags)

    async def test_should_convert_expected_geometry_types(self) -> None:
        obj_file = this_dir.parent / "data" / "simple_shapes" / "simple_shapes.obj"
        go_objects = await convert_obj(
            filepath=obj_file, evo_workspace_metadata=self.metadata, epsg_code=4326, publish_objects=False
        )

        expected_go_object_types = [TriangleMesh_V2_2_0]
        self.assertListEqual(expected_go_object_types, [type(obj) for obj in go_objects])


@pytest.mark.parametrize(
    "input_crs, expected_crs",
    [
        (4326, Crs_V1_0_1_EpsgCode(epsg_code=4326)),
        ("EPSG:4326", Crs_V1_0_1_EpsgCode(epsg_code=4326)),
        (_WKT2_EXAMPLE, Crs_V1_0_1_OgcWkt(ogc_wkt=CRS.from_wkt(_WKT2_EXAMPLE).to_wkt("WKT2_2019"))),
        (None, "unspecified"),
    ],
)
@pytest.mark.asyncio
async def test_coordinate_reference_system(input_crs, expected_crs) -> None:
    cache_root_dir = tempfile.TemporaryDirectory()
    metadata = EvoWorkspaceMetadata(workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=cache_root_dir.name)
    obj_file = this_dir.parent / "data" / "simple_shapes" / "simple_shapes.obj"
    go_objects = await convert_obj(
        filepath=obj_file,
        evo_workspace_metadata=metadata,
        coordinate_reference_system=input_crs,
        publish_objects=False,
    )
    assert all(obj.coordinate_reference_system == expected_crs for obj in go_objects)


@pytest.mark.asyncio
async def test_coordinate_reference_system_conflicts_with_epsg_code() -> None:
    cache_root_dir = tempfile.TemporaryDirectory()
    metadata = EvoWorkspaceMetadata(workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=cache_root_dir.name)
    obj_file = this_dir.parent / "data" / "simple_shapes" / "simple_shapes.obj"
    with pytest.raises(
        ValueError, match="Both epsg_code and coordinate_reference_system were provided. Please provide only one."
    ):
        await convert_obj(
            filepath=obj_file,
            evo_workspace_metadata=metadata,
            epsg_code=4326,
            coordinate_reference_system=_WKT2_EXAMPLE,
            publish_objects=False,
        )
