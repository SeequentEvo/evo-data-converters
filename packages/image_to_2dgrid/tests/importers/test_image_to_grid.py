# --------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Bentley Systems, Incorporated. All rights reserved.
# --------------------------------------------------------------------------------------------

"""
Unit tests for image to Regular 2D Grid converter.
All tests run offline (no Evo auth) using a local mock data client that
implements save_table(...) similar to the real ObjectDataClient.
"""

from __future__ import annotations

import io
import hashlib
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image

from evo.data_converters.image_to_2dgrid.image_to_grid import (
    ImageGridConverter,
    geoscience_object_data_options,
)


class _MockDataClient:
    """
    Minimal mock for ObjectDataClient used by tests.
    - save_table(table) returns a dict with the keys your converter expects.
    - Stores the last content hash so tests can assert equality.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.last_saved_hash: str | None = None

    def save_table(self, table: pa.Table):
        buf = io.BytesIO()
        pq.write_table(table, buf, **geoscience_object_data_options())
        data = buf.getvalue()
        data_hash = hashlib.sha256(data).hexdigest()
        self.last_saved_hash = data_hash
        # Write a local copy so tests can check existence when output_parquet=True
        (self.output_dir / f"{data_hash}.parquet").write_bytes(data)
        return {
            "data": data_hash,
            "length": table.num_rows,
            "width": 1,
            "data_type": "float64",
        }


@pytest.fixture
def sample_image(tmp_path: Path) -> Tuple[Path, int, int]:
    """
    Create a small 10x8 grayscale gradient PNG for testing.
    Using PNG to avoid JPEG compression artifacts in assertions.
    """
    width, height = 10, 8
    arr = np.arange(width * height, dtype=np.uint8).reshape((height, width))
    img_path = tmp_path / "test_image.png"
    Image.fromarray(arr, mode="L").save(img_path)
    return img_path, width, height


@pytest.fixture
def mock_data_client(tmp_path: Path) -> _MockDataClient:
    """Provide a mock data client that mimics save_table(...)."""
    return _MockDataClient(output_dir=tmp_path / "parquet")


def test_read_image_as_grayscale(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Test reading an image and converting to grayscale array."""
    image_path, expected_width, expected_height = sample_image
    converter = ImageGridConverter(mock_data_client)

    cell_values, width, height = converter._read_image_as_grayscale(str(image_path))

    assert width == expected_width
    assert height == expected_height
    assert len(cell_values) == width * height
    assert cell_values.dtype == np.float64
    # Row-major: first row should be strictly increasing for our gradient
    assert np.all(np.diff(cell_values[:width]) > 0)


def test_convert_basic_grid(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Test basic grid conversion with default parameters."""
    image_path, width, height = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    grid = converter.convert(str(image_path))

    assert grid.schema == "/objects/regular-2d-grid/1.3.0/regular-2d-grid.schema.json"
    assert grid.name == image_path.stem
    assert grid.size == [width, height]
    assert grid.origin == [0.0, 0.0, 0.0]
    assert grid.cell_size == [1.0, 1.0]
    assert len(grid.cell_attributes) == 1

    attr = grid.cell_attributes[0]
    assert attr.attribute_type == "scalar"
    assert attr.name == "2d-grid-data-continuous"
    assert attr.values.data_type == "float64"
    assert attr.values.width == 1
    assert attr.values.length == width * height


def test_convert_with_custom_parameters(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Custom origin/cell_size/name/description propagate to the grid."""
    image_path, width, height = sample_image
    custom_origin = [572565.0, 6839415.0, 1000.0]
    custom_cell_size = [30.0, 30.0]
    custom_name = "Custom Grid"
    custom_description = "Test grid with custom parameters"

    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    grid = converter.convert(
        str(image_path),
        origin=custom_origin,
        cell_size=custom_cell_size,
        name=custom_name,
        description=custom_description,
    )

    assert grid.name == custom_name
    assert grid.description == custom_description
    assert grid.origin == custom_origin
    assert grid.cell_size == custom_cell_size

    # Bounding box math
    assert grid.bounding_box.min_x == custom_origin[0]
    assert grid.bounding_box.min_y == custom_origin[1]
    assert grid.bounding_box.min_z == custom_origin[2]
    assert grid.bounding_box.max_x == custom_origin[0] + (width * custom_cell_size[0])
    assert grid.bounding_box.max_y == custom_origin[1] + (height * custom_cell_size[1])
    assert grid.bounding_box.max_z == custom_origin[2]

    # Default rotation zeros
    assert grid.rotation.dip == 0.0
    assert grid.rotation.dip_azimuth == 0.0
    assert grid.rotation.pitch == 0.0


def test_cell_attribute_and_hash(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Ensure attribute references use the hash produced by data_client.save_table."""
    image_path, width, height = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    grid = converter.convert(str(image_path))
    attr = grid.cell_attributes[0]

    assert mock_data_client.last_saved_hash is not None
    expected_hash = mock_data_client.last_saved_hash

    assert attr.key == expected_hash
    assert attr.values.data == expected_hash
    assert attr.values.length == width * height
    assert attr.values.width == 1


def test_tags_and_crs(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Tags are preserved; CRS dict with EPSG becomes a Crs object."""
    from evo_schemas.components import Crs_V1_0_1_EpsgCode

    image_path, _, _ = sample_image
    tags = {"Source": "Test", "Type": "Image Grid"}
    crs_dict = {"epsg_code": 32618}

    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    grid = converter.convert(str(image_path), tags=tags, coordinate_reference_system=crs_dict)

    assert grid.tags == tags
    assert isinstance(grid.coordinate_reference_system, Crs_V1_0_1_EpsgCode)
    assert grid.coordinate_reference_system.epsg_code == 32618


def test_parquet_file_output(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient, tmp_path: Path):
    """When output_parquet=True, a local parquet file is written with hash filename."""
    image_path, _, _ = sample_image

    # Recreate converter with output_parquet=True to force a local file write
    converter = ImageGridConverter(
        data_client=mock_data_client,
        output_dir=str(mock_data_client.output_dir),
        output_parquet=True,
    )
    grid = converter.convert(str(image_path))

    attr = grid.cell_attributes[0]
    expected = mock_data_client.output_dir / f"{attr.key}.parquet"
    assert expected.exists(), f"Expected parquet at {expected}"


def test_different_image_sizes(mock_data_client: _MockDataClient, tmp_path: Path):
    """Conversion succeeds for various dimensions and attribute length matches size."""
    test_sizes = [(50, 50), (100, 75), (1, 1), (256, 128)]

    for width, height in test_sizes:
        arr = np.random.randint(0, 256, (height, width), dtype=np.uint8)
        img_path = tmp_path / f"test_{width}x{height}.png"
        Image.fromarray(arr, mode="L").save(img_path)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        grid = converter.convert(str(img_path))

        assert grid.size == [width, height]
        assert grid.cell_attributes[0].values.length == width * height
