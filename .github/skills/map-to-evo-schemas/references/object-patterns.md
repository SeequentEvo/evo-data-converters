# Object construction patterns

Copy-adaptable snippets for implementing `get_geoscience_object_from_<type>`. Full working
examples live in [`packages/xyz`](../../../../packages/xyz) (point set) and
[`packages/omf`](../../../../packages/omf) (meshes, lines, block model, plus export).

## Point set (adapted from `packages/xyz/importer/xyz_parser.py`)

```python
import os
import hashlib
import numpy as np
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.objects.pointset import Pointset_V1_3_0, Pointset_V1_3_0_Locations
from evo_schemas.elements import FloatArray3_V1_0_1
from evo_schemas.elements.float_array_1 import FloatArray1_V1_0_1
from evo_schemas.components import BoundingBox_V1_0_1, Crs_V1_0_1
from evo_schemas.components.continuous_attribute import ContinuousAttribute_V1_1_0
from evo_schemas.components.nan_continuous import NanContinuous_V1_0_1


def build_pointset(
    data_client: ObjectDataClient,
    name: str,
    points: np.ndarray,        # shape (N, 3)
    values: np.ndarray | None, # shape (N,) or None
    crs: Crs_V1_0_1,
    tags: dict[str, str],
) -> Pointset_V1_3_0:
    # 1. Upload coordinates via the parquet-hash pattern.
    data_bytes = np.ascontiguousarray(points).tobytes()
    coords_hash = hashlib.sha256(data_bytes).hexdigest().lower()
    save_array_to_parquet(points, os.path.join(str(data_client.cache_location), coords_hash))
    coordinates = FloatArray3_V1_0_1(data=coords_hash, length=points.shape[0])

    # 2. Bounding box.
    bb = BoundingBox_V1_0_1(
        min_x=float(np.min(points[:, 0])), max_x=float(np.max(points[:, 0])),
        min_y=float(np.min(points[:, 1])), max_y=float(np.max(points[:, 1])),
        min_z=float(np.min(points[:, 2])), max_z=float(np.max(points[:, 2])),
    )

    # 3. Optional continuous attribute.
    attributes = None
    if values is not None and len(values) > 0:
        values_hash = hashlib.sha256((name + "_values").encode()).hexdigest().lower()
        save_1d_array_to_parquet(values, os.path.join(str(data_client.cache_location), values_hash))
        attributes = [
            ContinuousAttribute_V1_1_0(
                name="value", key="value",
                nan_description=NanContinuous_V1_0_1(values=[-1.0e32]),
                values=FloatArray1_V1_0_1(data=values_hash, length=len(values)),
            )
        ]

    # 4. Assemble.
    return Pointset_V1_3_0(
        name=name, uuid=None, description=None,
        bounding_box=bb, coordinate_reference_system=crs,
        locations=Pointset_V1_3_0_Locations(coordinates=coordinates, attributes=attributes),
        tags=tags,
    )
```

## Preferred array upload — `data_client.save_table`

For new converters, prefer PyArrow + `save_table` over hand-rolled parquet writes:

```python
import pyarrow as pa

table = pa.table({"x": points[:, 0], "y": points[:, 1], "z": points[:, 2]})
reference = data_client.save_table(table)   # embed `reference` in the element
```

Inspect the exact `save_table` return/signature in your installed version:

```shell
uv run python -c "from evo.objects.utils.data import ObjectDataClient; help(ObjectDataClient.save_table)"
```

## Meshes, lines, grids, block models

- **TriangleMesh / LineSegments**: upload a vertex `FloatArray3` and an index array
  (`IndexArray3` for triangles, index pairs for segments). See `packages/omf` and `packages/obj`.
- **Regular grids**: use `packages/common/grid_data.py` (`RegularGridData`, `TensorGridData`)
  and set origin, cell sizes, counts, and rotation. See `packages/resqml`, `packages/vtk`.
- **Block models**: use the Block Model API via `BlockSyncClient`
  (`packages/common/blockmodel_client.py`), not the object API. See `packages/omf` block model
  and `packages/ubc`.

## Quick local validation harness

Run the builder against a real sample without publishing:

```python
import tempfile

from evo.data_converters.common import create_evo_object_service_and_data_client, EvoWorkspaceMetadata
from evo.data_converters.common.crs import crs_from_epsg_code
from evo.data_converters.<type>.importer.utils import get_geoscience_object_from_<type>

# workspace_id must be a valid UUID — data_client.save_table derives the cache scope from it,
# and a bare cache_root (without workspace_id) raises AttributeError on save_table.
_, data_client = create_evo_object_service_and_data_client(
    evo_workspace_metadata=EvoWorkspaceMetadata(
        workspace_id="00000000-0000-0000-0000-000000000000",
        cache_root=tempfile.mkdtemp(),
    )
)
result = get_geoscience_object_from_<type>(data_client, "<sample>", crs_from_epsg_code(4326))
# The builder may return a single object or a list (see multi-object outputs below).
for obj in (result if isinstance(result, list) else [result]):
    print(type(obj).__name__, obj.bounding_box)
```

## Reference

- Schemas: <https://github.com/SeequentEvo/evo-schemas>
- SDK: <https://github.com/SeequentEvo/evo-python-sdk>
