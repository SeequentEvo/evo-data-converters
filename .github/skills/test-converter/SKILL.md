---
name: test-converter
description: "Use when writing and running tests for an Evo data converter, and validating it with linting and type checks. Replaces the generated placeholder tests with real ones using sample data, then runs make test-<type>, ruff, and mypy until green. Use for: 'test the converter', 'write converter tests', 'the converter tests fail', 'run ruff/mypy on the converter'. Final phase of building a converter."
---

# Test a converter

Goal: replace the scaffold's placeholder tests with real ones exercising the reader and object
builder against sample data, then get tests, linting, and type checks passing.

## 1. Understand the generated tests

The scaffold creates, under `packages/<type>/tests/importers/`:

- `test_<type>_reader.py` — asserts `read_<type>_file` raises `NotImplementedError` (placeholder).
- `test_<type>_utils.py` — asserts `get_geoscience_object_from_<type>` raises
  `NotImplementedError` (placeholder).
- `test_<type>_to_evo.py` — real tests for `convert_<type>` using mocks; these already cover
  client creation, publish vs. no-publish, connection-detail errors, and CRS resolution. Keep
  and adapt these; they do **not** need real data.

Replace the two placeholder files once the reader and builder are implemented.

> **`mypy` on the generated tests:** the scaffold's `test_<type>_to_evo.py` ships a parametrized
> test whose function args are untyped (`no-untyped-def`) — annotate them (e.g.
> `input_crs: str | int | None, expected_crs: object`). Fixtures that return a client from
> `create_evo_object_service_and_data_client(...)[1]` trip `no-any-return` — annotate the local
> (`data_client: ObjectDataClient = client`) before returning. If your builder now returns a
> list, update the mocked `get_geoscience_object_from_<type>` to `return_value=[mock_object]`.

## 2. Write reader tests — `test_<type>_reader.py`

- Add a small, license-clear sample file under the package's `tests/` (or reuse one from
  `code-samples`). Keep it tiny.
- Test the happy path: parsing returns the expected shapes/values.
- Test error paths: a missing/unreadable file raises `<TYPE>DataFileIOError`; malformed content
  raises `<TYPE>InvalidDataError`.

## 3. Write builder tests — `test_<type>_utils.py`

- Use a mocked `ObjectDataClient` (see `test_<type>_to_evo.py` and existing converters such as
  `packages/xyz/tests` for the pattern) with a real `cache_location`, or a `tmp_path` fixture.
  If your builder calls `data_client.save_table(...)`, a bare `MagicMock` won't work — create a
  real client via `create_evo_object_service_and_data_client(EvoWorkspaceMetadata(workspace_id=<uuid>, cache_root=<tmp>))`
  (the `workspace_id` must be a valid UUID or `save_table` raises `AttributeError`).
- Assert the returned object is the expected `evo_schemas` type, that the bounding box matches
  the sample, that attribute lengths equal the element count, and that tags include
  `Source`/`Stage`/`InputType`.
- Pass the CRS with `crs_from_epsg_code(...)` from `evo.data_converters.common.crs`.

## 4. Run tests and checks

```shell
make test-<type>              # runs pytest for packages/<type>/tests
uv run ruff check packages/<type>
uv run mypy packages/<type>
```

Iterate until all three are clean. When you change behaviour, update the tests in the same pass.

## 5. Optional: end-to-end smoke test

If the user has Evo credentials and wants a live check, run `convert_<type>` with
`publish_objects=False` against a real sample to confirm a valid object is produced without
touching Evo. Only publish (`publish_objects=True`) when the user explicitly asks and supplies
their own workspace details — never commit those.

## Done criteria

- `make test-<type>` passes with real reader/builder tests (no remaining `NotImplementedError`
  placeholders).
- `ruff` and `mypy` are clean for the package.
- Sample test data is small and appropriately licensed.
