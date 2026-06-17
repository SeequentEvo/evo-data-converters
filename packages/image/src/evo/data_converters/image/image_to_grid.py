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
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np
from PIL import Image

import pyarrow as pa
import pyarrow.parquet as pq

import evo.logging
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects_sync,
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

        Supports JPEG, PNG, TIFF, BMP, GIF, and other formats supported by PIL/Pillow.

        For grayscale images (mode L, LA): returns single float64 array.
        For color images (mode RGB, RGBA): returns uint8 RGB array (flattened, one value per pixel = 3 bytes RGB).

        :param image_path: Path to the image file
        :return: Tuple of (pixel_values (float64 or uint8 array), width, height, mode_type)
             mode_type is either 'grayscale' or 'color'
             Pixel values are flattened row-major starting from the bottom row so
             index 0 maps to the grid origin (bottom-left convention).
        """
        logger.info(f"Reading image file: {image_path}")

        with Image.open(image_path) as img:
            width, height = img.size
            original_mode = img.mode
            logger.info(f"Image dimensions: {width}x{height}, mode: {original_mode}")

            # Determine if grayscale or color
            if original_mode in ("L", "LA"):
                # Grayscale: convert to single channel float64
                if original_mode == "LA":
                    # Drop alpha channel for grayscale
                    grayscale_img = img.convert("L")
                else:
                    grayscale_img = img

                pixel_array = np.asarray(grayscale_img, dtype=np.float64)
                cell_values = np.flipud(pixel_array).ravel(order="C")
                logger.info("Image is grayscale, returning single float64 array")
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
        grid_origin = origin or [0.0, 0.0, 0.0]
        grid_cell_size = cell_size or [1.0, 1.0]

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
        if coordinate_reference_system:
            if isinstance(coordinate_reference_system, dict):
                if "epsg_code" in coordinate_reference_system:
                    crs = Crs_V1_0_1_EpsgCode(epsg_code=coordinate_reference_system["epsg_code"])
                elif "ogc_wkt" in coordinate_reference_system:
                    crs = coordinate_reference_system["ogc_wkt"]  # WKT string
            else:
                crs = coordinate_reference_system

        # Assemble Regular 2D Grid object
        grid = Regular2DGrid_V1_3_0(
            name=grid_name,
            uuid=None,  # Let the system generate
            description=grid_description,
            tags=tags,
            bounding_box=bbox,
            coordinate_reference_system=crs
            if crs is not None
            else Crs_V1_0_1_EpsgCode(epsg_code=4326),  # default WGS84
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
