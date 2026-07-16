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

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from evo.data_converters.xyz.importer import convert_xyz
from evo.data_converters.common import EvoWorkspaceMetadata

this_dir = Path(__file__).parent


def test_convert_xyz_parser() -> None:
    xyz_file = this_dir / "data" / "ThreePointTable.xyz"
    evo_workspace_metadata = EvoWorkspaceMetadata(hub_url="http://example.com")
    tags = {"tagtest": "testvalue"}
    upload_path = "upload/path"

    with (
        patch(
            "evo.data_converters.xyz.importer.xyz_main.create_evo_object_service_and_data_client"
        ) as mock_create_client,
        patch("evo.data_converters.xyz.importer.xyz_parser.save_array_to_parquet") as mock_save_parquet_file,
        patch("evo.data_converters.xyz.importer.xyz_parser.save_1d_array_to_parquet") as mock_save_1d_parquet_file,
    ):
        mock_create_client.return_value = (MagicMock(), MagicMock())
        mock_save_parquet_file.return_value = None
        mock_save_1d_parquet_file.return_value = None

        result = convert_xyz(
            filepath=str(xyz_file),
            evo_workspace_metadata=evo_workspace_metadata,
            tags=tags,
            upload_path=upload_path,
            publish_objects=False,
        )

        assert len(result) == 1
        assert result[0].coordinate_reference_system == "unspecified"
        assert result[0].bounding_box.min_x == 444001.07
        assert result[0].bounding_box.min_y == 492001.5
        assert result[0].bounding_box.min_z == 2390.96
        assert result[0].bounding_box.max_x == 447004.076
        assert result[0].bounding_box.max_y == 495057.8947
        assert result[0].bounding_box.max_z == 3682.755318

        assert result[0].locations.coordinates.length == 702355
        if result[0].locations.attributes:
            assert result[0].locations.attributes[0].name == "data"
            assert result[0].locations.attributes[0].values.data.count() == 0
            assert result[0].locations.attributes[0].nan_description.values == [-1.0e32]


def _run_convert(filename: str, x_index: int = -1, y_index: int = -1, z_index: int = -1, data_index: int = -1):
    xyz_file = this_dir / "data" / filename
    evo_workspace_metadata = EvoWorkspaceMetadata(hub_url="http://example.com")
    with (
        patch(
            "evo.data_converters.xyz.importer.xyz_main.create_evo_object_service_and_data_client"
        ) as mock_create_client,
        patch("evo.data_converters.xyz.importer.xyz_parser.save_array_to_parquet"),
        patch("evo.data_converters.xyz.importer.xyz_parser.save_1d_array_to_parquet"),
    ):
        mock_create_client.return_value = (MagicMock(), MagicMock())
        result = convert_xyz(
            filepath=str(xyz_file),
            evo_workspace_metadata=evo_workspace_metadata,
            publish_objects=False,
            x_index=x_index,
            y_index=y_index,
            z_index=z_index,
            data_index=data_index,
        )
    assert len(result) == 1
    return result[0]


def _assert_pointset(ps, min_x, min_y, min_z, max_x, max_y, max_z, n, has_data):
    assert ps.coordinate_reference_system == "unspecified"
    assert ps.bounding_box.min_x == pytest.approx(min_x)
    assert ps.bounding_box.min_y == pytest.approx(min_y)
    assert ps.bounding_box.min_z == pytest.approx(min_z)
    assert ps.bounding_box.max_x == pytest.approx(max_x)
    assert ps.bounding_box.max_y == pytest.approx(max_y)
    assert ps.bounding_box.max_z == pytest.approx(max_z)
    assert ps.locations.coordinates.length == n
    if has_data:
        assert ps.locations.attributes is not None
        assert len(ps.locations.attributes) == 1
        assert ps.locations.attributes[0].name == "data"
        assert ps.locations.attributes[0].values.length == n
    else:
        assert ps.locations.attributes is None


# binary_located.XYZ — GEOSOFT_BYNARY_XYZ


def test_binary_default() -> None:
    ps = _run_convert("binary_located.XYZ")
    _assert_pointset(ps, -4.48, -1.4, 0.0, 4.48, 1.4, 0.0, 180, False)


def test_binary_custom_xy() -> None:
    ps = _run_convert("binary_located.XYZ", x_index=1, y_index=0)
    _assert_pointset(ps, -1.4, -4.48, 0.0, 1.4, 4.48, 0.0, 180, False)


# triplet_located.XYZ — GEOSOFT_XYZ_TRIPLET


def test_triplet_default() -> None:
    ps = _run_convert("triplet_located.XYZ")
    _assert_pointset(ps, -4.48, -1.4, 0.2, 4.48, 1.4, 0.2, 180, False)


def test_triplet_custom_xyz() -> None:
    ps = _run_convert("triplet_located.XYZ", x_index=2, y_index=1, z_index=0)
    _assert_pointset(ps, 0.2, -1.4, -4.48, 0.2, 1.4, 4.48, 180, False)


# triplet_located.XYZ — GEOSOFT_BYNARY_XYZ_DATA


def test_triplet_data_default() -> None:
    ps = _run_convert("triplet_located.XYZ", data_index=2)
    _assert_pointset(ps, -4.48, -1.4, 0.0, 4.48, 1.4, 0.0, 180, True)


def test_triplet_data_custom_xy() -> None:
    ps = _run_convert("triplet_located.XYZ", x_index=1, y_index=0, data_index=2)
    _assert_pointset(ps, -1.4, -4.48, 0.0, 1.4, 4.48, 0.0, 180, True)


# full_located.XYZ — GEOSOFT_XYZ_TRIPLET


def test_full_default() -> None:
    ps = _run_convert("full_located.XYZ")
    _assert_pointset(ps, 0.0, 0.0, 0.2, 0.0, 0.0, 0.2, 180, False)


def test_full_custom_xyz() -> None:
    ps = _run_convert("full_located.XYZ", x_index=5, y_index=6, z_index=2)
    _assert_pointset(ps, -4.48, -1.4, 0.2, 4.48, 1.4, 0.2, 180, False)


# full_located.XYZ — GEOSOFT_BYNARY_XYZ_DATA


def test_full_data_default() -> None:
    ps = _run_convert("full_located.XYZ", data_index=10)
    _assert_pointset(ps, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 180, True)


# full_located.XYZ — GEOSOFT_XYZ_TRIPLET_DATA


def test_full_data_custom_z() -> None:
    ps = _run_convert("full_located.XYZ", z_index=2, data_index=10)
    _assert_pointset(ps, 0.0, 0.0, 0.2, 0.0, 0.0, 0.2, 180, True)


def test_full_data_custom_xyz() -> None:
    ps = _run_convert("full_located.XYZ", x_index=4, y_index=5, z_index=2, data_index=10)
    _assert_pointset(ps, -1e32, -4.48, 0.2, -1e32, 4.48, 0.2, 180, True)
