# Editing Converter Capabilities Safely

This guide describes the safest workflow to edit [converter-capabilities.json](../converter-capabilities.json).

## Recommended workflow

1. Validate the current file before editing:

```shell
uv run python scripts/manage_converter_capabilities.py validate
```

2. If adding a new converter, scaffold a valid section instead of writing one manually:

```shell
uv run python scripts/manage_converter_capabilities.py add --id my-format --name "My Format"
```

3. Edit the generated entry fields in [converter-capabilities.json](../converter-capabilities.json).

4. Regenerate stakeholder outputs. This also validates the file and rewrites it in normalized form, so there is no separate normalize step to remember:

```shell
uv run python scripts/render_converter_capabilities.py
```

If validation fails, the command exits without writing anything — fix the reported errors and run it again.

You can still validate or normalize on their own while iterating:

```shell
uv run python scripts/manage_converter_capabilities.py validate
uv run python scripts/manage_converter_capabilities.py normalize
```

## Why this is safe

- The JSON file is linked to [converter-capabilities.schema.json](../converter-capabilities.schema.json), so VS Code can flag shape mistakes while you type.
- The validator checks required fields, duplicate ids/names, array types, and id/package consistency.
- The normalize step keeps converter ordering stable, reducing merge conflicts.

## Required fields per converter

Every converter entry must include these fields:

- id
- name
- package
- status
- formats
- platform
- import
- export
- limitations

## Field glossary

- schema_version: Registry schema version in major.minor format.
- maintainers_note: Maintainer-facing note about how and when to update/regenerate artifacts.
- converters: List of converter capability entries.
- id: Stable converter identifier (lowercase slug, for example obj).
- name: Human-readable converter name.
- package: Python package name; must match id pattern evo-data-converters-{id}.
- status: Lifecycle status (implemented, template_only, planned).
- formats: Source file extensions accepted by the converter.
- platform: Runtime/platform notes and prerequisites.
- import.supported: Whether import to Evo is supported.
- import.source_types: Source-domain data types accepted by import.
- import.produces_evo_objects: Evo object types produced by import.
- export.supported: Whether export from Evo is supported.
- export.supports_evo_objects: Evo object types accepted for export.
- limitations: Known behavior limits, constraints, or caveats.

## Common mistakes caught by validation

- Duplicate converter ids
- Missing import/export subfields
- Non-string entries in arrays
- Package not matching id pattern, for example id xyz must use package evo-data-converters-xyz