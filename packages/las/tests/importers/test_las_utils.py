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

import shutil
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
import pytest
import pytest_asyncio
from evo_schemas.components import Crs_V1_0_1_EpsgCode

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.las.importer.las_reader import LASInvalidDataError, read_las_file
from evo.data_converters.las.importer.utils import _positions_at, get_geoscience_object_from_las
from evo.objects.utils.data import ObjectDataClient

DATA = Path(__file__).parent.parent / "data"
LAS = DATA / "BR-I-1_V2.las"
DEV = DATA / "BR-I-1.dev"
CRS = Crs_V1_0_1_EpsgCode(epsg_code=32650)


@pytest_asyncio.fixture
async def data_client() -> AsyncIterator[ObjectDataClient]:
    with tempfile.TemporaryDirectory() as cache:
        metadata = EvoWorkspaceMetadata(workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=cache)
        _, client = await create_evo_object_service_and_data_client(metadata)
        yield client


def test_single_file_with_deviation(data_client: ObjectDataClient) -> None:
    obj, _ = get_geoscience_object_from_las(data_client, LAS, CRS, {"a": "b"}, deviation_files=DEV)
    assert obj.name == "BR-I-1_V2"
    assert obj.tags["a"] == "b"
    assert obj.bounding_box.min_x == pytest.approx(-113.0)
    assert obj.bounding_box.max_y == pytest.approx(5648.0)
    assert obj.bounding_box.max_z == pytest.approx(35.0)
    assert obj.bounding_box.min_z == pytest.approx(35.0 - 1900.0)
    names = [a.name for a in obj.collections[0].distance.attributes]
    assert "GR" in names and "DEPT" not in names


def test_pointset_along_trajectory(data_client: ObjectDataClient) -> None:
    las = read_las_file(LAS)
    _, points = get_geoscience_object_from_las(data_client, LAS, CRS, deviation_files=DEV)
    assert points.name == "BR-I-1_V2 points"
    attrs = [a.name for a in points.locations.attributes]
    assert attrs[0] == "holeid"
    assert {c.mnemonic for c in las.curves[1:]} <= set(attrs)
    assert points.bounding_box.min_x == points.bounding_box.max_x == -113.0
    # vertical hole: elevation is KB minus measured depth
    assert points.bounding_box.max_z == pytest.approx(35.0 - las.depth_in_metres.min())
    assert points.bounding_box.min_z == pytest.approx(35.0 - las.depth_in_metres.max())


def test_positions_follow_inclined_survey() -> None:
    survey = np.array([[0.0, 0.0, 90.0], [100.0, 90.0, 45.0]])
    xyz = _positions_at((10.0, 20.0, 30.0), survey, 100.0, np.array([0.0, 100.0, 150.0]))
    assert xyz[0].tolist() == [10.0, 20.0, 30.0]
    assert xyz[1, 0] > 10.0 and xyz[1, 2] < 30.0  # heads east and down
    assert xyz[1, 1] == pytest.approx(20.0)


def test_default_collar_without_deviation(data_client: ObjectDataClient) -> None:
    obj, _ = get_geoscience_object_from_las(data_client, LAS, CRS)
    assert obj.bounding_box.min_x == obj.bounding_box.max_x == 0.0
    assert obj.bounding_box.max_z == 0.0
    assert obj.bounding_box.min_z == pytest.approx(-1777.4433, abs=1e-3)


def test_multiple_files_and_directory_matching(data_client: ObjectDataClient, tmp_path: Path) -> None:
    second = tmp_path / "BR-I-2.las"
    second.write_text(LAS.read_text().replace("BR-I-1", "BR-I-2"))
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    shutil.copy(DEV, dev_dir / "BR-I-1.dev")

    with pytest.raises(LASInvalidDataError, match="BR-I-2"):
        get_geoscience_object_from_las(data_client, [LAS, second], CRS, deviation_files=dev_dir)

    obj, _ = get_geoscience_object_from_las(
        data_client, [LAS, second], CRS, deviation_files=dev_dir, allow_missing_deviation=True
    )
    assert obj.name == "LAS downhole collection"
    assert obj.collections[0].distance.attributes


def test_duplicate_hole_ids(data_client: ObjectDataClient) -> None:
    with pytest.raises(LASInvalidDataError, match="Duplicate"):
        get_geoscience_object_from_las(data_client, [LAS, LAS], CRS)
