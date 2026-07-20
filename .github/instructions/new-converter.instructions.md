---
applyTo: "packages/*/src/**/*.py"
---
# Writing a data converter

This guide covers the conventions, patterns, and API used across all converters
in this repository. Read it before implementing or modifying any converter code.

## Converter module layout

Each converter package follows this structure:

```
packages/<format>/src/evo/data_converters/<format>/
  importer/
    <format>_to_evo.py        ← top-level entry point (public API)
    <format>_<type>_to_evo.py ← one file per geoscience object type
    utils.py                  ← shared array/geometry helpers
    __init__.py               ← re-exports public conversion functions
  common/
    <format>_types.py         ← typed dataclasses for the source format
  __init__.py
```

See `packages/omf/src/evo/data_converters/omf/importer/` for a complete
reference implementation covering surface, pointset, lineset, and block model
conversions.

---

## Top-level entry point pattern

The main `<format>_to_evo.py` module is the public entry point. Follow this
signature pattern (see `omf_to_evo.py` and `duf_to_evo.py` for examples):

```python
from typing import Optional
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects_sync,
    crs_from_any,
)

def convert_<format>(
    filepath: str,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    coordinate_reference_system: str | int | None = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[BaseSpatialDataProperties_V1_0_1]:
    object_service_client, data_client = create_evo_object_service_and_data_client(evo_workspace_metadata)
    crs = crs_from_any(coordinate_reference_system)

    objects = _read_and_convert(filepath, data_client, crs)

    if publish_objects:
        return publish_geoscience_objects_sync(
            objects, object_service_client, data_client,
            path_prefix=upload_path,
            overwrite_existing_objects=overwrite_existing_objects,
        )
    return objects
```

- Always accept both `evo_workspace_metadata` and an optional
  `service_manager_widget` for notebook compatibility.
- Use `publish_geoscience_objects_sync` for sync converters and
  `publish_geoscience_objects` (async) for async ones.
- Never hardcode credentials — they always come from `EvoWorkspaceMetadata`.

---

## Writing array data with ObjectDataClient

Large numeric arrays (vertices, indices, attributes) **must not** be stored
inline in schema dataclasses. They are written to Parquet storage via
`ObjectDataClient.save_table()`, which returns a dict of kwargs consumed by the
schema component.

### Pattern for vertices (x, y, z as float64)

```python
import pyarrow as pa
from evo.objects.utils.data import ObjectDataClient

vertices_schema = pa.schema([
    pa.field("x", pa.float64()),
    pa.field("y", pa.float64()),
    pa.field("z", pa.float64()),
])
vertices_table = pa.Table.from_arrays(
    [pa.array(vertices_array[:, i], type=pa.float64()) for i in range(3)],
    schema=vertices_schema,
)
vertices_go = SomeVerticesClass(**data_client.save_table(vertices_table))
```

### Pattern for triangle indices (n0, n1, n2 as uint64)

```python
indices_schema = pa.schema([
    pa.field("n0", pa.uint64()),
    pa.field("n1", pa.uint64()),
    pa.field("n2", pa.uint64()),
])
indices_table = pa.Table.from_arrays(
    [pa.array(indices_array[:, i], type=pa.uint64()) for i in range(3)],
    schema=indices_schema,
)
indices_go = SomeIndicesClass(**data_client.save_table(indices_table))
```

### Pattern for line segment indices (n0, n1 as uint64)

```python
segment_indices_schema = pa.schema([
    pa.field("n0", pa.uint64()),
    pa.field("n1", pa.uint64()),
])
```

---

## Mapping source geometry to evo-schema object types

### Triangle mesh / surface → `TriangleMesh_V2_1_0`

Use when the source has vertices + triangular face indices (e.g. a mesh or surface).

```python
from evo_schemas.objects import TriangleMesh_V2_1_0
from evo_schemas.components import (
    Triangles_V1_2_0,
    Triangles_V1_2_0_Vertices,
    Triangles_V1_2_0_Indices,
    Crs_V1_0_1,
)
from evo.data_converters.common.utils import vertices_bounding_box

bounding_box = vertices_bounding_box(vertices_array)

vertices_go = Triangles_V1_2_0_Vertices(**data_client.save_table(vertices_table))
indices_go = Triangles_V1_2_0_Indices(**data_client.save_table(indices_table))

obj = TriangleMesh_V2_1_0(
    name=name,
    uuid=None,
    bounding_box=bounding_box,
    coordinate_reference_system=crs,
    triangles=Triangles_V1_2_0(vertices=vertices_go, indices=indices_go),
)
```

See `packages/omf/src/evo/data_converters/omf/importer/omf_surface_to_evo.py`
for the full reference.

### Point cloud → `Pointset_V1_2_0`

Use when the source has X, Y, Z point locations (e.g. drillhole collars, point
data, XYZ files).

