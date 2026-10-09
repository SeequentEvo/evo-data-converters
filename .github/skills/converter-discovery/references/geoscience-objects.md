# Evo geoscience object cheatsheet

Use this to map input data to an `evo_schemas` object type during discovery. Class names carry
a version suffix (e.g. `Pointset_V1_3_0`); always confirm the exact version available in the
installed package:

```shell
uv run python -c "import evo_schemas.objects as o; print([n for n in dir(o) if not n.startswith('_')])"
```

All objects are subclasses of `BaseSpatialDataProperties_V1_0_1` and share:

- `name`, `uuid=None`, `description`
- `bounding_box` — `BoundingBox_V1_0_1(min_x, max_x, min_y, max_y, min_z, max_z)`
- `coordinate_reference_system` — a `Crs_V1_0_1_*` value or `"unspecified"`
- `tags` — dict of string metadata

## Choosing an object type

| Input data looks like… | Likely Evo object | Notes |
|---|---|---|
| Scattered 3D points (± values) | `Pointset` | Coordinates as `FloatArray3`; values as attributes. See `packages/xyz`. |
| Polylines / segments | `LineSegments` | Vertices + segment index pairs. See `packages/omf`. |
| Triangulated surface / mesh | `TriangleMesh` | Vertices (`FloatArray3`) + triangle indices (`IndexArray3`). See `packages/omf`, `packages/obj`. |
| Regular/rectilinear 3D grid | `RegularGrid3D` / tensor grid | Origin, cell sizes, counts, rotation. See `packages/common/grid_data.py`, `packages/resqml`. |
| Block model (mining) | Block model via `evo-blockmodels` / BlockSync | Uses `BlockSyncClient`, not the object API directly. See `packages/omf` block model, `packages/ubc`. |
| Raster / image over an extent | image/2D grid object | See `packages/image`. |

When unsure, look at the closest existing converter under `packages/` and mirror its object
construction.

## Attributes (per-element values)

- **Continuous** (floats): `ContinuousAttribute_V1_1_0(name, key, nan_description=NanContinuous_V1_0_1(values=[...]), values=FloatArray1_V1_0_1(data=<hash>, length=N))`
- **Categorical** (labels): `CategoryAttribute_*` with a lookup table.
- Attribute length must match the number of elements (points, cells, etc.).

## Referenced data (arrays)

Large arrays are not inlined — they are uploaded and referenced by hash/name:

- Modern: `data_client.save_table(pyarrow_table)` returns a reference to embed.
- Parquet-hash pattern (see `packages/xyz`): write the array to
  `os.path.join(data_client.cache_location, sha256_hash)` and reference `data=<hash>`.

## Where things live in `evo_schemas`

- `evo_schemas.objects.*` — top-level objects (`Pointset_V1_3_0`, …)
- `evo_schemas.elements.*` — arrays (`FloatArray3_V1_0_1`, `FloatArray1_V1_0_1`, index arrays)
- `evo_schemas.components.*` — `BoundingBox_V1_0_1`, `Crs_V1_0_1_*`, attributes, `NanContinuous_V1_0_1`

Reference: <https://github.com/SeequentEvo/evo-schemas> ·
<https://developer.seequent.com/docs/data-structures/geoscience-objects/>
