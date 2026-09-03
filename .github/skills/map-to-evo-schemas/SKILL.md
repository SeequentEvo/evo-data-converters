---
name: map-to-evo-schemas
description: "Use when implementing the reader and geoscience-object builder for an Evo data converter — turning a parsed file into evo-schemas objects. Covers implementing read_<type>_file, building Pointset/TriangleMesh/grid/etc. objects, uploading arrays via data_client.save_table or the parquet-hash pattern, and setting CRS, bounding box, and tags. Use for: 'implement the converter', 'map data to geoscience objects', 'build the evo_schemas object', 'upload attribute arrays'. Third phase of building a converter."
---

# Map data to Evo schemas

Goal: implement the two stub functions the scaffold generated so `convert_<type>` produces a
real Evo geoscience object. Everything else in `convert_<type>` is already wired.

See [`references/object-patterns.md`](references/object-patterns.md) for copy-adaptable code and
[`packages/xyz`](../../../packages/xyz) / [`packages/omf`](../../../packages/omf) for full
working examples.

## 1. Implement the reader — `<type>_reader.py`

`read_<type>_file(filepath)` parses the file into an intermediate representation of your choice
(a dataclass is recommended). It must:

- Open and read `filepath`; raise `<TYPE>DataFileIOError` on I/O failure.
- Parse into memory (use the open-source library chosen during discovery, or a custom parser).
- Validate; raise `<TYPE>InvalidDataError` on malformed data.
- Return the intermediate object(s) the builder needs (geometry arrays, attribute values, grid
  dimensions, coordinate hints, units).

Prefer returning NumPy arrays / PyArrow tables so the upload step is straightforward.

## 2. Implement the builder — `utils.py`

`get_geoscience_object_from_<type>(data_client, filepath, coordinate_reference_system, tags)`
must:

1. Call `read_<type>_file(filepath)` to get the intermediate data.
2. Extract geometry and per-element values.
3. Upload large arrays and reference them (see step 3).
4. Compute the `BoundingBox_V1_0_1` from the coordinates.
5. Construct and return the `evo_schemas` object (a `BaseSpatialDataProperties_V1_0_1`
   subclass), passing `coordinate_reference_system`, the merged `tags` (the stub already builds
   `object_tags` with `Source`/`Stage`/`InputType` — extend, don't discard them), and
   `uuid=None`.

Keep the CRS handling in `convert_<type>` — the builder just receives and passes through
`coordinate_reference_system`.

### Multiple objects from one file

A single input file may map to more than one Geoscience Object (e.g. one `TriangleMesh` per
element type). In that case:

- Have `get_geoscience_object_from_<type>` return a `list[...]` of objects.
- In `convert_<type>`, replace the generated `geoscience_objects = [get_geoscience_object_from_<type>(...)]`
  with an explicitly typed assignment so `mypy` doesn't flag `no-any-return`:
  ```python
  geoscience_objects: list[BaseSpatialDataProperties_V1_0_1 | ObjectMetadata] = list(
      utils.get_geoscience_object_from_<type>(data_client, filepath, crs, tags)
  )
  ```
- Update the generated `test_<type>_to_evo.py` mocks: `get_geoscience_object_from_<type>` must
  now `return_value=[mock_object]` (a list), and assertions on the published list follow.

### Runtime-configurable options

When the user needs to choose behaviour at conversion time (e.g. how to group geometry), add an
**optional keyword-only** parameter to `convert_<type>` (after the `*`, with a sensible default)
and thread it through to the builder. This does not violate the "don't change the standard
parameters" rule — you are adding, not altering, and keeping the return type. Model the option
as an `Enum` (e.g. `class <TYPE>MeshGrouping(str, Enum)`), export it from the package
`__init__.py`, and surface it in the code samples (see the test and after-import phases).

## 3. Upload referenced arrays

Two supported patterns (see the reference file for full snippets):

- **`data_client.save_table(pyarrow_table)`** — build a PyArrow table and save it; embed the
  returned reference. Preferred for new converters.
- **Parquet-hash** (as in `packages/xyz`) — hash the array bytes, write parquet to
  `os.path.join(str(data_client.cache_location), sha256_hash)`, and reference `data=<hash>` in a
  `FloatArray*` element. Ensure `length` matches the element count.

## 4. Export exports (`__init__.py`)

The generated `__init__.py` already re-exports `convert_<type>` and the exception classes. If
you add new public helpers, export them there too.

## 5. Sanity-check as you go

```shell
uv run ruff check packages/<type>
uv run mypy packages/<type>
```

Then validate against a small real sample by running the object builder directly (no publishing
needed) before moving to full tests — see the reference file for a quick local harness.

## Guardrails

- Don't inline large arrays — always upload and reference them.
- Attribute `length` must equal the number of elements.
- Keep the Apache 2.0 header on any new file.
- Don't hard-code CRS/EPSG or workspace details; they flow in as parameters.

## Next

Proceed to [`test-converter`](../test-converter/SKILL.md).
