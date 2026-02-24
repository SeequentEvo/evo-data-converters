# Image to Grid Conversion Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Image to Regular 2D Grid Converter                    │
└─────────────────────────────────────────────────────────────────────────┘

INPUT: Image File (JPEG, PNG, TIFF, BMP, GIF, etc.)
  │
  ├─ image.jpg (any size, color or grayscale)
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Read and Convert to Grayscale                                   │
│   - PIL Image.open(image_path)                                          │
│   - Convert to 'L' mode (grayscale/luminance)                           │
│   - Get dimensions: width, height                                       │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Extract Pixel Values (Row-Major Order)                          │
│   for y in range(height):                                               │
│       for x in range(width):                                            │
│           value = pixel_array[y, x]  # 0-255 grayscale                  │
│           cell_values.append(float(value))                              │
│                                                                          │
│   Result: Flattened 1D array [width × height] of float64 values         │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Create Parquet File                                             │
│   - Create PyArrow table: {"values": cell_values}                       │
│   - Serialize with options:                                             │
│     • version: "2.4"                                                    │
│     • compression: "gzip"                                               │
│   - Generate SHA-256 hash of serialized data                            │
│   - Save as: {hash}.parquet                                             │
│   - Upload to Evo data client                                           │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: Build Regular 2D Grid JSON Object                               │
│   {                                                                      │
│     "schema": "/objects/regular-2d-grid/1.3.0/...",                      │
│     "origin": [x0, y0, z0],           ← World coordinates               │
│     "size": [width, height],          ← Image dimensions                │
│     "cell_size": [dx, dy],            ← Cell size in world units        │
│     "rotation": {                     ← Orientation                     │
│       "dip": 0.0,                                                        │
│       "dip_azimuth": 0.0,                                               │
│       "pitch": 0.0                                                       │
│     },                                                                   │
│     "bounding_box": {                 ← Calculated from above           │
│       "min_x": x0,                                                       │
│       "max_x": x0 + width*dx,                                           │
│       "min_y": y0,                                                       │
│       "max_y": y0 + height*dy,                                          │
│       "min_z": z0,                                                       │
│       "max_z": z0                                                        │
│     },                                                                   │
│     "cell_attributes": [{             ← Pixel data reference            │
│       "attribute_type": "scalar",                                        │
│       "name": "2d-grid-data-continuous",                                │
│       "key": "{hash}",                ← SHA-256 hash                    │
│       "values": {                                                        │
│         "data": "{hash}",             ← Same hash                       │
│         "data_type": "float64",                                         │
│         "width": 1,                                                      │
│         "length": width × height                                        │
│       }                                                                  │
│     }],                                                                  │
│     "coordinate_reference_system": {...},  ← Optional CRS               │
│     "tags": {...}                     ← Optional metadata               │
│   }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 5: Publish to Evo                                                  │
│   - Upload parquet file to data service                                 │
│   - Create geoscience object in object service                          │
│   - Return ObjectMetadata with UUID                                     │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
OUTPUT: Published Geoscience Object
  ├─ JSON metadata in Evo object service
  ├─ Parquet data in Evo data service
  └─ UUID for referencing


═══════════════════════════════════════════════════════════════════════════
                              EXAMPLE DATA FLOW
═══════════════════════════════════════════════════════════════════════════

Input Image:
  File: satellite_view.jpg
  Dimensions: 128 × 106 pixels
  Format: Any PIL/Pillow supported format

After Conversion:
  Grid Size: [128, 106]
  Total Cells: 13,568
  Cell Values: Float64 array [0.0 - 255.0]
  Data File: abc123def456...789.parquet (hash-named)
  JSON Schema: regular-2d-grid v1.3.0

Example Parameters:
  Origin: [572565.0, 6839415.0, 1000.0]  (UTM coordinates)
  Cell Size: [30.0, 30.0]  (30m × 30m cells)
  Bounding Box:
    - X: 572565.0 to 576405.0  (128 × 30 = 3840m width)
    - Y: 6839415.0 to 6842595.0  (106 × 30 = 3180m height)
    - Z: 1000.0 (constant, 2D grid)


═══════════════════════════════════════════════════════════════════════════
                              FILE STRUCTURE
═══════════════════════════════════════════════════════════════════════════

mdos/
├── src/evo/data_converters/
│   └── image_to_2dgrid/             ← Image converter
│       ├── __init__.py              ← Package exports
│       └── image_to_grid.py         ← Main implementation (350+ lines)
│
├── code-samples/
│   └── convert-image-grid/          ← Image samples
│       ├── convert-image-grid.ipynb ← Jupyter notebook tutorial
│       ├── example_image_to_json.py ← Standalone converter script
│       ├── create_sample_image.py   ← Generate test images
│       ├── README.md                ← Full documentation
│       └── QUICKSTART.md            ← Quick reference
│
└── tests/importers/
    └── test_image_to_grid.py        ← Image tests (200+ lines)



═══════════════════════════════════════════════════════════════════════════
                           GETTING STARTED
═══════════════════════════════════════════════════════════════════════════

1. Install dependencies:
   pip install pillow pyarrow evo-schemas

2. Try standalone example (no Evo needed):
  cd code-samples/convert-image-grid
   python create_sample_image.py
   python example_image_to_json.py data/input/sample_gradient.jpg test.json

3. Use in Jupyter notebook:
  - Open convert-image-grid.ipynb
   - Add your client_id
   - Follow the examples

4. Run tests:
   pytest tests/importers/test_image_to_grid.py -v

5. Read documentation:
   - README.md: Complete API reference
   - QUICKSTART.md: Quick reference guide
