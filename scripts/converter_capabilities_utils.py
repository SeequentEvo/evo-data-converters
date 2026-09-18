from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "converter-capabilities.json"

ALLOWED_STATUS = {"implemented", "template_only", "planned"}


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_registry(registry: dict, path: Path = REGISTRY_PATH) -> None:
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def normalize_registry(registry: dict) -> dict:
    registry["converters"] = sorted(registry.get("converters", []), key=lambda c: c.get("id", ""))
    return registry


def _is_list_of_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_registry(registry: dict) -> list[str]:
    errors: list[str] = []

    required_root = {"schema_version", "converters"}
    for key in required_root:
        if key not in registry:
            errors.append(f"Missing root field: {key}")

    converters = registry.get("converters")
    if not isinstance(converters, list):
        errors.append("Root field converters must be a list")
        return errors

    ids: set[str] = set()
    names: set[str] = set()

    for index, conv in enumerate(converters):
        context = f"converters[{index}]"
        if not isinstance(conv, dict):
            errors.append(f"{context} must be an object")
            continue

        required_fields = {
            "id",
            "name",
            "package",
            "status",
            "extensions",
            "platform",
            "import",
            "export",
            "limitations",
        }
        missing = required_fields - set(conv.keys())
        for field in sorted(missing):
            errors.append(f"{context} missing required field: {field}")

        conv_id = conv.get("id")
        if isinstance(conv_id, str):
            if conv_id in ids:
                errors.append(f"{context} duplicate id: {conv_id}")
            ids.add(conv_id)
        else:
            errors.append(f"{context}.id must be a string")

        conv_name = conv.get("name")
        if isinstance(conv_name, str):
            if conv_name in names:
                errors.append(f"{context} duplicate name: {conv_name}")
            names.add(conv_name)
        else:
            errors.append(f"{context}.name must be a string")

        package = conv.get("package")
        if not isinstance(package, str):
            errors.append(f"{context}.package must be a string")
        elif isinstance(conv_id, str):
            expected = f"evo-data-converters-{conv_id}"
            if package != expected:
                errors.append(f"{context}.package must match id (expected {expected}, got {package})")

        status = conv.get("status")
        if status not in ALLOWED_STATUS:
            errors.append(f"{context}.status must be one of: {sorted(ALLOWED_STATUS)}")

        extensions = conv.get("extensions")
        if not _is_list_of_strings(extensions) or not extensions:
            errors.append(f"{context}.extensions must be a non-empty list of strings")

        for array_field in ("platform", "limitations"):
            if not _is_list_of_strings(conv.get(array_field)):
                errors.append(f"{context}.{array_field} must be a list of strings")

        import_block = conv.get("import")
        if not isinstance(import_block, dict):
            errors.append(f"{context}.import must be an object")
        else:
            if not isinstance(import_block.get("supported"), bool):
                errors.append(f"{context}.import.supported must be a boolean")
            for key in ("source_types", "produces_evo_objects"):
                if not _is_list_of_strings(import_block.get(key)):
                    errors.append(f"{context}.import.{key} must be a list of strings")

        export_block = conv.get("export")
        if not isinstance(export_block, dict):
            errors.append(f"{context}.export must be an object")
        else:
            if not isinstance(export_block.get("supported"), bool):
                errors.append(f"{context}.export.supported must be a boolean")
            if not _is_list_of_strings(export_block.get("supports_evo_objects")):
                errors.append(f"{context}.export.supports_evo_objects must be a list of strings")

    return errors