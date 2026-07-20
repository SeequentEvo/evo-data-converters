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

"""
Unit tests for image to Regular 2D Grid converter.
All tests run offline (no Evo auth) using a local mock data client that
implements save_table(...) similar to the real ObjectDataClient.
"""

from __future__ import annotations

import io
import hashlib
import importlib.util
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
from pyproj import CRS

from evo.data_converters.image.importer.image_to_grid import (
    ImageGridConverter,
    geoscience_object_data_options,
    _normalize_array_data_type,
)

HAS_RASTERIO = importlib.util.find_spec("rasterio") is not None


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
        first_field = table.schema.field(0)
        # Write a local copy so tests can check existence when output_parquet=True
        (self.output_dir / f"{data_hash}.parquet").write_bytes(data)
        return {
            "data": data_hash,
            "length": table.num_rows,
            "width": 1,
            "data_type": _normalize_array_data_type(first_field.type),
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
    """Test reading an image and detecting grayscale mode."""
    image_path, expected_width, expected_height = sample_image
    converter = ImageGridConverter(mock_data_client)

    cell_values, width, height, mode = converter._read_image(str(image_path))

    assert width == expected_width
    assert height == expected_height
    assert mode == "grayscale"
    assert len(cell_values) == width * height
    assert cell_values.dtype == np.float64
    # Row-major after vertical flip: first row should still be strictly increasing.
    assert np.all(np.diff(cell_values[:width]) > 0)


@pytest.mark.parametrize("mode,dtype", [("F", np.float32), ("I", np.int32)])
def test_read_image_tiff_single_band_numeric_modes_are_grayscale(
    tmp_path: Path,
    mock_data_client: _MockDataClient,
    mode: str,
    dtype,
):
    """Single-band TIFF numeric modes (F/I) must be handled as grayscale."""
    width, height = 7, 5
    arr = np.arange(width * height, dtype=dtype).reshape((height, width))
    img_path = tmp_path / f"single_band_{mode}.tif"
    Image.fromarray(arr, mode=mode).save(img_path)

    converter = ImageGridConverter(mock_data_client)
    cell_values, read_width, read_height, read_mode = converter._read_image(str(img_path))

    assert read_width == width
    assert read_height == height
    assert read_mode == "grayscale"
    assert cell_values.dtype == np.float64
    assert len(cell_values) == width * height


def test_read_image_uses_bottom_left_as_origin(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """The first flattened row must correspond to the bottom image row."""
    image_path, width, height = sample_image
    converter = ImageGridConverter(mock_data_client)

    cell_values, read_width, read_height, mode = converter._read_image(str(image_path))

    assert read_width == width
    assert read_height == height

    # Fixture image is a simple ramp: arr[y, x] = y * width + x.
    expected_bottom_row = np.arange((height - 1) * width, height * width, dtype=np.float64)
    np.testing.assert_array_equal(cell_values[:width], expected_bottom_row)


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
    tags = {"Source": "Test", "Type": "Image"}
    crs_dict = {"epsg_code": 32618}

    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    grid = converter.convert(str(image_path), tags=tags, coordinate_reference_system=crs_dict)

    assert grid.tags == tags
    assert isinstance(grid.coordinate_reference_system, Crs_V1_0_1_EpsgCode)
    assert grid.coordinate_reference_system.epsg_code == 32618


def test_no_crs_when_not_provided(sample_image: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """When no CRS is provided, coordinate_reference_system should be 'unspecified'."""
    image_path, _, _ = sample_image

    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    grid = converter.convert(str(image_path))

    # Image without an explicitly defined coordinate system should be marked as unspecified
    assert grid.coordinate_reference_system == "unspecified"


def test_extract_epsg_from_geokey_directory_projected(mock_data_client: _MockDataClient):
    """ProjectedCSTypeGeoKey (3072) should be preferred when present."""
    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    geokey = (
        1,
        1,
        0,
        2,
        2048,
        0,
        1,
        4326,
        3072,
        0,
        1,
        32614,
    )
    assert converter._extract_epsg_from_geokey_directory(geokey) == 32614


def test_extract_epsg_from_geokey_directory_geographic(mock_data_client: _MockDataClient):
    """GeographicTypeGeoKey (2048) should be used when projected key is absent."""
    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    geokey = (1, 1, 0, 1, 2048, 0, 1, 4326)
    assert converter._extract_epsg_from_geokey_directory(geokey) == 4326


def test_extract_epsg_from_geokey_directory_user_defined_returns_none(mock_data_client: _MockDataClient):
    """User-defined key value (32767) should not be treated as EPSG authority."""
    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    geokey = (1, 1, 0, 1, 3072, 0, 1, 32767)
    assert converter._extract_epsg_from_geokey_directory(geokey) is None


def test_extract_wkt_candidate_from_text(mock_data_client: _MockDataClient):
    """WKT text can be isolated from surrounding metadata text."""
    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    metadata = 'prefix text PROJCS["WGS 84 / UTM zone 14N",GEOGCS["WGS 84",DATUM["WGS_1984"]]] trailing text'

    wkt = converter._extract_wkt_candidate_from_text(metadata)
    assert wkt is not None
    assert wkt.startswith("PROJCS[")
    assert wkt.endswith("]")


def test_auto_crs_from_embedded_geotiff_when_not_provided(
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """If input CRS is not provided, embedded GeoTIFF CRS should be used when detected."""
    image_path, _, _ = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    monkeypatch.setattr(
        converter,
        "_extract_embedded_coordinate_reference_system",
        lambda _: {"epsg_code": 32614},
    )

    from evo_schemas.components import Crs_V1_0_1_EpsgCode

    grid = converter.convert(str(image_path))
    assert isinstance(grid.coordinate_reference_system, Crs_V1_0_1_EpsgCode)
    assert grid.coordinate_reference_system.epsg_code == 32614


def test_auto_wkt_crs_from_embedded_geotiff_when_epsg_missing(
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """If embedded EPSG is unavailable, embedded WKT should be used as CRS."""
    image_path, _, _ = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    wkt = CRS.from_epsg(32614).to_wkt(version="WKT2_2019")
    monkeypatch.setattr(
        converter,
        "_extract_embedded_coordinate_reference_system",
        lambda _: {"ogc_wkt": wkt},
    )

    from evo_schemas.components import Crs_V1_0_1_OgcWkt

    grid = converter.convert(str(image_path))
    assert isinstance(grid.coordinate_reference_system, Crs_V1_0_1_OgcWkt)
    assert grid.coordinate_reference_system.ogc_wkt == CRS.from_wkt(wkt).to_wkt(version="WKT2_2019")


def test_explicit_crs_overrides_embedded_geotiff_crs(
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Explicit coordinate_reference_system input should take precedence over embedded CRS."""
    image_path, _, _ = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    monkeypatch.setattr(
        converter,
        "_extract_embedded_coordinate_reference_system",
        lambda _: {"epsg_code": 4326},
    )

    from evo_schemas.components import Crs_V1_0_1_EpsgCode

    grid = converter.convert(str(image_path), coordinate_reference_system={"epsg_code": 32614})
    assert isinstance(grid.coordinate_reference_system, Crs_V1_0_1_EpsgCode)
    assert grid.coordinate_reference_system.epsg_code == 32614


def test_auto_georeferencing_from_embedded_geotiff_when_origin_and_cell_size_not_provided(
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """If origin/cell_size are not provided, embedded GeoTIFF georeferencing should be used."""
    image_path, width, height = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    monkeypatch.setattr(
        converter,
        "_extract_embedded_georeferencing",
        lambda _image_path, _width, _height: {
            "origin": [1000.0, 2000.0, 0.0],
            "cell_size": [30.0, 40.0],
        },
    )

    grid = converter.convert(str(image_path))
    assert grid.origin == [1000.0, 2000.0, 0.0]
    assert grid.cell_size == [30.0, 40.0]
    assert grid.bounding_box.min_x == 1000.0
    assert grid.bounding_box.min_y == 2000.0
    assert grid.bounding_box.max_x == 1000.0 + (width * 30.0)
    assert grid.bounding_box.max_y == 2000.0 + (height * 40.0)


def test_explicit_origin_and_cell_size_override_embedded_georeferencing(
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Explicit origin/cell_size should take precedence over embedded georeferencing."""
    image_path, _, _ = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    monkeypatch.setattr(
        converter,
        "_extract_embedded_georeferencing",
        lambda _image_path, _width, _height: {
            "origin": [1000.0, 2000.0, 0.0],
            "cell_size": [30.0, 40.0],
        },
    )

    grid = converter.convert(
        str(image_path),
        origin=[10.0, 20.0, 0.0],
        cell_size=[2.0, 3.0],
    )

    assert grid.origin == [10.0, 20.0, 0.0]
    assert grid.cell_size == [2.0, 3.0]


def test_partial_override_origin_uses_embedded_cell_size(
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """If only origin is explicit, cell_size should come from embedded georeferencing."""
    image_path, _, _ = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    monkeypatch.setattr(
        converter,
        "_extract_embedded_georeferencing",
        lambda _image_path, _width, _height: {
            "origin": [1000.0, 2000.0, 0.0],
            "cell_size": [30.0, 40.0],
        },
    )

    grid = converter.convert(str(image_path), origin=[10.0, 20.0, 0.0])
    assert grid.origin == [10.0, 20.0, 0.0]
    assert grid.cell_size == [30.0, 40.0]


def test_partial_override_cell_size_uses_embedded_origin(
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """If only cell_size is explicit, origin should come from embedded georeferencing."""
    image_path, _, _ = sample_image
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    monkeypatch.setattr(
        converter,
        "_extract_embedded_georeferencing",
        lambda _image_path, _width, _height: {
            "origin": [1000.0, 2000.0, 0.0],
            "cell_size": [30.0, 40.0],
        },
    )

    grid = converter.convert(str(image_path), cell_size=[2.0, 3.0])
    assert grid.origin == [1000.0, 2000.0, 0.0]
    assert grid.cell_size == [2.0, 3.0]


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


# ============================================================================
# Color Image Tests
# ============================================================================


@pytest.fixture
def color_image_rgb(tmp_path: Path) -> Tuple[Path, int, int]:
    """
    Create a small 4x3 RGB test image with specific color values.
    Colors used:
    - Red (255, 0, 0)
    - Green (0, 255, 0)
    - Blue (0, 0, 255)
    - White (255, 255, 255)
    """
    width, height = 4, 3
    # Create a simple pattern: each pixel has a distinct color
    # Bottom row: Red, Green, Blue, White
    # Middle row: Red, Green, Blue, White (repeated)
    # Top row: Red, Green, Blue, White (repeated)
    arr = np.array(
        [
            # Top row (y=2)
            [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255]],
            # Middle row (y=1)
            [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255]],
            # Bottom row (y=0) - will be index 0-3 after flip
            [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255]],
        ],
        dtype=np.uint8,
    )
    img_path = tmp_path / "test_color_rgb.png"
    Image.fromarray(arr, mode="RGB").save(img_path)
    return img_path, width, height


@pytest.fixture
def color_image_rgba(tmp_path: Path) -> Tuple[Path, int, int]:
    """
    Create a small 2x2 RGBA test image with different alpha values.
    Should be converted to RGB (alpha dropped) and A set to 0xFF in output.
    """
    width, height = 2, 2
    arr = np.array(
        [
            # Top row (y=1)
            [[255, 0, 0, 255], [0, 255, 0, 128]],
            # Bottom row (y=0)
            [[0, 0, 255, 64], [255, 255, 255, 0]],
        ],
        dtype=np.uint8,
    )
    img_path = tmp_path / "test_color_rgba.png"
    Image.fromarray(arr, mode="RGBA").save(img_path)
    return img_path, width, height


def test_read_color_image_rgb(color_image_rgb: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Test reading an RGB color image."""
    image_path, expected_width, expected_height = color_image_rgb
    converter = ImageGridConverter(mock_data_client)

    cell_values, width, height, mode = converter._read_image(str(image_path))

    assert width == expected_width
    assert height == expected_height
    assert mode == "color"
    assert cell_values.shape == (expected_width * expected_height, 3)
    assert cell_values.dtype == np.uint8

    # Verify bottom row (first after flip): should be [R, G, B, White]
    expected_bottom_row = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255]], dtype=np.uint8)
    np.testing.assert_array_equal(cell_values[:expected_width], expected_bottom_row)


def test_read_color_image_rgba(color_image_rgba: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Test that RGBA images are converted to RGB (alpha dropped)."""
    image_path, expected_width, expected_height = color_image_rgba
    converter = ImageGridConverter(mock_data_client)

    cell_values, width, height, mode = converter._read_image(str(image_path))

    assert width == expected_width
    assert height == expected_height
    assert mode == "color"
    # Should have 3 channels (RGB only, alpha dropped)
    assert cell_values.shape == (expected_width * expected_height, 3)

    # Verify bottom row: [Blue, White] (alpha info lost, but RGB preserved)
    expected_bottom_row = np.array([[0, 0, 255], [255, 255, 255]], dtype=np.uint8)
    np.testing.assert_array_equal(cell_values[:expected_width], expected_bottom_row)


def test_color_packing_format(color_image_rgb: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """
    Test that RGB values are correctly packed as 0xAABBGGRR format.
    Red (255,0,0)   -> 0xFF0000FF
    Green (0,255,0) -> 0xFF00FF00
    Blue (0,0,255)  -> 0xFFFF0000
    White (255,255,255) -> 0xFFFFFFFF
    """
    image_path, width, height = color_image_rgb
    converter = ImageGridConverter(mock_data_client)

    cell_values, _, _, _ = converter._read_image(str(image_path))

    # Pack the values using the same logic as _create_cell_attribute
    r = cell_values[:, 0].astype(np.uint32)
    g = cell_values[:, 1].astype(np.uint32)
    b = cell_values[:, 2].astype(np.uint32)
    packed = r | (g << 8) | (b << 16) | np.uint32(0xFF000000)

    # Expected packed values for bottom row:
    # Red (255,0,0)      -> 0xFF0000FF
    # Green (0,255,0)    -> 0xFF00FF00
    # Blue (0,0,255)     -> 0xFFFF0000
    # White (255,255,255)-> 0xFFFFFFFF
    expected_packed = np.array([0xFF0000FF, 0xFF00FF00, 0xFFFF0000, 0xFFFFFFFF], dtype=np.uint32)
    np.testing.assert_array_equal(packed[:width], expected_packed)


def test_color_grid_conversion(color_image_rgb: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Test complete color image to grid conversion."""
    image_path, width, height = color_image_rgb
    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    grid = converter.convert(str(image_path))

    # Verify basic grid properties
    assert grid.schema == "/objects/regular-2d-grid/1.3.0/regular-2d-grid.schema.json"
    assert grid.name == image_path.stem
    assert grid.size == [width, height]
    assert len(grid.cell_attributes) == 1

    # Verify color attribute
    attr = grid.cell_attributes[0]
    from evo_schemas.components import ColorAttribute_V1_1_0
    from evo_schemas.elements import ColorArray_V1_0_1

    assert isinstance(attr, ColorAttribute_V1_1_0)
    assert attr.attribute_type == "color"
    assert attr.name == "2d-grid-data-color"
    assert isinstance(attr.values, ColorArray_V1_0_1)
    assert attr.values.length == width * height
    assert attr.values.data_type == "uint32"
    assert attr.key == mock_data_client.last_saved_hash
    assert attr.values.data == mock_data_client.last_saved_hash


def test_color_attribute_vs_grayscale_attribute(
    color_image_rgb: Tuple[Path, int, int],
    sample_image: Tuple[Path, int, int],
    mock_data_client: _MockDataClient,
):
    """Verify that color and grayscale produce different attribute types."""
    color_path, _, _ = color_image_rgb
    gray_path, _, _ = sample_image

    converter = ImageGridConverter(mock_data_client, output_parquet=False)

    color_grid = converter.convert(str(color_path))
    gray_grid = converter.convert(str(gray_path))

    from evo_schemas.components import ColorAttribute_V1_1_0, ContinuousAttribute_V1_1_0

    color_attr = color_grid.cell_attributes[0]
    gray_attr = gray_grid.cell_attributes[0]

    assert isinstance(color_attr, ColorAttribute_V1_1_0)
    assert isinstance(gray_attr, ContinuousAttribute_V1_1_0)
    assert color_attr.attribute_type == "color"
    assert gray_attr.attribute_type == "scalar"


def test_color_parquet_roundtrip(color_image_rgb: Tuple[Path, int, int], mock_data_client: _MockDataClient):
    """Test that color values can be read back from parquet correctly."""
    import pyarrow.parquet as pq

    image_path, width, height = color_image_rgb
    converter = ImageGridConverter(mock_data_client, output_dir=str(mock_data_client.output_dir), output_parquet=True)

    grid = converter.convert(str(image_path))
    attr = grid.cell_attributes[0]

    # Read parquet file
    parquet_file = mock_data_client.output_dir / f"{attr.values.data}.parquet"
    assert parquet_file.exists()

    table = pq.read_table(parquet_file)
    assert table.schema.field(0).type == pa.int32()
    packed_colors = table.column("data").to_pylist()

    # Unpack and verify
    def unpack_rgba(color: int):
        color = color & 0xFFFFFFFF
        r = color & 0xFF
        g = (color >> 8) & 0xFF
        b = (color >> 16) & 0xFF
        a = (color >> 24) & 0xFF
        return [r, g, b, a]

    rgba_colors = [unpack_rgba(color) for color in packed_colors]

    # Verify bottom row colors
    expected_rgba = [
        [255, 0, 0, 255],  # Red
        [0, 255, 0, 255],  # Green
        [0, 0, 255, 255],  # Blue
        [255, 255, 255, 255],  # White
    ]
    np.testing.assert_array_equal(rgba_colors[:width], expected_rgba)


# ============================================================================
# BigTIFF Tests
# ============================================================================


class TestBigTiffDetection:
    """Test BigTIFF format detection."""

    def test_is_bigtiff_returns_false_for_standard_tiff(self, tmp_path: Path, mock_data_client: _MockDataClient):
        """Standard TIFF (version 42) should not be detected as BigTIFF."""
        # Create a standard TIFF file
        arr = np.random.randint(0, 256, (10, 10), dtype=np.uint8)
        tiff_path = tmp_path / "standard.tiff"
        Image.fromarray(arr, mode="L").save(tiff_path)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        assert not converter._is_bigtiff(str(tiff_path))

    def test_is_bigtiff_returns_false_for_png(self, tmp_path: Path, mock_data_client: _MockDataClient):
        """PNG format should not be detected as BigTIFF."""
        arr = np.random.randint(0, 256, (10, 10), dtype=np.uint8)
        png_path = tmp_path / "test.png"
        Image.fromarray(arr, mode="L").save(png_path)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        assert not converter._is_bigtiff(str(png_path))

    def test_is_bigtiff_returns_false_for_nonexistent_file(self, mock_data_client: _MockDataClient):
        """Nonexistent file should return False."""
        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        assert not converter._is_bigtiff("/nonexistent/file.tiff")

    @pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
    def test_read_bigtiff_single_band(self, tmp_path: Path, mock_data_client: _MockDataClient):
        """Test reading single-band BigTIFF returns grayscale data."""
        import rasterio
        from rasterio.transform import Affine

        # Create a simple 1-band BigTIFF
        width, height = 10, 8
        data = np.arange(height * width, dtype=np.float32).reshape(height, width)

        bigtiff_path = tmp_path / "test_1band.tif"
        with rasterio.open(
            str(bigtiff_path),
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=data.dtype,
            transform=Affine.identity(),
            TILED="YES",
            BIGTIFF="YES",  # Force BigTIFF format
        ) as dst:
            dst.write(data, 1)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        pixel_values, w, h, mode = converter._read_bigtiff(str(bigtiff_path))

        assert mode == "grayscale"
        assert w == width
        assert h == height
        assert pixel_values.dtype == np.float64
        assert len(pixel_values) == width * height


@pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
def test_extract_embedded_georeferencing_from_geotiff(tmp_path: Path, mock_data_client: _MockDataClient):
    """GeoTIFF transform should map to bottom-left origin and positive cell sizes."""
    import rasterio
    from rasterio.transform import from_origin

    width, height = 4, 3
    x_min = 500000.0
    y_max = 6200000.0
    x_res = 10.0
    y_res = 20.0
    transform = from_origin(x_min, y_max, x_res, y_res)

    data = np.arange(width * height, dtype=np.uint8).reshape(height, width)
    tif_path = tmp_path / "georef_test.tif"
    with rasterio.open(
        str(tif_path),
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        transform=transform,
        crs="EPSG:25832",
    ) as dst:
        dst.write(data, 1)

    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    georef = converter._extract_embedded_georeferencing(str(tif_path), width, height)

    assert georef is not None
    assert georef["origin"] == [x_min, y_max - (height * y_res), 0.0]
    assert georef["cell_size"] == [x_res, y_res]


@pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
def test_convert_uses_embedded_georeferencing_for_geotiff(tmp_path: Path, mock_data_client: _MockDataClient):
    """End-to-end conversion should use embedded GeoTIFF georeferencing when not explicitly provided."""
    import rasterio
    from rasterio.transform import from_origin

    width, height = 4, 3
    x_min = 500000.0
    y_max = 6200000.0
    x_res = 10.0
    y_res = 20.0
    transform = from_origin(x_min, y_max, x_res, y_res)

    data = np.arange(width * height, dtype=np.uint8).reshape(height, width)
    tif_path = tmp_path / "georef_convert.tif"
    with rasterio.open(
        str(tif_path),
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        transform=transform,
        crs="EPSG:25832",
    ) as dst:
        dst.write(data, 1)

    converter = ImageGridConverter(mock_data_client, output_parquet=False)
    grid = converter.convert(str(tif_path))

    assert grid.origin == [x_min, y_max - (height * y_res), 0.0]
    assert grid.cell_size == [x_res, y_res]

    @pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
    def test_read_bigtiff_three_bands(self, tmp_path: Path, mock_data_client: _MockDataClient):
        """Test reading 3-band BigTIFF returns RGB data."""
        import rasterio
        from rasterio.transform import Affine

        width, height = 10, 8
        r_data = np.full((height, width), 255, dtype=np.uint8)
        g_data = np.full((height, width), 128, dtype=np.uint8)
        b_data = np.full((height, width), 64, dtype=np.uint8)

        bigtiff_path = tmp_path / "test_3band.tif"
        with rasterio.open(
            str(bigtiff_path),
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=3,
            dtype=np.uint8,
            transform=Affine.identity(),
            TILED="YES",
            BIGTIFF="YES",
        ) as dst:
            dst.write(r_data, 1)
            dst.write(g_data, 2)
            dst.write(b_data, 3)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        pixel_values, w, h, mode = converter._read_bigtiff(str(bigtiff_path))

        assert mode == "color"
        assert w == width
        assert h == height
        assert pixel_values.shape == (width * height, 3)
        assert pixel_values.dtype == np.uint8
        # Verify each pixel has the expected RGB values
        for i in range(width * height):
            np.testing.assert_array_equal(pixel_values[i], [255, 128, 64])

    @pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
    def test_read_bigtiff_many_bands(self, tmp_path: Path, mock_data_client: _MockDataClient):
        """Test reading many-band BigTIFF uses first 3 bands as RGB."""
        import rasterio
        from rasterio.transform import Affine

        width, height = 8, 6
        band_count = 10

        bigtiff_path = tmp_path / "test_manyband.tif"
        with rasterio.open(
            str(bigtiff_path),
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=band_count,
            dtype=np.uint8,
            transform=Affine.identity(),
            TILED="YES",
            BIGTIFF="YES",
        ) as dst:
            for i in range(band_count):
                data = np.full((height, width), 50 + i * 10, dtype=np.uint8)
                dst.write(data, i + 1)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        pixel_values, w, h, mode = converter._read_bigtiff(str(bigtiff_path))

        assert mode == "color"
        assert w == width
        assert h == height
        assert pixel_values.shape == (width * height, 3)
        # Verify each pixel uses first 3 bands (50, 60, 70)
        for i in range(width * height):
            np.testing.assert_array_equal(pixel_values[i], [50, 60, 70])

    @pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
    def test_read_bigtiff_two_bands_averages_to_grayscale(self, tmp_path: Path, mock_data_client: _MockDataClient):
        """Test reading 2-band BigTIFF averages to grayscale."""
        import rasterio
        from rasterio.transform import Affine

        width, height = 8, 6
        b1_data = np.full((height, width), 100.0, dtype=np.float32)
        b2_data = np.full((height, width), 200.0, dtype=np.float32)

        bigtiff_path = tmp_path / "test_2band.tif"
        with rasterio.open(
            str(bigtiff_path),
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=2,
            dtype=np.float32,
            transform=Affine.identity(),
            TILED="YES",
            BIGTIFF="YES",
        ) as dst:
            dst.write(b1_data, 1)
            dst.write(b2_data, 2)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        pixel_values, w, h, mode = converter._read_bigtiff(str(bigtiff_path))

        assert mode == "grayscale"
        assert w == width
        assert h == height
        assert pixel_values.dtype == np.float64
        # Average of 100 and 200 is 150
        np.testing.assert_array_almost_equal(pixel_values[0], 150.0)

    @pytest.mark.skipif(not HAS_RASTERIO, reason="rasterio not installed")
    def test_read_bigtiff_float_rgb_bands_normalized_to_uint8(self, tmp_path: Path, mock_data_client: _MockDataClient):
        """Float/NaN RGB bands should be normalized safely to uint8 without cast errors."""
        import rasterio
        from rasterio.transform import Affine

        width, height = 4, 3
        r_data = np.array(
            [
                [-10.0, 0.0, 100.0, np.nan],
                [200.0, 300.0, 400.0, 500.0],
                [600.0, 700.0, 800.0, 900.0],
            ],
            dtype=np.float32,
        )
        g_data = r_data + 5.0
        b_data = r_data + 10.0

        bigtiff_path = tmp_path / "test_float_rgb.tif"
        with rasterio.open(
            str(bigtiff_path),
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=3,
            dtype=np.float32,
            transform=Affine.identity(),
            TILED="YES",
            BIGTIFF="YES",
        ) as dst:
            dst.write(r_data, 1)
            dst.write(g_data, 2)
            dst.write(b_data, 3)

        converter = ImageGridConverter(mock_data_client, output_parquet=False)
        pixel_values, w, h, mode = converter._read_bigtiff(str(bigtiff_path))

        assert mode == "color"
        assert w == width
        assert h == height
        assert pixel_values.shape == (width * height, 3)
        assert pixel_values.dtype == np.uint8
        assert int(pixel_values.min()) >= 0
        assert int(pixel_values.max()) <= 255
