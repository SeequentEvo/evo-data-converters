#!/usr/bin/env python
# --------------------------------------------------------------------------------------------
#  Copyright (c) 2026 Bentley Systems, Incorporated. All rights reserved.
# --------------------------------------------------------------------------------------------

"""
Simple example: Convert Image to Regular 2D Grid JSON (without publishing to Evo)

This script demonstrates how to convert an image file (JPEG, PNG, TIFF, etc.) to the
regular-2d-grid schema format and save it as a JSON file locally, without requiring
Evo authentication.

Usage:
    python example_image_to_json.py input.jpg output.json

Supported formats: JPEG, PNG, TIFF, BMP, GIF, and other PIL/Pillow supported formats.

This will create:
    - output.json: The grid schema JSON
    - output_data/: Directory containing parquet data files
"""

import sys
import json
import hashlib
import io
from pathlib import Path
from PIL import Image
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def geoscience_object_data_options():
    """Parquet writing options for geoscience objects"""
    return {
        "version": "2.4",
        "flavor": None,
        "data_page_size": None,
        "compression": "gzip",
        "encryption_properties": None,
    }


def convert_image_to_grid_json(
    image_path: str,
    output_json: str,
    output_data_dir: str = None,
    origin: list = None,
    cell_size: list = None,
    name: str = None,
    description: str = None,
):
    """
    Convert image to Regular 2D Grid JSON without Evo publishing.

    Supports JPEG, PNG, TIFF, BMP, GIF, and other PIL/Pillow formats.

    Args:
        image_path: Path to input image file
        output_json: Path to output JSON file
        output_data_dir: Directory for parquet files (default: same as JSON with _data suffix)
        origin: Grid origin [x, y, z]
        cell_size: Cell size [x, y]
        name: Grid name
        description: Grid description
    """

    # Set defaults
    if origin is None:
        origin = [0.0, 0.0, 0.0]
    if cell_size is None:
        cell_size = [1.0, 1.0]
    if output_data_dir is None:
        output_data_dir = str(Path(output_json).parent / f"{Path(output_json).stem}_data")

    # Create output directory
    Path(output_data_dir).mkdir(parents=True, exist_ok=True)

    print(f"Reading image: {image_path}")

    # Read and convert image to grayscale
    img = Image.open(image_path)
    grayscale_img = img.convert("L")
    width, height = grayscale_img.size

    print(f"Image size: {width} x {height} pixels")

    # Extract pixel values (row-major order)
    pixel_array = np.array(grayscale_img, dtype=np.float64)
    cell_values = []
    for y in range(height):
        for x in range(width):
            value = pixel_array[y, x]
            cell_values.append(value)

    cell_values = np.array(cell_values, dtype=np.float64)
    print(f"Extracted {len(cell_values)} cell values")

    # Create parquet file
    print("Creating parquet file...")
    table = pa.table({"values": cell_values})

    # Generate hash
    buffer = io.BytesIO()
    pq.write_table(table, buffer, **geoscience_object_data_options())
    table_bytes = buffer.getvalue()
    data_hash = hashlib.sha256(table_bytes).hexdigest()

    # Write parquet file
    parquet_path = Path(output_data_dir) / f"{data_hash}.parquet"
    buffer.seek(0)
    with open(parquet_path, "wb") as f:
        f.write(buffer.read())

    print(f"Parquet file: {parquet_path}")
    print(f"Data hash: {data_hash}")

    # Build grid JSON
    grid_name = name or Path(image_path).stem
    grid_description = description or "A 2D grid from image"

    grid_json = {
        "schema": "/objects/regular-2d-grid/1.3.0/regular-2d-grid.schema.json",
        "name": grid_name,
        "description": grid_description,
        "origin": origin,
        "size": [width, height],
        "cell_size": cell_size,
        "rotation": {"dip": 0.0, "dip_azimuth": 0.0, "pitch": 0.0},
        "bounding_box": {
            "min_x": origin[0],
            "min_y": origin[1],
            "min_z": origin[2],
            "max_x": origin[0] + (width * cell_size[0]),
            "max_y": origin[1] + (height * cell_size[1]),
            "max_z": origin[2],
        },
        "cell_attributes": [
            {
                "attribute_type": "scalar",
                "name": "2d-grid-data-continuous",
                "key": data_hash,
                "nan_description": {"values": [-1.0000000331813535e32, -1e32]},
                "values": {"data": data_hash, "data_type": "float64", "width": 1, "length": width * height},
            }
        ],
    }

    # Write JSON
    print(f"Writing JSON: {output_json}")
    with open(output_json, "w") as f:
        json.dump(grid_json, f, indent=2)

    print("\nConversion complete!")
    print(f"  Grid: {grid_name}")
    print(f"  Size: {width} x {height}")
    print(f"  Cells: {width * height}")
    print(f"  Origin: {origin}")
    print(f"  Cell size: {cell_size}")
    print("\nOutput files:")
    print(f"  JSON: {output_json}")
    print(f"  Parquet: {parquet_path}")


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Usage: python example_image_to_json.py <input_image> <output.json>")
        print("\nSupported formats: JPEG, PNG, TIFF, BMP, GIF, etc.")
        print("\nExamples:")
        print("  python example_image_to_json.py satellite_image.jpg grid.json")
        print("  python example_image_to_json.py heightmap.png grid.json")
        print("  python example_image_to_json.py scan.tiff grid.json")
        sys.exit(1)

    image_path = sys.argv[1]
    output_json = sys.argv[2]

    # Check input file exists
    if not Path(image_path).exists():
        print(f"Error: Input file not found: {image_path}")
        sys.exit(1)

    # Convert with default parameters
    # You can modify these values as needed
    convert_image_to_grid_json(
        image_path=image_path,
        output_json=output_json,
        origin=[0.0, 0.0, 0.0],
        cell_size=[1.0, 1.0],
        name=Path(image_path).stem,
        description="Converted from image",
    )


if __name__ == "__main__":
    main()
