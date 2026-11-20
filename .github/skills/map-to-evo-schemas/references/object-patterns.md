# Object construction patterns

Copy-adaptable snippets for implementing `get_geoscience_object_from_<type>`. Full working
examples live in [`packages/omf`](../../../../packages/omf) (point sets, meshes, lines, block
model, plus export) and [`packages/obj`](../../../../packages/obj) (triangle meshes).

## Point set

Based on two functions in `packages/omf`:

- `convert_omf_pointset` in
  [`omf_pointset_to_evo.py`](../../../../packages/omf/src/evo/data_converters/omf/importer/omf_pointset_to_evo.py)
  for the geometry.
- `convert_omf_number_attribute` (float branch) in
  [`omf_attributes_to_evo.py`](../../../../packages/omf/src/evo/data_converters/omf/importer/omf_attributes_to_evo.py)
  for a continuous attribute.

How this snippet differs from the source:

- The `omf2` inputs are replaced with plain NumPy arrays:
  - `reader.array_vertices(...) + project.origin + geometry.origin` becomes `vertices_array`.
  - `reader.array_numbers(...)` becomes `numbers` and `null_mask`.
- OMF loops over every attribute through `convert_omf_attributes`. This snippet takes a single
  optional attribute instead.
- `tags` is passed to `Pointset_V1_2_0`. The OMF converter doesn't do this, but the
  `get_geoscience_object_from_<type>` contract requires it.

```python
from uuid import uuid4

import numpy as np
import numpy.typing as npt
import pyarrow as pa
from evo_schemas.components import ContinuousAttribute_V1_1_0, Crs_V1_0_1, NanContinuous_V1_0_1
from evo_schemas.elements import FloatArray1_V1_0_1, FloatArray3_V1_0_1
from evo_schemas.objects import Pointset_V1_2_0, Pointset_V1_2_0_Locations

from evo.objects.utils.data import ObjectDataClient

from evo.data_converters.common.utils import vertices_bounding_box


# From convert_omf_number_attribute (float branch).
def convert_number_attribute(
    attribute_name: str,
    numbers: npt.NDArray[np.floating],
    null_mask: npt.NDArray[np.bool_] | None,
    data_client: ObjectDataClient,
) -> ContinuousAttribute_V1_1_0:
    # No evo object schemas expect float32, so ensure the array is of type float64.
    table = pa.Table.from_arrays([pa.array(numbers, type=pa.float64(), mask=null_mask)], names=["data"])
    array_args = data_client.save_table(table)
    array = FloatArray1_V1_0_1.from_dict(array_args)

    return ContinuousAttribute_V1_1_0(
        name=attribute_name,
        key=str(uuid4()),
        nan_description=NanContinuous_V1_0_1(values=[]),
        values=array,
    )


# From convert_omf_pointset.
def convert_pointset(
    name: str,
    vertices_array: npt.NDArray[np.floating],  # shape (N, 3), absolute world coordinates
    data_client: ObjectDataClient,
    crs: Crs_V1_0_1,
    tags: dict[str, str],
    attribute: tuple[str, npt.NDArray[np.floating], npt.NDArray[np.bool_] | None] | None = None,
) -> Pointset_V1_2_0:
    bounding_box_go = vertices_bounding_box(vertices_array)

    vertices_schema = pa.schema(
        [
            pa.field("x", pa.float64()),
            pa.field("y", pa.float64()),
            pa.field("z", pa.float64()),
        ]
    )

    coordinates_table = pa.Table.from_arrays(
        [pa.array(vertices_array[:, i], type=pa.float64()) for i in range(len(vertices_schema))],
        schema=vertices_schema,
    )
    coordinates_args = data_client.save_table(coordinates_table)
    coordinates_go = FloatArray3_V1_0_1.from_dict(coordinates_args)

    attributes_go = [convert_number_attribute(*attribute, data_client)] if attribute else []

    locations = Pointset_V1_2_0_Locations(
        coordinates=coordinates_go,
        attributes=attributes_go,
    )

    return Pointset_V1_2_0(
        name=name,
        uuid=None,
        bounding_box=bounding_box_go,
        coordinate_reference_system=crs,
        locations=locations,
        tags=tags,
    )


# Demo: save this block as a .py file and run it inside any converter package's environment
# (`uv run python pointset_demo.py`). Arrays are written to a local temp cache; nothing is published.
if __name__ == "__main__":
    import asyncio
    import tempfile

    from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
    from evo.data_converters.common.crs import crs_from_epsg_code

    async def main() -> None:
        _, data_client = await create_evo_object_service_and_data_client(
            evo_workspace_metadata=EvoWorkspaceMetadata(
                workspace_id="00000000-0000-0000-0000-000000000000",
                cache_root=tempfile.mkdtemp(),
            )
        )
        rng = np.random.default_rng(0)
        vertices = rng.random((10, 3)) * 100.0
        grades = rng.random(10)
        null_mask = np.zeros(10, dtype=bool)
        null_mask[3] = True

        pointset = convert_pointset(
            "demo-points", vertices, data_client, crs_from_epsg_code(4326), {"Source": "demo"},
            attribute=("grade", grades, null_mask),
        )
        print(type(pointset).__name__, pointset.bounding_box)
        print("attribute length:", pointset.locations.attributes[0].values.length)

    asyncio.run(main())
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

Run the builder against a real sample without publishing. Replace `<type>` with your converter
type and `<sample>` with the path to a sample file, then run it from the package directory with
`uv run python <script>.py`:

```python
import asyncio
import tempfile

from evo.data_converters.common import create_evo_object_service_and_data_client, EvoWorkspaceMetadata
from evo.data_converters.common.crs import crs_from_epsg_code
from evo.data_converters.<type>.importer.utils import get_geoscience_object_from_<type>


async def main() -> None:
    # create_evo_object_service_and_data_client is async, so it must be awaited.
    # workspace_id must be a valid UUID — data_client.save_table derives the cache scope from it,
    # and a bare cache_root (without workspace_id) raises AttributeError on save_table.
    _, data_client = await create_evo_object_service_and_data_client(
        evo_workspace_metadata=EvoWorkspaceMetadata(
            workspace_id="00000000-0000-0000-0000-000000000000",
            cache_root=tempfile.mkdtemp(),
        )
    )
    result = get_geoscience_object_from_<type>(data_client, "<sample>", crs_from_epsg_code(4326))
    # The builder may return a single object or a list (see "Multiple objects from one file" in SKILL.md).
    for obj in result if isinstance(result, list) else [result]:
        print(type(obj).__name__, obj.bounding_box)


asyncio.run(main())
```

## Reference

- Schemas: <https://github.com/SeequentEvo/evo-schemas>
- SDK: <https://github.com/SeequentEvo/evo-python-sdk>
