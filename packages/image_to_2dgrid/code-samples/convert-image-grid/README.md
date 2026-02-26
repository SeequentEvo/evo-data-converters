# Image to Regular 2D Grid Converter

This module converts images (JPEG, PNG, TIFF, BMP, GIF, etc.) to Regular 2D Grid geoscience objects that can be published to Evo.

## Overview

The converter:
1. Reads an image file and converts it to grayscale
2. Extracts pixel values as a flattened array
3. Stores the data in a parquet file following geoscience object schema specifications
4. Creates a Regular 2D Grid JSON object with proper schema references
5. Publishes the grid and associated data to Evo workspace

## Schema

The converter implements the Regular 2D Grid schema version 1.3.0:
- **Schema**: `/objects/regular-2d-grid/1.3.0/regular-2d-grid.schema.json`
- **Cell Attributes**: Scalar attribute type for continuous data
- **Data Storage**: Parquet files with SHA-256 hash references

## Key Features

- Converts images to grayscale for grid data
- Supports JPEG, PNG, TIFF, BMP, GIF, and other PIL/Pillow formats
- Row-major iteration for pixel extraction
- Configurable origin, cell size, and coordinate reference system
- Automatic parquet file generation with hash-based naming
- Compatible with Evo publishing workflow
- Optional local parquet output for debugging

## Installation

Ensure you have the required dependencies:

```bash
pip install pillow pyarrow evo-schemas
```

## Usage

## Samples vs Tests

The scripts in this folder are examples, not automated tests:
- `create_sample_image.py` generates sample input images for demos.
- `example_image_to_json.py` shows a standalone conversion flow.

Automated tests belong under `packages/image_to_2dgrid/tests/`.

### Basic Example (Jupyter Notebook)

```python
from evo.data_converters.image_to_2dgrid import convert_image_to_grid
from evo.notebooks import ServiceManagerWidget

# Authenticate
manager = await ServiceManagerWidget.with_auth_code(
    client_id="your-client-id"
).login()

# Convert and publish
results = convert_image_to_grid(
    image_path="path/to/image.jpg",
    service_manager_widget=manager,
    upload_path="grids/image_imports",
    tags={"Source": "Jupyter Notebook"}
)

print(f"Published: {results[0].name}")
```

### Advanced Example with Custom Parameters

```python
results = convert_image_to_grid(
    image_path="image.jpg",
    origin=[572565.0, 6839415.0, 1000.0],  # World coordinates
    cell_size=[30.0, 30.0],  # 30m x 30m cells
    coordinate_reference_system={
        "epsg_code": 32618  # UTM Zone 18N
    },
    tags={"Source": "Jupyter", "type": "image-grid"},
    name="My Custom Grid",
    description="Grid from satellite imagery",
    service_manager_widget=manager,
    upload_path="grids",
    publish_objects=True,
    overwrite_existing_objects=False
)
```

### Programmatic Use (Without Publishing)

```python
from evo.data_converters.image_to_2dgrid.image_to_grid import ImageGridConverter
from evo.objects.utils.data import ObjectDataClient

# Create converter
data_client = ObjectDataClient(...)
converter = ImageGridConverter(data_client, output_parquet=True)

# Convert to grid object
grid = converter.convert(
    image_path="image.jpg",
    origin=[0, 0, 0],
    cell_size=[1, 1]
)

# Access grid properties
print(f"Size: {grid.size}")  # [width, height]
print(f"Cell count: {grid.size[0] * grid.size[1]}")
print(f"Cell attributes: {len(grid.cell_attributes)}")
```

## Parameters

