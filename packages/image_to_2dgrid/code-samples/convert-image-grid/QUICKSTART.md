# Image to Regular 2D Grid - Quick Start

## What Was Created

A complete Python implementation to convert images (JPEG, PNG, TIFF, etc.) to Regular 2D Grid geoscience objects.

## Files Created

### Core Implementation
- `src/evo/data_converters/image_to_2dgrid/__init__.py` - Package exports
- `src/evo/data_converters/image_to_2dgrid/image_to_grid.py` - Main converter implementation

### Examples & Documentation
- `code-samples/convert-image-grid/convert-image-grid.ipynb` - Jupyter notebook example
- `code-samples/convert-image-grid/example_image_to_json.py` - Standalone script (no Evo required)
- `code-samples/convert-image-grid/create_sample_image.py` - Generate test images
- `code-samples/convert-image-grid/README.md` - Complete documentation

### Tests
- `tests/importers/test_image_to_grid.py` - Unit tests

### Configuration
- Updated `pyproject.toml` - Added Pillow dependency

## Quick Usage

### Option 1: Use in Jupyter Notebook (with Evo)

```python
from evo.data_converters.image_to_2dgrid import convert_image_to_grid
from evo.notebooks import ServiceManagerWidget

# Authenticate
manager = await ServiceManagerWidget.with_auth_code(
    client_id="your-client-id"
).login()

# Convert and publish
results = convert_image_to_grid(
    image_path="image.jpg",
    origin=[572565.0, 6839415.0, 1000.0],
    cell_size=[30.0, 30.0],
    service_manager_widget=manager,
    upload_path="grids/image_imports"
)
```

### Option 2: Standalone Script (no Evo)

```bash
cd code-samples/convert-image-grid

# Create sample image
python create_sample_image.py

# Convert to JSON
python example_image_to_json.py data/input/sample_gradient.jpg output.json
```

This creates:
- `output.json` - The grid schema
- `output_data/*.parquet` - The pixel data

## How It Works

1. **Read Image**: Opens image and converts to grayscale
2. **Extract Pixels**: Flattens pixel values in row-major order
3. **Create Parquet**: Stores data with SHA-256 hash reference
4. **Build Schema**: Creates Regular 2D Grid JSON object
5. **Upload to Evo**: Publishes both JSON and parquet data

## Key Features

✅ Image-to-grid conversion for Evo Regular 2D Grid objects  
✅ Proper parquet generation with hash references  
✅ Schema compliance (regular-2d-grid v1.3.0)  
✅ Works with Evo publishing workflow  
✅ Includes unit tests  

## Schema Output

The converter creates JSON matching your example:

```json
{
  "schema": "/objects/regular-2d-grid/1.3.0/regular-2d-grid.schema.json",
  "name": "my_image",
  "origin": [572565.0, 6839415.0, 1000.0],
  "size": [128, 106],
  "cell_size": [30.0, 30.0],
  "rotation": {"dip": 0.0, "dip_azimuth": 0.0, "pitch": 0.0},
  "bounding_box": {
    "min_x": 572565.0,
    "max_x": 576405.0,
    "min_y": 6839415.0,
    "max_y": 6842595.0,
    "min_z": 1000.0,
    "max_z": 1000.0
  },
  "cell_attributes": [{
    "attribute_type": "scalar",
    "name": "2d-grid-data-continuous",
    "key": "abc123...",
    "values": {
      "data": "abc123...",
      "data_type": "float64",
      "width": 1,
      "length": 13568
    }
  }]
}
```

## Installation

```bash
# Install dependencies
pip install pillow pyarrow evo-schemas

# Or install the package
pip install -e .
```

## Testing

```bash
# Run tests
pytest tests/importers/test_image_to_grid.py -v
```

## Next Steps

1. **Try the standalone example**:
   ```bash
  cd code-samples/convert-image-grid
   python create_sample_image.py
   python example_image_to_json.py data/input/sample_gradient.jpg test_output.json
   ```

2. **Use in notebook**: Open `convert-image-grid.ipynb` and follow the examples

3. **Customize**: Modify origin, cell_size, and CRS to match your coordinate system

## Configuration Details

- **Origin**: Set to `[0, 0, 0]` by default or custom values
- **Size**: Automatically derived from image dimensions
- **CRS**: Optional, can use EPSG or WKT
- **Bounding Box**: Automatically calculated from origin + (size × cell_size)
- **Rotation**: Defaults to zero (no rotation)

## Support

For issues or questions:
1. Check the README.md for detailed documentation
2. Run the unit tests to verify installation
3. Try the standalone example first before Evo publishing

---

**Created**: February 2026  
**Compatible with**: regular-2d-grid schema v1.3.0