```python
from evo_schemas.objects import Pointset_V1_2_0
from evo_schemas.components import Pointset_V1_2_0_Locations
from evo_schemas.elements import FloatArray3_V1_0_1

coordinates_go = FloatArray3_V1_0_1.from_dict(data_client.save_table(coordinates_table))

obj = Pointset_V1_2_0(
    name=name,
    uuid=None,
    bounding_box=bounding_box,
    coordinate_reference_system=crs,
    locations=Pointset_V1_2_0_Locations(coordinates=coordinates_go),
)
```

See `packages/omf/src/evo/data_converters/omf/importer/omf_pointset_to_evo.py`
for the full reference.

### Line segments / polylines → `LineSegments_V2_1_0`

Use when the source has vertices + segment index pairs (start/end vertex index
per segment).

```python
from evo_schemas.objects import LineSegments_V2_1_0
from evo_schemas.components import (
    Segments_V1_2_0,
    Segments_V1_2_0_Vertices,
    Segments_V1_2_0_Indices,
    Crs_V1_0_1,
)

vertices_go = Segments_V1_2_0_Vertices(**data_client.save_table(vertices_table))
indices_go = Segments_V1_2_0_Indices(**data_client.save_table(segment_indices_table))

obj = LineSegments_V2_1_0(
    name=name,
    uuid=None,
    bounding_box=bounding_box,
    coordinate_reference_system=crs,
    segments=Segments_V1_2_0(vertices=vertices_go, indices=indices_go),
)
```

See `packages/omf/src/evo/data_converters/omf/importer/omf_lineset_to_evo.py`
for the full reference.

---

## Attributes (scalar data on vertices or primitives)

Attributes attach scalar data (floats, integers, strings, categories,
booleans, datetimes) to vertices or primitives (faces/segments). Pass an
`attributes` list to the relevant vertices or indices component.

Attribute component classes come from `evo_schemas.components`:
- `ContinuousAttribute_V1_1_0` — float data
- `IntegerAttribute_V1_1_0` — integer data
- `CategoryAttribute_V1_1_0` — enum/category data with a lookup table
- `StringAttribute_V1_1_0` — string data
- `BoolAttribute_V1_1_0` — boolean data
- `DateTimeAttribute_V1_1_0` — datetime data

See `packages/duf/src/evo/data_converters/duf/importer/utils.py` and
`packages/omf/src/evo/data_converters/omf/importer/omf_attributes_to_evo.py`
for attribute conversion patterns.

---

## CRS handling

Always resolve CRS before constructing any geoscience object. Never pass `None`
directly as `coordinate_reference_system`.

```python
from evo.data_converters.common import (
    crs_from_epsg_code,   # int | str EPSG code  -> Crs_V1_0_1_EpsgCode
    crs_from_ogc_wkt,     # OGC WKT string       -> Crs_V1_0_1_OgcWkt
    crs_from_any,         # int | str | None      -> Crs_V1_0_1 (recommended)
    crs_unspecified,      # no CRS known          -> Crs_V1_0_1
    InvalidCRSError,      # raised on bad input
)

# Prefer crs_from_any for user-supplied inputs — handles EPSG ints,
# "EPSG:NNNN" strings, OGC WKT strings, and None (unspecified).
crs = crs_from_any(user_supplied_crs)
```

---

## Bounding box

Always compute the bounding box from the vertices array before constructing the
object:

```python
from evo.data_converters.common.utils import vertices_bounding_box
# vertices_array: NDArray of shape (N, 3) with float64 x, y, z columns
bounding_box = vertices_bounding_box(vertices_array)
```

---

## Logging

Use the `evo.logging` module, not Python's built-in `logging`:

```python
import evo.logging
logger = evo.logging.getLogger("data_converters")

logger.debug(f'Converting "{source_name}" to TriangleMesh_V2_1_0.')
logger.warning(f"Unsupported type {obj_type}, skipping.")
```

Always log a `debug` message when creating a geoscience object and a `warning`
when skipping an object.

---

## Package configuration

Each converter package uses a `pyproject.toml` with the namespace package
`evo.data_converters.<format>`. Add `evo-data-converters-common` as a
dependency and depend on `evo-schemas` for the schema dataclasses. See any
existing `packages/<format>/pyproject.toml` for the template.

---

## Choosing the right evo-schema object

| If your source data has... | Use this Evo object |
|---|---|
| Vertices + triangular face indices | `TriangleMesh_V2_1_0` |
| X, Y, Z point locations only | `Pointset_V1_2_0` |
| Vertices + start/end segment pairs | `LineSegments_V2_1_0` |
| A regular 3-D grid of blocks with uniform spacing | `RegularBlockModel_V1_4_0` |
| A grid where blocks can be sub-divided | `SubBlockedModel_V1_1_0` |
| Drillhole collars + intervals | `DrillingCampaign_V2_1_0` |

When in doubt, check the [evo-schemas objects directory](https://github.com/SeequentEvo/evo-schemas/tree/main/schema/objects)
and the [Seequent Developer Portal](https://developer.seequent.com/docs/data-structures/geoscience-objects/).
