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

import typing
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from evo_schemas import Tensor3DGrid_V1_2_0

from evo.data_converters.ubc.importer.utils import get_geoscience_object_from_ubc
from evo.objects.utils.data import ObjectDataClient


@pytest.fixture
def mock_data_client() -> typing.Any:
    return MagicMock(spec=ObjectDataClient)


@pytest.fixture
def mock_mesh_importer() -> typing.Any:
    with patch("evo.data_converters.ubc.importer.utils.UBCMeshFileImporter") as mock:
        yield mock


@pytest.fixture
def mock_property_importer() -> typing.Any:
    with patch("evo.data_converters.ubc.importer.utils.UBCPropertyFileImporter") as mock:
        yield mock


def test_get_geoscience_object_from_ubc_success(
    mock_data_client: MagicMock, mock_mesh_importer: MagicMock, mock_property_importer: MagicMock
) -> None:
    values_data = {
        "data": "475667033d674e3dbcc25a05880e9e151c10c4d682234b1cfb63d41b905b97a4",
        "data_type": "float64",
        "length": 60,
        "width": 1,
    }
    mock_data_client.save_table.return_value = values_data
    files_path = ["dummy_file.msh", "dummy_values.txt"]
    epsg_code = 4326

    mock_mesh_importer.return_value.execute.return_value = (
        np.array([1.0, 2.0, 3.0]),
        [np.array([3.0]), np.array([4.0]), np.array([5.0])],
        [3, 4, 5],
        "",  # wkt_string
    )
    mock_property_importer.return_value.execute.return_value = np.array([1.0])

    tags = {"First tag": "first tag value", "Second tag": "second tag value"}
    result = get_geoscience_object_from_ubc(mock_data_client, files_path, epsg_code, tags=tags)

    expected_tags = {
        "Source": "dummy_file.msh (via Evo Data Converters)",
        "Stage": "Experimental",
        "InputType": "UBC",
        **tags,
    }
    assert isinstance(result, Tensor3DGrid_V1_2_0)
    assert result.tags == expected_tags
    assert result.size == [3, 4, 5]
    assert result.origin == [1.0, 2.0, 3.0]
    assert len(result.cell_attributes) == 1
    assert result.cell_attributes[0].values.data == values_data["data"]
    assert result.cell_attributes[0].values.data_type == values_data["data_type"]
    assert result.cell_attributes[0].values.length == values_data["length"]
    assert result.cell_attributes[0].values.width == values_data["width"]
    assert result.cell_attributes[0].name == "dummy_values"
    assert result.grid_cells_3d.cell_sizes_x == [3.0]
    assert result.grid_cells_3d.cell_sizes_y == [4.0]
    assert result.grid_cells_3d.cell_sizes_z == [5.0]
    bbox = (
        result.bounding_box.min_x,
        result.bounding_box.max_x,
        result.bounding_box.min_y,
        result.bounding_box.max_y,
        result.bounding_box.min_z,
        result.bounding_box.max_z,
    )
    assert bbox == (1.0, 4.0, 2.0, 6.0, 3.0, 8.0)


def test_get_geoscience_object_from_ubc_no_mesh_file(mock_data_client: MagicMock) -> None:
    files_path = ["dummy_values.txt"]
    epsg_code = 4326

    with pytest.raises(ValueError, match="No UBC mesh file provided."):
        get_geoscience_object_from_ubc(mock_data_client, files_path, epsg_code)


def test_get_geoscience_object_from_ubc_multiple_mesh_files(mock_data_client: MagicMock) -> None:
    files_path = ["dummy_file1.msh", "dummy_file2.msh"]
    epsg_code = 4326

    with pytest.raises(ValueError, match="Multiple UBC mesh files provided."):
        get_geoscience_object_from_ubc(mock_data_client, files_path, epsg_code)


