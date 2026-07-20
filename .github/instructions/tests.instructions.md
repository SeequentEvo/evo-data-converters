---
applyTo: "packages/*/tests/**"
---
# Test conventions for data converters

## Overview

Each converter package has a `tests/` directory. Tests use `pytest` and should
cover the converter's core transformation logic — not the Evo API itself.

```
packages/<format>/tests/
  conftest.py          ← session-scoped fixtures: data_client, sample data
  utils.py             ← helpers for reading test data back from Parquet
  importer/            ← one file per converter module
    test_<format>_<type>_to_evo.py
  data/                ← small test input files
```

See `packages/duf/tests/` for a complete reference.

---

## Fixtures

### `data_client` fixture

The `data_client` fixture must create a real `ObjectDataClient` backed by a
temporary directory. Do not mock it — the converter writes Parquet files through
it and tests read them back to verify array contents.

```python
import pytest
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)

@pytest.fixture(scope="session")
def evo_metadata(tmp_path_factory):
    cache_root = tmp_path_factory.mktemp("cache")
    return EvoWorkspaceMetadata(
        workspace_id="00000000-0000-0000-0000-000000000000",
        cache_root=str(cache_root),
    )

@pytest.fixture(scope="session")
def data_client(evo_metadata):
    _, client = create_evo_object_service_and_data_client(evo_metadata)
    return client
```

### Reading Parquet data back in tests

Use `pyarrow.parquet.read_table` to load a table written by `data_client` and
verify its contents. The cache location is at `data_client.cache_location`.

```python
import pyarrow.parquet as pq
import os

def load_table(data_client, table_ref):
    parquet_path = os.path.join(str(data_client.cache_location), table_ref.data)
    return pq.read_table(parquet_path)
```

See `packages/duf/tests/utils.py` for `extract_single_attr_value` and
`extract_attr_values` helpers that follow this pattern.

---

## What to test

For each converter module, write tests that verify:

1. **Object type** — the returned object is the expected schema class  
   `assert isinstance(result, TriangleMesh_V2_1_0)`

2. **Object fields** — `name`, `uuid=None`, `coordinate_reference_system`  
   Use `assert result == expected` with a hand-constructed expected object.
   Substitute `result.bounding_box` and `result.triangles` for fields you
   validate separately.

3. **Bounding box** — min/max values match the known extents of the test data  
   ```python
   expected_bbox = BoundingBox_V1_0_1(min_x=0.0, max_x=10.0, ...)
   assert result.bounding_box == expected_bbox
   ```

4. **Array shape and dtype** — read the Parquet table back and check row count
   and column types  
   ```python
   table = load_table(data_client, result.triangles.vertices)
   assert table.num_rows == expected_vertex_count
   assert table.schema.field("x").type == pa.float64()
   ```

5. **Attribute correctness** — for each attribute, verify name, type, and a
   sample of values.

6. **Edge cases** — empty geometry, missing optional fields, unsupported types
   (ensure a warning is logged, not a crash).

---

## Unit testing individual converter functions

Test the low-level per-type converter functions directly rather than going
through the top-level entry point. For example:

```python
from evo.data_converters.omf.importer.omf_surface_to_evo import convert_omf_surface

def test_convert_surface(data_client, sample_surface_element, sample_project, sample_reader):
    crs = crs_from_epsg_code(32650)
    result = convert_omf_surface(sample_surface_element, sample_project, sample_reader, data_client, crs)
    assert isinstance(result, TriangleMesh_V2_1_0)
```

---

## Using `EvoDataConvertersTestCase` for unittest-style tests

For tests that need a full mock connector and storage (e.g. testing
`publish_geoscience_objects`), use the base class from `test_tools`:

```python
from evo.data_converters.common.test_tools import EvoDataConvertersTestCase

class TestPublish(EvoDataConvertersTestCase):
    def test_publish_returns_metadata(self):
        # self.workspace_metadata is pre-configured
        # self.data_client is available
        ...
```

---

## Platform guards

If a converter only works on Windows (e.g. DUF which uses a Windows-only
library), add this to `conftest.py`:

```python
import sys
from pathlib import Path

def pytest_ignore_collect(collection_path: Path, config) -> bool:
    return not sys.platform.startswith("win")
```

---

## Test data

- Keep test data files small (< 100 KB where possible).
- Store them in `packages/<format>/tests/data/`.
- Use synthetic/generated data rather than real customer data.
- Name files descriptively: `simple_triangle_mesh.omf`, `empty_pointset.xyz`.