### `convert_image_to_grid()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_path` | str | Required | Path to the image file (JPEG, PNG, TIFF, etc.) |
| `origin` | list[float] | `[0, 0, 0]` | Grid origin coordinates [x, y, z] |
| `cell_size` | list[float] | `[1, 1]` | Cell dimensions [x, y] |
| `coordinate_reference_system` | dict | None | CRS definition (EPSG or WKT) |
| `tags` | dict[str, str] | None | Tags to add to the object |
| `name` | str | filename | Name for the grid object |
| `description` | str | Auto | Description of the grid |
| `evo_workspace_metadata` | EvoWorkspaceMetadata | None | Evo workspace metadata |
| `service_manager_widget` | ServiceManagerWidget | None | Service manager (for notebooks) |
| `upload_path` | str | `""` | Path in Evo workspace |
| `publish_objects` | bool | `True` | Whether to publish to Evo |
| `overwrite_existing_objects` | bool | `False` | Overwrite existing objects |

## Data Format

### Cell Attributes

The converter creates a scalar attribute named `"2d-grid-data-continuous"` with:
- **Data type**: `float64`
- **Width**: 1 (single value per cell)
- **Length**: width × height
- **Data**: SHA-256 hash reference to parquet file
- **NaN values**: `[-1.0000000331813535e+32, -1e+32]`

### Parquet File Structure

The parquet file contains a single column named `"values"` with:
- Flattened pixel values (row-major order)
- Type: double (float64)
- Compression: gzip
- Version: 2.4 (Apache Parquet)

## Grid Orientation

The converter follows this pattern for pixel extraction:

```python
for y in range(height):
    for x in range(width):
        value = pixel_array[y, x]
        cell_values.append(value)
```

This creates a row-major flattened array where:
- First `width` values = top row of image
- Next `width` values = second row
- And so on...

## Coordinate Reference System

You can specify CRS in two ways:

### EPSG Code
```python
crs = {"epsg_code": 32618}  # UTM Zone 18N
```

### WKT String
```python
crs = {
    "ogc_wkt": 'PROJCS["NAD27 / UTM zone 18N",...]'
}
```

## Example Output

A successfully converted grid will have this structure:

```json
{
  "schema": "/objects/regular-2d-grid/1.3.0/regular-2d-grid.schema.json",
  "name": "my_image",
  "description": "A 2D grid from image",
  "origin": [0.0, 0.0, 0.0],
  "size": [800, 600],
  "cell_size": [1.0, 1.0],
  "rotation": {
    "dip": 0.0,
    "dip_azimuth": 0.0,
    "pitch": 0.0
  },
  "bounding_box": {
    "min_x": 0.0,
    "min_y": 0.0,
    "min_z": 0.0,
    "max_x": 800.0,
    "max_y": 600.0,
    "max_z": 0.0
  },
  "cell_attributes": [
    {
      "attribute_type": "scalar",
      "name": "2d-grid-data-continuous",
      "key": "abc123...",
      "values": {
        "data": "abc123...",
        "data_type": "float64",
        "length": 480000,
        "width": 1
      }
    }
  ]
}
```

## Troubleshooting

### Notebook output and local artifacts

Authentication and workspace-selection cells can produce local traceback output in notebook cells.
This output is runtime-only and should not be committed.

Before committing, clear notebook outputs in `convert-image-grid.ipynb` and keep generated files local
(`notebook-data/`, `parquet_arrays/`, `output_data/`, and temporary output JSON files).

### Common Issues

1. **ImportError: No module named 'PIL'**
   ```bash
   pip install pillow
   ```

2. **Authentication errors**
   - Ensure your `client_id` is correct
   - Check that you have proper Evo workspace access

3. **Large image memory issues**
   - Consider downsampling very large images before conversion
   - The entire pixel array is loaded into memory

### Debug Mode

Enable parquet file output for debugging:

```python
from evo.data_converters.image_to_2dgrid.image_to_grid import ImageGridConverter

converter = ImageGridConverter(
    data_client, 
    output_dir="./debug_parquet",
    output_parquet=True  # Write files to disk
)
```

## See Also

- [Regular 2D Grid Schema](https://github.com/seequent/geoscience-object-schemas)
- [Evo Documentation](https://evo.seequent.com)
