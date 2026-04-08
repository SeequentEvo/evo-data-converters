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

from evo.data_converters.common import TensorGridData
from evo.data_converters.ubc.importer.utils import get_geoscience_object_from_ubc, get_grid_data
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


def test_get_grid_data_from_ubc_success(mock_mesh_importer: MagicMock, mock_property_importer: MagicMock) -> None:
    files_path = ["dummy_file.msh", "dummy_values.txt"]

    mock_mesh_importer.return_value.execute.return_value = (
        np.array([1.0, 2.0, 3.0]),
        [np.array([3.0]), np.array([4.0]), np.array([5.0])],
        [3, 4, 5],
    )
    mock_property_importer.return_value.execute.return_value = np.array([1.0])

    name, grid_data = get_grid_data(files_path)

    assert isinstance(grid_data, TensorGridData)
    assert grid_data.size == [3, 4, 5]
    assert grid_data.origin == [1.0, 2.0, 3.0]
    assert len(grid_data.cell_attributes) == 1
    assert grid_data.cell_attributes[0]["name"] == "dummy_values"
    assert grid_data.cell_sizes_x == [3.0]
    assert grid_data.cell_sizes_y == [4.0]
    assert grid_data.cell_sizes_z == [5.0]
    assert grid_data.bounding_box == [1.0, 4.0, 2.0, 6.0, 3.0, 8.0]
    np.testing.assert_array_equal(grid_data.rotation, [0.0, 0.0, 0.0])


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