def test_derive_epsg_from_wkt_gda94_mga() -> None:
    from evo.data_converters.ubc.importer.utils import _derive_epsg_from_wkt

    # Test GDA94/MGA zone 55
    wkt = "GDA94 / MGA zone 55"
    assert _derive_epsg_from_wkt(wkt) == 28355

    # Test GDA94/MGA zone 50
    wkt = "GDA94 / MGA zone 50"
    assert _derive_epsg_from_wkt(wkt) == 28350


def test_derive_epsg_from_wkt_gda2020_mga() -> None:
    from evo.data_converters.ubc.importer.utils import _derive_epsg_from_wkt

    # Test GDA2020/MGA zone 55
    wkt = "GDA2020 / MGA zone 55"
    assert _derive_epsg_from_wkt(wkt) == 7855

    # Test GDA2020/MGA zone 50
    wkt = "GDA2020 / MGA zone 50"
    assert _derive_epsg_from_wkt(wkt) == 7850


def test_derive_epsg_from_wkt_wgs84_utm() -> None:
    from evo.data_converters.ubc.importer.utils import _derive_epsg_from_wkt

    # Test WGS84/UTM zone 55N
    wkt = "WGS 84 / UTM zone 55 N"
    assert _derive_epsg_from_wkt(wkt) == 32655

    # Test WGS84/UTM zone 55S
    wkt = "WGS 84 / UTM zone 55 S"
    assert _derive_epsg_from_wkt(wkt) == 32755


def test_derive_epsg_from_wkt_nad83_utm() -> None:
    from evo.data_converters.ubc.importer.utils import _derive_epsg_from_wkt

    # Test NAD83/UTM zone 11N
    wkt = "NAD83 / UTM zone 11 N"
    assert _derive_epsg_from_wkt(wkt) == 26911


def test_derive_epsg_from_wkt_invalid() -> None:
    from evo.data_converters.ubc.importer.utils import _derive_epsg_from_wkt

    # Test invalid WKT
    wkt = "Some random coordinate system"
    assert _derive_epsg_from_wkt(wkt) is None

    # Test empty string
    assert _derive_epsg_from_wkt("") is None

    # Test None
    assert _derive_epsg_from_wkt(None) is None


def test_derive_epsg_from_wkt_case_insensitive() -> None:
    from evo.data_converters.ubc.importer.utils import _derive_epsg_from_wkt

    # Test case insensitivity
    wkt_lower = "gda94 / mga zone 55"
    wkt_upper = "GDA94 / MGA ZONE 55"
    wkt_mixed = "GdA94 / mGa ZoNe 55"

    assert _derive_epsg_from_wkt(wkt_lower) == 28355
    assert _derive_epsg_from_wkt(wkt_upper) == 28355
    assert _derive_epsg_from_wkt(wkt_mixed) == 28355


def test_get_geoscience_object_from_ubc_with_inferred_epsg(
    mock_data_client: MagicMock, mock_mesh_importer: MagicMock, mock_property_importer: MagicMock
) -> None:
    """Test that EPSG code is inferred from WKT when not provided"""
    values_data = {
        "data": "475667033d674e3dbcc25a05880e9e151c10c4d682234b1cfb63d41b905b97a4",
        "data_type": "float64",
        "length": 60,
        "width": 1,
    }
    mock_data_client.save_table.return_value = values_data
    files_path = ["dummy_file.msh", "dummy_values.txt"]

    mock_mesh_importer.return_value.execute.return_value = (
        np.array([1.0, 2.0, 3.0]),
        [np.array([3.0]), np.array([4.0]), np.array([5.0])],
        [3, 4, 5],
        "GDA94 / MGA zone 55",  # wkt_string with inferred EPSG
    )
    mock_property_importer.return_value.execute.return_value = np.array([1.0])

    tags = {"First tag": "first tag value"}
    # Call with default epsg_code (-1)
    result = get_geoscience_object_from_ubc(mock_data_client, files_path, tags=tags)

    assert isinstance(result, Tensor3DGrid_V1_2_0)
    # EPSG 28355 should be inferred from "GDA94 / MGA zone 55"
    assert result.coordinate_reference_system.epsg_code == 28355
