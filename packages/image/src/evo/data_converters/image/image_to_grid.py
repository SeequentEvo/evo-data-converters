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
Image to Regular 2D Grid Converter

This module converts images (JPEG, PNG, TIFF, etc.) into Geoscience Objects following the
regular-2d-grid schema. It reads pixel values from image files and creates properly formatted
JSON with associated parquet data files.
"""

from __future__ import annotations

import io
import hashlib
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np
from PIL import Image

try:
    import rasterio

    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

import pyarrow as pa
import pyarrow.parquet as pq

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects_sync,
    crs_from_ogc_wkt,
    crs_unspecified,
)

from evo.objects.utils.data import ObjectDataClient
from evo_schemas.objects import Regular2DGrid_V1_3_0
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Rotation_V1_1_0,
    OneOfAttribute_V1_2_0,
    ContinuousAttribute_V1_1_0,
    ColorAttribute_V1_1_0,
    NanContinuous_V1_0_1,
    AttributeDescription_V1_0_1,
    Crs_V1_0_1_EpsgCode,
)
from evo_schemas.elements import FloatArray1_V1_0_1, ColorArray_V1_0_1

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


def _normalize_array_data_type(pa_type: pa.DataType) -> str:
    """Map PyArrow type names to evo_schemas data_type values."""
    arrow_name = str(pa_type)
    if arrow_name == "double":
        return "float64"
    return arrow_name


# -----------------------------------------------------------------------------
# Parquet writer options recommended by geoscience object schemas
# -----------------------------------------------------------------------------
def geoscience_object_data_options() -> dict:
    """Enforce required options for writing Parquet files for geoscience object schemas."""
    return {
        "version": "2.4",
        "flavor": None,
        "data_page_size": None,
        "compression": "gzip",
        "encryption_properties": None,
    }


# -----------------------------------------------------------------------------
# Local stub data client for offline runs (no Evo credentials required)
# -----------------------------------------------------------------------------
class _LocalObjectDataClientStub:
    """
    Minimal stand-in for ObjectDataClient when running offline.
    - Writes the provided Arrow table to ./parquet_arrays/<sha256>.parquet
    - Returns a dict with keys that mirror the real client's save_table result.
    """

    def __init__(self, output_dir: str = "./parquet_arrays"):
        self.output_path = Path(output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)

    def save_table(self, table: pa.Table):
        # Serialize to memory to compute a stable content hash
        buf = io.BytesIO()
        pq.write_table(table, buf, **geoscience_object_data_options())
        data = buf.getvalue()
        data_hash = hashlib.sha256(data).hexdigest()

        # Persist a local copy so you can inspect/debug the parquet
        (self.output_path / f"{data_hash}.parquet").write_bytes(data)

        first_field = table.schema.field(0)

        # Shape matches what the converter expects from the real data client
        # (include basic metadata commonly used by downstream code)
        return {
            "data": data_hash,
            "length": table.num_rows,
            "width": 1,
            "data_type": _normalize_array_data_type(first_field.type),
        }


# -----------------------------------------------------------------------------
# Core converter implementation
# -----------------------------------------------------------------------------
class ImageGridConverter:
    """Converts images (JPEG, PNG, TIFF, etc.) to Regular 2D Grid format."""

    def __init__(
        self,
        data_client: ObjectDataClient | _LocalObjectDataClientStub | None,
        output_dir: str = "./parquet_arrays",
        output_parquet: bool = False,
    ):
        """Initialize the Image to Grid converter.

        :param data_client: Object data client for uploading parquet files (real or stub). If None, the
                            converter will still compute a content hash and optionally write a local parquet
                            when output_parquet=True.
        :param output_dir: Directory to store parquet files
        :param output_parquet: Whether to write parquet files to disk (for debugging)
        """
        self.data_client = data_client
        self.output_dir = output_dir
        self.output_path = Path(output_dir)
        self.output_parquet = output_parquet

    def _read_image(self, image_path: str) -> tuple[np.ndarray, int, int, str]:
        """Read image file and preserve its color mode (grayscale or RGB).

        Supports JPEG, PNG, TIFF, BMP, GIF, BigTIFF, and other formats.
        For BigTIFF files (multi-band GeoTIFF), uses rasterio.
        For standard images, uses PIL/Pillow.

        For grayscale images (mode L, LA): returns single float64 array.
        For color images (mode RGB, RGBA): returns uint8 RGB array (flattened, one value per pixel = 3 bytes RGB).

        :param image_path: Path to the image file
        :return: Tuple of (pixel_values (float64 or uint8 array), width, height, mode_type)
             mode_type is either 'grayscale' or 'color'
             Pixel values are flattened row-major starting from the bottom row so
             index 0 maps to the grid origin (bottom-left convention).
        """
        logger.info(f"Reading image file: {image_path}")

        # Check for BigTIFF first
        if self._is_bigtiff(image_path):
            return self._read_bigtiff(image_path)

        with Image.open(image_path) as img:
            width, height = img.size
            original_mode = img.mode
            logger.info(f"Image dimensions: {width}x{height}, mode: {original_mode}")

            # Determine if grayscale or color.
            # Scientific GeoTIFF rasters are commonly single-band in F/I modes.
            grayscale_modes = {"1", "L", "LA", "I", "I;16", "I;16B", "I;16L", "F"}
            if original_mode in grayscale_modes:
                # Grayscale: convert to single channel float64
                if original_mode in ("LA",):
                    # Drop alpha channel for grayscale
                    grayscale_img = img.convert("L")
                elif original_mode == "1":
                    # Binary images mapped to 0/255 grayscale before float conversion
                    grayscale_img = img.convert("L")
                else:
                    grayscale_img = img

                pixel_array = np.asarray(grayscale_img, dtype=np.float64)
                cell_values = np.flipud(pixel_array).ravel(order="C")
                logger.info(f"Image mode '{original_mode}' treated as grayscale")
                return cell_values, width, height, "grayscale"

            else:
                # Color image: preserve RGB channels (drop alpha if present)
                color_img = img.convert("RGB") if original_mode in ("RGBA", "P", "LA") else img

                # Get uint8 RGB array
                pixel_array = np.asarray(color_img, dtype=np.uint8)  # shape: (height, width, 3)

                # Flip vertically and flatten to 1D for color storage
                pixel_array_flipped = np.flipud(pixel_array)
                # Reshape to (height*width, 3) then flatten to 1D with RGB interleaved
                cell_values = pixel_array_flipped.reshape(-1, 3).astype(np.uint8)
                logger.info(f"Image is color (RGB), returning uint8 array of shape {cell_values.shape}")
                return cell_values, width, height, "color"

    @staticmethod
    def _extract_epsg_from_geokey_directory(geokey_directory: tuple) -> int | None:
        """Extract EPSG code from GeoTIFF GeoKeyDirectoryTag (34735) when available.

        The GeoKeyDirectory structure is:
        - 4-value header
        - N key entries, each as (key_id, tiff_tag_location, count, value_offset)

        For EPSG-like keys, tiff_tag_location is typically 0 and value_offset carries
        the numeric code directly.
        """
        if not geokey_directory or len(geokey_directory) < 8:
            return None

        # GeoKey IDs that can carry authority codes.
        # Prefer projected CRS, then geographic, then vertical.
        preferred_keys = (3072, 2048, 4096)

        try:
            number_of_keys = int(geokey_directory[3])
            entries = geokey_directory[4 : 4 + (number_of_keys * 4)]
        except (TypeError, ValueError, IndexError):
            return None

        values_by_key: dict[int, int] = {}
        for i in range(0, len(entries), 4):
            try:
                key_id = int(entries[i])
                tiff_tag_location = int(entries[i + 1])
                count = int(entries[i + 2])
                value_offset = int(entries[i + 3])
            except (TypeError, ValueError, IndexError):
                continue

            # For scalar inline keys (common for CRS authority codes), use value_offset.
            if tiff_tag_location == 0 and count == 1 and value_offset > 0:
                values_by_key[key_id] = value_offset

        for key_id in preferred_keys:
            epsg_code = values_by_key.get(key_id)
            # 32767 denotes user-defined/not an EPSG authority code.
            if epsg_code and epsg_code != 32767:
                return epsg_code

        return None

    @staticmethod
    def _is_bigtiff(image_path: str) -> bool:
        """Check if file is BigTIFF format (not standard TIFF).

        BigTIFF signature is TIFF header (II/MM) followed by 0x002b (little-endian) or 0x2b00 (big-endian).
        """
        try:
            with open(image_path, "rb") as f:
                sig = f.read(4)
                if len(sig) < 4:
                    return False
                # Check for TIFF signature (II=little-endian or MM=big-endian)
                # followed by version 42 (standard TIFF) or version 43 (BigTIFF)
                if sig[:2] in (b"II", b"MM"):
                    version = int.from_bytes(sig[2:4], byteorder="little" if sig[0:1] == b"I" else "big")
                    return version == 43  # 43 = BigTIFF, 42 = standard TIFF
        except Exception:
            pass
        return False

    @staticmethod
    def _read_bigtiff(image_path: str) -> tuple[np.ndarray, int, int, str]:
        """Read BigTIFF file using rasterio and extract multi-band data.

        Strategy:
        - 1 band: return as grayscale (float64).
        - 3 bands: return as RGB (uint8).
        - 4+ bands: use first 3 as RGB, or average all to grayscale if 2 or 5+ bands.
        - 2 bands: average to grayscale.

        Returns: (pixel_values, width, height, mode_type)
        """
        if not HAS_RASTERIO:
            raise ImportError("rasterio is required for BigTIFF support. Install with: pip install rasterio")

        logger.info(f"Reading BigTIFF file via rasterio: {image_path}")

        with rasterio.open(image_path) as src:
            width = src.width
            height = src.height
            band_count = src.count

            logger.info(f"BigTIFF dimensions: {width}x{height}, bands: {band_count}")

            # Read data based on band count
            if band_count == 1:
                # Single band: return as grayscale float64
                data = src.read(1).astype(np.float64)
                pixel_array = np.flipud(data)
                cell_values = pixel_array.ravel(order="C")
                return cell_values, width, height, "grayscale"

            elif band_count == 3:
                # 3 bands: return as RGB uint8
                r = ImageGridConverter._normalize_band_to_uint8(src.read(1))
                g = ImageGridConverter._normalize_band_to_uint8(src.read(2))
                b = ImageGridConverter._normalize_band_to_uint8(src.read(3))
                # Stack into (height, width, 3)
                rgb_array = np.dstack((r, g, b))
                rgb_flipped = np.flipud(rgb_array)
                cell_values = rgb_flipped.reshape(-1, 3).astype(np.uint8)
                return cell_values, width, height, "color"

            elif band_count >= 4:
                # 4+ bands: use first 3 as RGB uint8
                logger.info(f"BigTIFF has {band_count} bands; using first 3 as RGB")
                r = ImageGridConverter._normalize_band_to_uint8(src.read(1))
                g = ImageGridConverter._normalize_band_to_uint8(src.read(2))
                b = ImageGridConverter._normalize_band_to_uint8(src.read(3))
                rgb_array = np.dstack((r, g, b))
                rgb_flipped = np.flipud(rgb_array)
                cell_values = rgb_flipped.reshape(-1, 3).astype(np.uint8)
                return cell_values, width, height, "color"

            else:
                # 2 bands: average to grayscale
                logger.info(f"BigTIFF has {band_count} bands; averaging to grayscale")
                band1 = src.read(1).astype(np.float64)
                band2 = src.read(2).astype(np.float64)
                avg = (band1 + band2) / 2.0
                avg_flipped = np.flipud(avg)
                cell_values = avg_flipped.ravel(order="C")
                return cell_values, width, height, "grayscale"

    @staticmethod
    def _normalize_band_to_uint8(band: np.ndarray) -> np.ndarray:
        """Normalize a raster band safely to uint8 (0..255).

        - Non-finite values become 0.
        - If data is already in 0..255, only clip and cast.
        - Otherwise min-max scale finite values to 0..255.
        """
        band_f = np.asarray(band, dtype=np.float64)
        finite_mask = np.isfinite(band_f)

        if not np.any(finite_mask):
            return np.zeros(band_f.shape, dtype=np.uint8)

        finite_values = band_f[finite_mask]
        min_value = float(finite_values.min())
        max_value = float(finite_values.max())

        if 0.0 <= min_value and max_value <= 255.0:
            normalized = np.clip(band_f, 0.0, 255.0)
        elif max_value > min_value:
            normalized = (band_f - min_value) / (max_value - min_value)
            normalized = np.clip(normalized * 255.0, 0.0, 255.0)
        else:
            normalized = np.zeros(band_f.shape, dtype=np.float64)

        normalized[~finite_mask] = 0.0
        return np.rint(normalized).astype(np.uint8)

    @staticmethod
    def _extract_wkt_candidate_from_text(text: str) -> str | None:
        """Extract a likely WKT CRS block from free-form text.

        Handles both WKT1 (GEOGCS/PROJCS) and WKT2 (GEOGCRS/PROJCRS) prefixes.
        """
        if not text:
            return None

        prefixes = (
            "GEOGCS[",
            "PROJCS[",
            "LOCAL_CS[",
            "GEOGCRS[",
            "PROJCRS[",
            "BOUNDCRS[",
            "COMPOUNDCRS[",
            "VERTCRS[",
            "ENGCRS[",
        )

        start_index = -1
        for prefix in prefixes:
            idx = text.find(prefix)
            if idx != -1 and (start_index == -1 or idx < start_index):
                start_index = idx

        if start_index == -1:
            return None

        wkt_like = text[start_index:]

        # Trim to the first balanced bracket block.
        depth = 0
        for i, char in enumerate(wkt_like):
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return wkt_like[: i + 1]

        return None

    def _extract_embedded_coordinate_reference_system(self, image_path: str) -> Optional[dict[str, int | str]]:
        """Try to extract embedded CRS from GeoTIFF metadata.

        Returns an EPSG or OGC WKT CRS dict suitable for converter input when available,
        otherwise returns None.
        """
        suffix = Path(image_path).suffix.lower()
        if suffix not in {".tif", ".tiff", ".cog"}:
            return None

        # Avoid Pillow limitations/noise for BigTIFF; query CRS directly from rasterio.
        if self._is_bigtiff(image_path):
            if not HAS_RASTERIO:
                return None

            try:
                with rasterio.open(image_path) as src:
                    if src.crs:
                        epsg_code = src.crs.to_epsg()
                        if epsg_code:
                            logger.info(f"Detected embedded BigTIFF EPSG:{epsg_code} via rasterio")
                            return {"epsg_code": int(epsg_code)}

                        wkt_text = src.crs.to_wkt()
                        if wkt_text:
                            logger.info("Detected embedded BigTIFF WKT via rasterio")
                            return {"ogc_wkt": wkt_text}
            except Exception as e:  # pragma: no cover - defensive parsing path
                logger.debug(f"Failed to read BigTIFF CRS from '{image_path}' via rasterio: {e}")

            return None

        try:
            with Image.open(image_path) as img:
                tags = getattr(img, "tag_v2", None)
                if not tags:
                    return None

                geokey_directory = tags.get(34735)
                if geokey_directory:
                    epsg_code = self._extract_epsg_from_geokey_directory(geokey_directory)
                    if epsg_code:
                        logger.info(f"Detected embedded GeoTIFF EPSG:{epsg_code} from tag 34735")
                        return {"epsg_code": epsg_code}

                # Fallback: parse embedded WKT from GDAL/TIFF text tags.
                # 42112 often stores GDAL metadata XML and may include an SRS item.
                gdal_metadata = tags.get(42112)
                if gdal_metadata:
                    gdal_metadata_text = str(gdal_metadata)
                    srs_match = re.search(
                        r'<Item[^>]*name="SRS"[^>]*>(.*?)</Item>',
                        gdal_metadata_text,
                        flags=re.DOTALL,
                    )
                    if srs_match:
                        wkt_candidate = self._extract_wkt_candidate_from_text(srs_match.group(1))
                        if wkt_candidate:
                            logger.info("Detected embedded GeoTIFF WKT from GDAL metadata tag 42112")
                            return {"ogc_wkt": wkt_candidate}

                    wkt_candidate = self._extract_wkt_candidate_from_text(gdal_metadata_text)
                    if wkt_candidate:
                        logger.info("Detected embedded GeoTIFF WKT-like text from tag 42112")
                        return {"ogc_wkt": wkt_candidate}

                # 34737 (GeoAsciiParamsTag) may include WKT text in some files.
                geotiff_ascii = tags.get(34737)
                if geotiff_ascii:
                    wkt_candidate = self._extract_wkt_candidate_from_text(str(geotiff_ascii))
                    if wkt_candidate:
                        logger.info("Detected embedded GeoTIFF WKT-like text from tag 34737")
                        return {"ogc_wkt": wkt_candidate}
        except Exception as e:  # pragma: no cover - defensive parsing path
            logger.debug(f"Failed to read embedded GeoTIFF CRS from '{image_path}': {e}")

        return None

    def _extract_embedded_georeferencing(
        self,
        image_path: str,
        width: int,
        height: int,
    ) -> Optional[dict[str, list[float]]]:
        """Try to extract origin and cell size from embedded GeoTIFF metadata.

        Returns a dict with:
        - origin: [x_min, y_min, z]
        - cell_size: [dx, dy]

        The converter uses bottom-left origin convention with positive cell sizes.
        """
        suffix = Path(image_path).suffix.lower()
        if suffix not in {".tif", ".tiff", ".cog"}:
            return None

        if not HAS_RASTERIO:
            return None

        try:
            with rasterio.open(image_path) as src:
                bounds = src.bounds

                # Rotated/sheared transforms are not representable with axis-aligned
                # origin + cell_size in Regular2DGrid.
                transform = src.transform
                if transform.b != 0 or transform.d != 0:
                    logger.warning(
                        "GeoTIFF has rotated/sheared transform; using default origin/cell_size for '%s'",
                        image_path,
                    )
                    return None

                if width <= 0 or height <= 0:
                    return None

                dx = float((bounds.right - bounds.left) / width)
                dy = float((bounds.top - bounds.bottom) / height)

                if dx <= 0 or dy <= 0:
                    return None

                origin = [float(bounds.left), float(bounds.bottom), 0.0]
                cell_size = [dx, dy]
                logger.info(
                    "Detected embedded GeoTIFF georeferencing origin=%s cell_size=%s",
                    origin,
                    cell_size,
                )
                return {"origin": origin, "cell_size": cell_size}
        except Exception as e:  # pragma: no cover - defensive parsing path
            logger.debug(f"Failed to read embedded GeoTIFF georeferencing from '{image_path}': {e}")

        return None

    def _create_parquet_file(self, table: pa.Table) -> tuple[dict[str, str | int], Path | None]:
        """Create parquet file and return (save_table_like_metadata, local_path_if_any).

        If a data_client is present (real or stub), use it. Otherwise, compute the hash and
        optionally write a local file only when output_parquet=True.
        """
        # Prefer the provided data_client (real Evo or local stub)
        if self.data_client is not None:
            logger.info("Saving parquet table via data_client.save_table(...)")
            saved_table_info = self.data_client.save_table(table)
            data_hash = saved_table_info["data"]

            local_path: Path | None = None
            if self.output_parquet:
                self.output_path.mkdir(parents=True, exist_ok=True)
                local_path = self.output_path / f"{data_hash}.parquet"
                pq.write_table(table, local_path, **geoscience_object_data_options())
            return saved_table_info, local_path

        # No data_client provided: compute a content hash locally
        logger.info("No data_client provided; computing local parquet + hash")
        buf = io.BytesIO()
        pq.write_table(table, buf, **geoscience_object_data_options())
        raw = buf.getvalue()
        data_hash = hashlib.sha256(raw).hexdigest()

        first_field = table.schema.field(0)
        saved_table_info: dict[str, str | int] = {
            "data": data_hash,
            "length": table.num_rows,
            "width": 1,
            "data_type": _normalize_array_data_type(first_field.type),
        }

        local_path = None
        if self.output_parquet:
            self.output_path.mkdir(parents=True, exist_ok=True)
            local_path = self.output_path / f"{data_hash}.parquet"
            local_path.write_bytes(raw)
        return saved_table_info, local_path

    def _create_cell_attribute(
        self, cell_values: np.ndarray, width: int, height: int, image_mode: str
    ) -> ContinuousAttribute_V1_1_0 | ColorAttribute_V1_1_0:
        """Create cell attribute from pixel values (grayscale or color)."""
        if image_mode == "grayscale":
            logger.info("Creating grayscale cell attribute from pixel data")
            # Arrow table of float64 values
            table = pa.table({"data": cell_values})
        else:  # color
            logger.info("Creating color cell attribute from pixel data")
            # Pack RGB into 0xAABBGGRR uint32 (A=255 fully opaque), one value per pixel
            # This matches the ColorArray_V1_0_1 expected format (little-endian RGBA)
            r = cell_values[:, 0].astype(np.uint32)
            g = cell_values[:, 1].astype(np.uint32)
            b = cell_values[:, 2].astype(np.uint32)
            packed = r | (g << 8) | (b << 16) | np.uint32(0xFF000000)
            packed_i32 = packed.view(np.int32)
            schema = pa.schema([("data", pa.int32())])
            table = pa.Table.from_arrays([pa.array(packed_i32, type=pa.int32())], schema=schema)

        # Persist parquet (via data_client or locally) and get metadata
        array_args, _ = self._create_parquet_file(table)
        data_hash = str(array_args["data"])

        if image_mode == "grayscale":
            # Grayscale continuous attribute
            attribute_description = AttributeDescription_V1_0_1(
                discipline="Imagery",
                type="Grayscale Intensity",
            )

            nan_description = NanContinuous_V1_0_1(values=[-1.0000000331813535e32, -1e32])

            values = FloatArray1_V1_0_1.from_dict(array_args)

            attribute = ContinuousAttribute_V1_1_0(
                name="2d-grid-data-continuous",
                key=data_hash,
                attribute_type="scalar",
                attribute_description=attribute_description,
                nan_description=nan_description,
                values=values,
            )
            return attribute
        else:  # color
            # Color attribute
            color_array_args = {
                "data": data_hash,
                "length": int(array_args.get("length", width * height)),
                "data_type": "uint32",
            }
            color_values = ColorArray_V1_0_1.from_dict(color_array_args)

            attribute = ColorAttribute_V1_1_0(
                name="2d-grid-data-color",
                key=data_hash,
                values=color_values,
            )
            return attribute

    def convert(
        self,
        image_path: str,
        origin: Optional[list[float]] = None,
        cell_size: Optional[list[float]] = None,
        coordinate_reference_system: Optional[dict] = None,
        tags: Optional[dict[str, str]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Regular2DGrid_V1_3_0:
        """Convert an image file to a Regular 2D Grid object.

        Preserves color images as RGB (ColorAttribute_V1_1_0).
        Grayscale images returned as float64 intensity (ContinuousAttribute_V1_1_0).
        """

        # Read and preprocess image (detect grayscale vs color)
        cell_values, width, height, image_mode = self._read_image(image_path)

        # Defaults
        grid_name = name or Path(image_path).stem
        grid_description = description or "A 2D grid from image"

        embedded_georeferencing = None
        if origin is None or cell_size is None:
            embedded_georeferencing = self._extract_embedded_georeferencing(image_path, width, height)

        if origin is not None:
            grid_origin = origin
        elif embedded_georeferencing and "origin" in embedded_georeferencing:
            grid_origin = embedded_georeferencing["origin"]
        else:
            grid_origin = [0.0, 0.0, 0.0]

        if cell_size is not None:
            grid_cell_size = cell_size
        elif embedded_georeferencing and "cell_size" in embedded_georeferencing:
            grid_cell_size = embedded_georeferencing["cell_size"]
        else:
            grid_cell_size = [1.0, 1.0]

        # Bounding box (from origin, grid size, and cell size)
        bbox = BoundingBox_V1_0_1(
            min_x=grid_origin[0],
            min_y=grid_origin[1],
            min_z=grid_origin[2],
            max_x=grid_origin[0] + (width * grid_cell_size[0]),
            max_y=grid_origin[1] + (height * grid_cell_size[1]),
            max_z=grid_origin[2],  # 2D grid, z constant
        )

        # Rotation (default none)
        rotation = Rotation_V1_1_0(dip=0.0, dip_azimuth=0.0, pitch=0.0)

        # Cell attribute: single attribute for either grayscale or color
        cell_attribute = self._create_cell_attribute(cell_values, width, height, image_mode)
        cell_attributes_list = OneOfAttribute_V1_2_0()
        cell_attributes_list.append(cell_attribute)

        # CRS
        crs = None
        effective_coordinate_reference_system = coordinate_reference_system
        if effective_coordinate_reference_system is None:
            effective_coordinate_reference_system = self._extract_embedded_coordinate_reference_system(image_path)

        if effective_coordinate_reference_system:
            if isinstance(effective_coordinate_reference_system, dict):
                if "epsg_code" in effective_coordinate_reference_system:
                    crs = Crs_V1_0_1_EpsgCode(epsg_code=effective_coordinate_reference_system["epsg_code"])
                elif "ogc_wkt" in effective_coordinate_reference_system:
                    crs = crs_from_ogc_wkt(effective_coordinate_reference_system["ogc_wkt"])
            else:
                crs = effective_coordinate_reference_system
        else:
            # No CRS provided: use unspecified to preserve data integrity
            crs = crs_unspecified()

        # Assemble Regular 2D Grid object
        grid = Regular2DGrid_V1_3_0(
            name=grid_name,
            uuid=None,  # Let the system generate
            description=grid_description,
            tags=tags,
            bounding_box=bbox,
            coordinate_reference_system=crs,
            origin=grid_origin,
            size=[width, height],
            cell_size=grid_cell_size,
            schema="/objects/regular-2d-grid/1.3.0/regular-2d-grid.schema.json",
            rotation=rotation,
            cell_attributes=cell_attributes_list,
        )

        logger.info(f"Successfully converted {image_mode} image to Regular 2D Grid: {grid.name} ({width}x{height})")
        return grid


# -----------------------------------------------------------------------------
# Convenience function that supports both offline (no publish) and online publish
# -----------------------------------------------------------------------------
def convert_image_to_grid(
    image_path: str,
    origin: Optional[list[float]] = None,
    cell_size: Optional[list[float]] = None,
    coordinate_reference_system: Optional[dict] = None,
    tags: Optional[dict[str, str]] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    upload_path: str = "",
    output_dir: str = "./parquet_arrays",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list:
    """
    Convert an image (JPEG, PNG, TIFF, etc.) to a Regular 2D Grid Geoscience Object.

    Returns:
        - If publish_objects=True: list[ObjectMetadata]
        - If publish_objects=False: list[Regular2DGrid]

    One of evo_workspace_metadata or service_manager_widget is required for publishing.
    """

    # Choose data client per mode
    if publish_objects:
        # Online path: real Evo clients (requires credentials)
        object_service_client, data_client = create_evo_object_service_and_data_client(
            evo_workspace_metadata=evo_workspace_metadata,
            service_manager_widget=service_manager_widget,
        )
    else:
        # Offline path: local stub (no credentials); still writes a local parquet and computes hash
        object_service_client = None
        data_client = _LocalObjectDataClientStub(output_dir=output_dir)

    # Convert (this will write parquet via data_client: real or stub)
    converter = ImageGridConverter(data_client, output_parquet=False)
    grid_object = converter.convert(
        image_path=image_path,
        origin=origin,
        cell_size=cell_size,
        coordinate_reference_system=coordinate_reference_system,
        tags=tags,
        name=name,
        description=description,
    )

    geoscience_objects = [grid_object]

    if publish_objects:
        logger.debug("Publishing Geoscience Objects")

        # Remove 'uuid' if None (your original behavior) before publishing
        for obj in geoscience_objects:
            original_as_dict = obj.as_dict

            def as_dict_remove_none_uuid(orig_method=original_as_dict, obj_ref=obj):
                d = orig_method()
                if getattr(obj_ref, "uuid", None) is None and "uuid" in d:
                    d.pop("uuid")
                return d

            obj.as_dict = as_dict_remove_none_uuid

        objects_metadata = publish_geoscience_objects_sync(
            geoscience_objects,
            object_service_client,
            data_client,
            upload_path,
            overwrite_existing_objects,
        )
        return objects_metadata

    # Offline: return objects for inspection
    return geoscience_objects
