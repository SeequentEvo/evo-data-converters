---
name: scaffold-converter
description: "Use when creating the package skeleton for a new Evo data converter with the create-converter CLI. Runs the scaffolding generator, chooses the converter type and import/export mode, installs the package, and verifies it was registered. Use for: 'scaffold a converter', 'set up a new converter package', 'run create-converter', generating importer/exporter stubs. First phase of building a converter."
---

# Scaffold a converter

Goal: generate a ready-to-implement `packages/<type>/` package with the `create-converter` CLI
and confirm it is wired into the repo. Do this **first**, before discovery: the generated
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

From `packages/common`, run the CLI interactively:

```shell
uv run create-converter
```

The CLI (see [`packages/common/scripts/create_converter.py`](../../../packages/common/scripts/create_converter.py))
prompts for `converter_type` and `export_support`, runs the copier template in
[`packages/common/scripts/converter_template`](../../../packages/common/scripts/converter_template), then updates
`packages/common/pyproject.toml` (adds a `test-<type>` script) and `README.md` (package table + code-samples list).
It also creates the CI workflow `.github/workflows/publish-<type>.yaml` and adds the package to
the test matrix in `.github/workflows/run-all-tests.yaml`.

To run it non-interactively (recommended for agents), pass both answers as flags:

```shell
uv run create-converter --converter-type <type> --export-support 'Import only'
```

`--export-support` accepts `Import only` or `Import and Export`. When both flags are supplied,
the CLI skips all prompts and still performs the pyproject.toml/README/workflow registrations.

> **Always** scaffold with `uv run create-converter`. Do **not** call `copier` directly — the
> raw copier command only renders the template and skips the pyproject.toml/README
> registrations that the CLI's `main()` applies, leaving the repository inconsistent.

## 3. Install the new package

```shell
cd packages/<type>
uv sync
```

## 4. Verify the scaffold

Confirm the package and its wiring exist:

- `packages/<type>/src/evo/data_converters/<type>/importer/` contains `<type>_reader.py`,
  `utils.py`, and `<type>_to_evo.py`.
- `tests/importers/` contains the placeholder tests, and `tests/data/` exists (with a
  `.gitkeep`) ready for the sample file.
- `.github/workflows/publish-<type>.yaml` exists and `<type>` appears in the `package:` matrix
  in `.github/workflows/run-all-tests.yaml`.
- If `Import and Export` was chosen, `exporter/` and export code-samples exist.
- Registration applied:
  ```shell
  grep -n "test-<type>" packages/common/pyproject.toml
  grep -n "evo-data-converters-<type>" README.md
  ```
- The generated tests pass out of the box (they assert the stubs raise `NotImplementedError`):
  ```shell
  uv run test-<type>
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
