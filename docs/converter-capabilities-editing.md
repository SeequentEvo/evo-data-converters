# Editing Converter Capabilities

Use this quick workflow to update [converter-capabilities.json](../converter-capabilities.json) and keep the generated report in sync.

## 1. Edit the registry
Update the converter entry in [converter-capabilities.json](../converter-capabilities.json).

Use the required fields:

- id
- name
- package
- status
- extensions
- platform
- import
- export
- limitations

## 2. Validate it
From the repo root:

```powershell
uv run --project packages/common python -m scripts.manage_converter_capabilities validate
```

If this fails, fix the issue before continuing.

## 3. Regenerate the docs
After the file is valid, generate the Markdown report:

```powershell
uv run --project packages/common python -m scripts.render_converter_capabilities
```

This updates [docs/converter-capabilities.md](../docs/converter-capabilities.md).

## 4. Add a new converter entry
If you are adding a new converter instead of editing an existing one:

```powershell
uv run --project packages/common python -m scripts.manage_converter_capabilities add --id my-format --name "My Format"
```

Then fill in the new entry and run the validation and render steps again.
