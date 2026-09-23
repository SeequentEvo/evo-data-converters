# Editing Converter Capabilities

Use this quick workflow to update a converter's capability entry and keep the generated report in sync.

## Where capability files live

Each converter package owns its own capability file:

```
packages/<converter-id>/converter-capabilities.json
```

The file contains a single JSON object describing that one converter (no wrapper, no
`converters` array). `packages/common` is not a converter and has no capability file.

Rendering aggregates every `packages/*/converter-capabilities.json` file into two generated
outputs — **do not edit either by hand**; regenerate them instead (step 3):

- [docs/converter-capabilities.md](../docs/converter-capabilities.md) — human-readable Markdown report.
- [docs/converter-capabilities.json](../docs/converter-capabilities.json) — machine-readable export for
  external consumers (e.g. the developer portal, or another service that wants to know what a converter
  supports) that don't want to parse per-package files or depend on this repo's Python packages. It
  validates against [docs/converter-capabilities.schema.json](../docs/converter-capabilities.schema.json)
  and is fetchable directly, e.g. via the raw GitHub content URL for this file on `main`.

Ownership of `packages/<id>/converter-capabilities.json` follows the existing
[CODEOWNERS](../.github/CODEOWNERS) rule for `packages/<id>/`, since the file lives inside
that package directory.

## 1. Edit the registry
Update or create `packages/<converter-id>/converter-capabilities.json`.

Use the required fields:

- id (must match the package directory name, e.g. `packages/xyz` → `"id": "xyz"`)
- name
- package
- status
- extensions
- platform
- import (`supported`, `source_types`, `produces_evo_objects`)
- export (`supported`, `supports_evo_objects`)
- limitations

## 2. Validate it
From the repo root:

```powershell
uv run --project packages/common python -m scripts.manage_converter_capabilities validate
```

This checks both:
- schema/content validation (required fields, allowed `status` values, nested `import`/`export` fields, duplicate ids); and
- package coverage (every converter package under `packages/` — excluding `packages/common` — must have a valid, matching `converter-capabilities.json`).

If this fails, fix the issue before continuing.

## 3. Regenerate the docs
After the files are valid, generate the Markdown report:

```powershell
uv run --project packages/common python -m scripts.render_converter_capabilities
```

This validates coverage again and updates both [docs/converter-capabilities.md](../docs/converter-capabilities.md)
and [docs/converter-capabilities.json](../docs/converter-capabilities.json).

## 4. Add a new converter entry
If you are adding a new converter instead of editing an existing one:

```powershell
uv run --project packages/common python -m scripts.manage_converter_capabilities add --id my-format --name "My Format"
```

This writes `packages/my-format/converter-capabilities.json` (the `packages/my-format` directory must
already exist — scaffold it first with `create-converter`). Then fill in the new entry and run the
validation and render steps again.

## Automatic CI validation

A GitHub Actions job (`converter-capabilities` in
[`.github/workflows/on-pull-request.yaml`](../.github/workflows/on-pull-request.yaml)) runs on every
pull request. It validates all `packages/*/converter-capabilities.json` files, regenerates
`docs/converter-capabilities.md` and `docs/converter-capabilities.json`, and fails the build if
validation fails or if either regenerated file differs from what's committed. Commit both the
capability file changes and the regenerated docs together.

## Consuming capabilities from outside this repo

External consumers (e.g. the developer portal, or another service) that just need the data — not a
running instance of these converters — should read
[`docs/converter-capabilities.json`](../docs/converter-capabilities.json) rather than parsing Markdown
or depending on individual `packages/*/converter-capabilities.json` files. It's regenerated from those
files on every merge to `main` and validates against
[`docs/converter-capabilities.schema.json`](../docs/converter-capabilities.schema.json). A Python
service could instead depend on `evo-data-converters-common` directly if it already needs that
dependency, but the generated JSON has no such requirement.

