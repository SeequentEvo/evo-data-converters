# --------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Bentley Systems, Incorporated. All rights reserved.
# --------------------------------------------------------------------------------------------

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
    NanContinuous_V1_0_1,
    AttributeDescription_V1_0_1,
    Crs_V1_0_1_EpsgCode,
)
from evo_schemas.elements import FloatArray1_V1_0_1

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


# -----------------------------------------------------------------------------
# Parquet writer options recommended by geoscience object schemas
# -----------------------------------------------------------------------------
def geoscience_object_data_options() -> dict:
    """Enforce required options for writing Parquet files for geoscience object schemas.
    See: https://github.com/seequent/geoscience-object-schemas/blob/main/doc/blob-storage.md#parquet-file-writing-options
    """
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

        # Shape matches what the converter expects from the real data client
        # (include basic metadata commonly used by downstream code)
        return {
            "data": data_hash,
            "length": table.num_rows,
            "width": 1,
            "data_type": "float64",
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

    def _read_image_as_grayscale(self, image_path: str) -> tuple[np.ndarray, int, int]:
        """Read image file and convert to grayscale values.

        Supports JPEG, PNG, TIFF, BMP, GIF, and other formats supported by PIL/Pillow.

        :param image_path: Path to the image file
        :return: Tuple of (flattened pixel_values (float64), width, height)
        """
        logger.info(f"Reading image file: {image_path}")

        with Image.open(image_path) as img:
            grayscale_img = img.convert("L")  # luminance
            width, height = grayscale_img.size
            logger.info(f"Image dimensions: {width}x{height}")

            # Vectorized conversion to 1D float64 (row-major)
            cell_values = np.asarray(grayscale_img, dtype=np.float64).ravel(order="C")

        return cell_values, width, height

    def _create_parquet_file(self, table: pa.Table) -> tuple[str, Path | None]:
        """Create parquet file and return (hash, local_path_if_any).

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
            return data_hash, local_path

        # No data_client provided: compute a content hash locally
        logger.info("No data_client provided; computing local parquet + hash")
        buf = io.BytesIO()
        pq.write_table(table, buf, **geoscience_object_data_options())
        raw = buf.getvalue()
        data_hash = hashlib.sha256(raw).hexdigest()

        local_path = None
        if self.output_parquet:
            self.output_path.mkdir(parents=True, exist_ok=True)
            local_path = self.output_path / f"{data_hash}.parquet"
            local_path.write_bytes(raw)
        return data_hash, local_path

    def _create_cell_attribute(self, cell_values: np.ndarray, width: int, height: int) -> ContinuousAttribute_V1_1_0:
        """Create cell attribute from pixel values."""
        logger.info("Creating cell attribute from pixel data")

        # Arrow table of values
        table = pa.table({"values": cell_values})

        # Persist parquet (via data_client or locally) and get the content hash
        data_hash, _ = self._create_parquet_file(table)

        # Attribute metadata
        attribute_description = AttributeDescription_V1_0_1(
            discipline="Imagery",
            type="Grayscale Intensity",
        )

        nan_description = NanContinuous_V1_0_1(values=[-1.0000000331813535e32, -1e32])

        values = FloatArray1_V1_0_1(
            data=data_hash,
            length=width * height,
            width=1,
            data_type="float64",
        )

        attribute = ContinuousAttribute_V1_1_0(
            name="2d-grid-data-continuous",
            key=data_hash,
            attribute_type="scalar",
            attribute_description=attribute_description,
            nan_description=nan_description,
            values=values,
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
        """Convert an image file to a Regular 2D Grid object."""

        # Read and preprocess image
        cell_values, width, height = self._read_image_as_grayscale(image_path)

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

        # Cell attributes (pixel data)
        cell_attribute = self._create_cell_attribute(cell_values, width, height)

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

        logger.info(f"Successfully converted image to Regular 2D Grid: {grid.name} ({width}x{height})")
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
        data_client = _LocalObjectDataClientStub(output_dir="./parquet_arrays")

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
