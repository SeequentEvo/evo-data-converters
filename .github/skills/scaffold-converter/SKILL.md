---
name: scaffold-converter
description: "Use when creating the package skeleton for a new Evo data converter with the create-converter CLI. Runs the scaffolding generator, chooses the converter type and import/export mode, syncs the workspace, and verifies the package was registered. Use for: 'scaffold a converter', 'set up a new converter package', 'run create-converter', generating importer/exporter stubs. First phase of building a converter."
---

# Scaffold a converter

Goal: generate a ready-to-implement `packages/<type>/` package with the `create-converter` CLI
and confirm it is wired into the workspace. Do this **first**, before discovery: the generated
package gives the user a home for their sample data and gives you the stub files you'll fill in
later.

## 1. Choose the converter name and mode

- **converter type**: a short, lowercase format name — e.g. `obj`, `shp`, `xyz`. It becomes the
  package name (`evo-data-converters-<type>`), the module path, and the `convert_<type>` /
  `export_<type>` function names. Pick a name that isn't already under `packages/`.
- **export support**: `Import only` or `Import and Export`. Import-first is the recommended
  path; choose `Import and Export` only if the user wants export stubs generated now (you still
  implement and verify import first).

## 2. Run the generator

From the repository root, run the CLI interactively:

```shell
uv run create-converter
```

The CLI (see [`scripts/create_converter.py`](../../../scripts/create_converter.py)) prompts for
`converter_type` and `export_support`, runs the copier template in
[`scripts/converter_template`](../../../scripts/converter_template), then updates the root
`Makefile` (adds a `test-<type>` target), `README.md` (package table + code-samples list), and
`pyproject.toml` (workspace dependency + `[tool.uv.sources]` entry).

To run it non-interactively (recommended for agents), pass both answers as flags:

```shell
uv run create-converter --converter-type <type> --export-support "Import only"
```

`--export-support` accepts `Import only` or `Import and Export`. When both flags are supplied,
the CLI skips all prompts and still performs the Makefile/README/pyproject registrations.

> **Always** scaffold with `uv run create-converter`. Do **not** call `copier` directly — the
> raw copier command only renders the template and skips the Makefile/README/pyproject
> registrations that the CLI's `main()` applies, leaving the workspace inconsistent.

## 3. Install the new package

```shell
uv sync
```

## 4. Verify the scaffold

Confirm the package and its wiring exist:

- `packages/<type>/src/evo/data_converters/<type>/importer/` contains `<type>_reader.py`,
  `utils.py`, and `<type>_to_evo.py`.
- `tests/importers/` contains the placeholder tests, and `tests/data/` exists (with a
  `.gitkeep`) ready for the sample file.
- If `Import and Export` was chosen, `exporter/` and export code-samples exist.
- Registration applied:
  ```shell
  grep -n "test-<type>" Makefile
  grep -n "evo-data-converters-<type>" README.md pyproject.toml
  ```
- The generated tests pass out of the box (they assert the stubs raise `NotImplementedError`):
  ```shell
  make test-<type>
  ```

## 5. Add the sample data

The template generates `packages/<type>/tests/data/` (the repo convention for sample files —
see `packages/duf/tests/data`, `packages/shp/tests/data`). Ask the user to drop their sample
file there so the next phase can inspect it:

Tell the user: "Put a small, license-clear sample `<type>` file in
`packages/<type>/tests/data/` before we continue to discovery." Keep samples tiny and confirm
licensing before anything is committed.

## What's already implemented vs. what you implement

Already wired (do **not** change the contract): `convert_<type>(...)` in `<type>_to_evo.py`
creates the Evo clients, resolves the CRS, calls the object builder, and publishes.

You implement next (in the mapping phase):

- `read_<type>_file(filepath)` in `<type>_reader.py`
- `get_geoscience_object_from_<type>(data_client, filepath, coordinate_reference_system, tags)`
  in `utils.py`

## Next

Proceed to [`converter-discovery`](../converter-discovery/SKILL.md).
