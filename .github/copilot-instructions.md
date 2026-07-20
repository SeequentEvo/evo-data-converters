# Copilot Instructions for evo-data-converters

## What this repository is

This repository provides Python packages that convert geoscience data files into
**Evo geoscience objects** and publish them to the Seequent Evo platform. Each
package handles one source format (DUF, OMF, GoCad, VTK, SHP, XYZ, etc.).

The converted objects are instances of Python dataclasses generated from the
[evo-schemas](https://github.com/SeequentEvo/evo-schemas) JSON schemas and
published to an Evo workspace via the Evo object API.

## Repository layout

```
packages/
  common/   # shared utilities: auth, publish, CRS, array helpers
  duf/      # Deswik DUF format
  omf/      # Open Mining Format (OMF v2)
  gocad/    # GOCAD / SKUA format
  image/    # Raster image format
  obj/      # Wavefront OBJ (import & export)
  omf/      # OMF (import & export)
  resqml/   # RESQML format
  shp/      # ESRI Shapefile
  ubc/      # UBC Mesh format
  vtk/      # VTK format
  xyz/      # XYZ point cloud format
code-samples/  # end-to-end usage examples and Jupyter notebooks
```

Each package follows the namespace package path
`packages/<format>/src/evo/data_converters/<format>/`.

## Key concepts

- **Source format** — the input file being read (DUF, OMF, SHP, etc.)
- **Evo geoscience object** — a Python dataclass from `evo-schemas` (e.g.
  `TriangleMesh_V2_1_0`). All objects inherit from
  `BaseSpatialDataProperties_V1_0_1`.
- **`ObjectDataClient`** — stores large numeric arrays (vertices, indices,
  attributes) as Parquet files via `data_client.save_table(pa.Table)`. The
  returned dict is passed to the schema dataclass via `**kwargs` or
  `from_dict(...)`.
- **`publish_geoscience_objects` / `publish_geoscience_objects_sync`** — stages
  and publishes a list of geoscience objects to the Evo workspace.
- **`EvoWorkspaceMetadata`** — dataclass that holds `org_id`, `hub_url`,
  `workspace_id`, `client_id`, `client_secret`, and `cache_root`.

## Evo schema object types

Import objects from `evo_schemas.objects` and components from
`evo_schemas.components`. The versioned suffix (e.g. `_V2_1_0`) is part of the
class name — always use the latest version available.

| Geoscience concept | Object class | Key component(s) |
|---|---|---|
| Triangle mesh / surface | `TriangleMesh_V2_1_0` | `Triangles_V1_2_0`, `Triangles_V1_2_0_Vertices`, `Triangles_V1_2_0_Indices` |
| Point cloud | `Pointset_V1_2_0` | `Pointset_V1_2_0_Locations`, `FloatArray3_V1_0_1` |
| Line segments / polylines | `LineSegments_V2_1_0` | `Segments_V1_2_0`, `Segments_V1_2_0_Vertices`, `Segments_V1_2_0_Indices` |
| Regular block model | `RegularBlockModel_V1_4_0` | `RegularBlockModelGeometry_V1_1_0` |
| Sub-blocked model | `SubBlockedModel_V1_1_0` | — |
| Drillhole campaign | `DrillingCampaign_V2_1_0` | — |

All objects require: `name` (str), `uuid` (set to `None` for new objects),
`bounding_box` (`BoundingBox_V1_0_1`), `coordinate_reference_system`
(`Crs_V1_0_1`).

## Common utilities (evo-data-converters-common)

```python
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,  # returns (ObjectAPIClient, ObjectDataClient)
    publish_geoscience_objects,                 # async
    publish_geoscience_objects_sync,            # sync wrapper
    crs_from_epsg_code,   # int | str -> Crs_V1_0_1_EpsgCode
    crs_from_ogc_wkt,     # str -> Crs_V1_0_1_OgcWkt
    crs_from_any,         # int | str | None -> Crs_V1_0_1
    crs_unspecified,      # -> Crs_V1_0_1 with no CRS defined
    InvalidCRSError,
)
from evo.data_converters.common.utils import vertices_bounding_box  # NDArray -> BoundingBox_V1_0_1
```

## Path-specific instructions

Domain-specific guidance is provided via path-specific instruction files in
`.github/instructions/`. These are automatically loaded by Copilot when working
on files that match their `applyTo` patterns:

| Instruction file | Applies to | Content |
|---|---|---|
| `new-converter.instructions.md` | `packages/*/src/**/*.py` | Writing converter code, schema mapping, array patterns |
| `tests.instructions.md` | `packages/*/tests/**` | Test conventions, fixtures, mock clients |
| `code-samples.instructions.md` | `code-samples/**` | Notebook and script conventions |

## Skills

On-demand workflow guides are in `.github/skills/`. Load them with `read_file`
when the task matches:

| Skill file | When to use |
|---|---|
| `new-converter-scaffold.md` | Creating a brand-new converter package from scratch — covers directory layout, `pyproject.toml` template, namespace `__init__.py` files, entry-point stub, test fixtures, and workspace registration |
