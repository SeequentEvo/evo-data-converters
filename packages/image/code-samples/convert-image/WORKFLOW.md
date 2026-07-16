# Image to Grid Conversion Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Image to Regular 2D Grid Converter                  │
└─────────────────────────────────────────────────────────────────────────┘

INPUT: Image File (JPEG, PNG, TIFF, BMP, GIF, etc.)
  │
  ├─ image.jpg (any size, color or grayscale)
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Read Image and Detect Mode                                     │
│   - PIL Image.open(image_path)                                         │
│   - Detect image mode: grayscale (L/LA) or color (RGB-like modes)      │
│   - Get dimensions: width, height                                      │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Extract Pixel Values (Bottom-Row-First, Row-Major)            │
│                                                                         │
│   Grayscale path:                                                       │
│     pixel_array = np.array(grayscale_img, dtype=np.float64)            │
│     cell_values = np.flipud(pixel_array).ravel(order="C")             │
│                                                                         │
│   Color path:                                                           │
│     pixel_array = np.array(color_img, dtype=np.uint8)                  │
│     cell_values = np.flipud(pixel_array).reshape(-1, 3)                │
│                                                                         │
│   Result aligns index 0 with grid origin (bottom-left convention).     │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Create Parquet Payload                                         │
│   - Grayscale: column "data" with float64 values                       │
│   - Color: pack RGB as 0xAABBGGRR (A=0xFF), store as int32 values      │
│   - Serialize with options: version="2.4", compression="gzip"         │
│   - Generate SHA-256 hash and persist parquet data                      │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: Build Regular 2D Grid JSON Object                              │
│   {                                                                     │
│     "schema": "/objects/regular-2d-grid/1.3.0/...",                    │
│     "origin": [x0, y0, z0],            ← World coordinates            │
│     "size": [width, height],           ← Image dimensions             │
│     "cell_size": [dx, dy],             ← Cell size in world units     │
│     "rotation": {"dip":0,"dip_azimuth":0,"pitch":0},               │
│     "bounding_box": {...},             ← Calculated from size/cell     │
│     "cell_attributes": [                                               │
│       grayscale: {attribute_type:"scalar", name:"2d-grid-data-..."},   │
│       color:     {attribute_type:"color",  name:"2d-grid-data-color"}   │
│     ],                                                                   │
│     "coordinate_reference_system": {...},  ← EPSG provided or "unspecified" if not provided │
│     "tags": {...}                      ← Optional metadata             │
│   }                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 5: Publish to Evo (Optional)                                      │
│   - Upload parquet file to data service                                │
│   - Create geoscience object in object service                         │
│   - Return ObjectMetadata with UUID                                    │
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
  Cell Attributes: 1 (scalar for grayscale, color for RGB)
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

packages/image/
├── src/evo/data_converters/
│   └── image/
│       ├── __init__.py              ← Package exports
│       └── image_to_grid.py         ← Main implementation
│
├── code-samples/
│   └── convert-image/
│       ├── convert-image.ipynb      ← Jupyter notebook tutorial
│       ├── example_image_to_json.py ← Standalone converter script
│       ├── create_sample_image.py   ← Generate test images
│       ├── README.md                ← Full documentation
│       └── QUICKSTART.md            ← Quick reference
│
└── tests/importers/
    └── test_image_to_grid.py        ← Image tests (grayscale + color)


═══════════════════════════════════════════════════════════════════════════
                           GETTING STARTED
═══════════════════════════════════════════════════════════════════════════

1. Install dependencies:
   pip install pillow pyarrow evo-schemas

2. Try standalone example (no Evo needed):
   cd code-samples/convert-image
   python create_sample_image.py
   python example_image_to_json.py data/input/sample_gradient.jpg test.json

3. Use in Jupyter notebook:
   - Open convert-image.ipynb
   - Add your client_id
   - Follow the examples

4. Run tests:
   pytest tests/importers/test_image_to_grid.py -v

5. Read documentation:
   - README.md: Complete API reference
   - QUICKSTART.md: Quick reference guide
```
