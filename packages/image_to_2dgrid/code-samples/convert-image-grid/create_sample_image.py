#!/usr/bin/env python
"""
Create a sample JPEG image for testing the JPEG to Grid converter.

This script generates a simple gradient image that can be used to test
the conversion process.
"""

import numpy as np
from PIL import Image
from pathlib import Path


def create_sample_gradient_image(output_path: str, width: int = 128, height: int = 106):
    """
    Create a sample gradient JPEG image.

    Args:
        output_path: Where to save the JPEG
        width: Image width in pixels
        height: Image height in pixels
    """
    print(f"Creating {width}x{height} sample gradient image...")

    # Create a 2D gradient (diagonal)
    img_array = np.zeros((height, width), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            # Create a diagonal gradient
            value = int((x + y) * 255 / (width + height - 2))
            img_array[y, x] = value

    # Convert to PIL Image and save
    img = Image.fromarray(img_array, mode="L")
    img.save(output_path, "JPEG", quality=95)

    print(f"Sample image saved to: {output_path}")
    print(f"Dimensions: {width} x {height} pixels")
    print(f"Total cells: {width * height}")


def create_sample_test_pattern(output_path: str, width: int = 128, height: int = 106):
    """
    Create a test pattern with distinct regions.

    Args:
        output_path: Where to save the JPEG
        width: Image width in pixels
        height: Image height in pixels
    """
    print(f"Creating {width}x{height} sample test pattern...")

    img_array = np.zeros((height, width), dtype=np.uint8)

    # Create quadrants with different values
    mid_x = width // 2
    mid_y = height // 2

    img_array[0:mid_y, 0:mid_x] = 50  # Top-left: dark
    img_array[0:mid_y, mid_x:] = 150  # Top-right: medium
    img_array[mid_y:, 0:mid_x] = 200  # Bottom-left: light
    img_array[mid_y:, mid_x:] = 100  # Bottom-right: medium-dark

    # Convert to PIL Image and save
    img = Image.fromarray(img_array, mode="L")
    img.save(output_path, "JPEG", quality=95)

    print(f"Test pattern saved to: {output_path}")
    print(f"Dimensions: {width} x {height} pixels")


if __name__ == "__main__":
    # Create output directory
    output_dir = Path("data/input")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create sample images
    create_sample_gradient_image(str(output_dir / "sample_gradient.jpg"), width=128, height=106)

    create_sample_test_pattern(str(output_dir / "sample_pattern.jpg"), width=128, height=106)

    print("\nSample images created successfully!")
    print("\nYou can now test the converter with:")
    print("  python example_jpeg_to_json.py data/input/sample_gradient.jpg output.json")
