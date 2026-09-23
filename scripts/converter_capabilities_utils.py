from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"
CAPABILITIES_FILENAME = "converter-capabilities.json"

# packages/common is the shared framework, not a converter.
EXCLUDED_PACKAGES = {"common"}

ALLOWED_STATUS = {"implemented", "template_only", "planned"}

CONVERTER_FIELD_ORDER = (
    "id",
    "name",
    "package",
    "status",
    "extensions",
    "platform",
    "import",
    "export",
    "limitations",
)


def discover_converter_packages(packages_dir: Path | None = None) -> list[str]:
    """Return the sorted converter package directory names under ``packages/``.

    A directory counts as a converter package when it contains a ``pyproject.toml``
    and isn't in EXCLUDED_PACKAGES, so unrelated directories (caches, non-package
    folders) are never mistaken for converters.
    """
    packages_dir = packages_dir if packages_dir is not None else PACKAGES_DIR
    if not packages_dir.is_dir():
        return []

    names = []
    for entry in packages_dir.iterdir():
        if not entry.is_dir() or entry.name in EXCLUDED_PACKAGES:
            continue
        if (entry / "pyproject.toml").is_file():
            names.append(entry.name)
    return sorted(names)


def capability_file_path(package_name: str, packages_dir: Path | None = None) -> Path:
    packages_dir = packages_dir if packages_dir is not None else PACKAGES_DIR
    return packages_dir / package_name / CAPABILITIES_FILENAME


@dataclass
class LoadedCapability:
    """The result of loading (or failing to load) one package's capability file."""

    package_name: str
    path: Path
    data: dict | None
    error: str | None = None


def discover_capability_files(packages_dir: Path | None = None) -> list[LoadedCapability]:
    """Load the package-local capability file for every converter package.

    Packages without a capability file are still returned (with ``data=None``) so
    callers can report missing coverage.
    """
    packages_dir = packages_dir if packages_dir is not None else PACKAGES_DIR
    loaded = []
    for package_name in discover_converter_packages(packages_dir):
        path = capability_file_path(package_name, packages_dir)
        if not path.is_file():
            loaded.append(LoadedCapability(package_name, path, None))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            loaded.append(LoadedCapability(package_name, path, None, f"invalid JSON ({exc})"))
            continue
        loaded.append(LoadedCapability(package_name, path, data))
    return loaded


def _display_path(path: Path) -> str:
    """Format a path for error messages: repo-relative when possible, absolute otherwise."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def build_registry(packages_dir: Path | None = None) -> tuple[dict, list[str]]:
    """Aggregate package-local capability files into an in-memory registry.

    Returns ``(registry, errors)``. ``errors`` covers missing capability files,
    malformed JSON, and id/package-directory mismatches; it is independent from the
    schema/content validation performed by ``validate_registry``.
    """
    errors: list[str] = []
    converters: list[dict] = []

    for loaded in discover_capability_files(packages_dir):
        rel_path = _display_path(loaded.path)

        if loaded.error is not None:
            errors.append(f"{rel_path}: {loaded.error}")
            continue
        if loaded.data is None:
            errors.append(
                f"packages/{loaded.package_name} is missing {CAPABILITIES_FILENAME}"
                " (run: uv run --project packages/common python -m scripts.manage_converter_capabilities"
                f" add --id {loaded.package_name} --name <name>)"
            )
            continue
        if not isinstance(loaded.data, dict):
            errors.append(f"{rel_path}: must contain a JSON object")
            continue

        conv_id = loaded.data.get("id")
        if isinstance(conv_id, str) and conv_id != loaded.package_name:
            errors.append(f"{rel_path}: id '{conv_id}' does not match package directory 'packages/{loaded.package_name}'")

        converters.append(loaded.data)

    registry = {
        "schema_version": "1.0",
        "converters": sorted(converters, key=lambda c: c.get("id", "")),
    }
    return registry, errors


def _is_list_of_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_registry(registry: dict) -> list[str]:
    """Validate the schema/content rules for an aggregated registry.

    This operates on the in-memory registry produced by ``build_registry`` and does
    not know about individual files; use ``validate_all`` to combine both layers.
    """
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

        required_fields = set(CONVERTER_FIELD_ORDER)
        missing = required_fields - set(conv.keys())
        for field in sorted(missing):
            errors.append(f"{context} missing required field: {field}")

        conv_id = conv.get("id")
        if isinstance(conv_id, str):
            context = f"converters[{conv_id}]"
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


def validate_all(packages_dir: Path | None = None) -> list[str]:
    """Validate both package coverage (discovery-level) and content (schema-level)."""
    registry, errors = build_registry(packages_dir)
    return [*errors, *validate_registry(registry)]


def normalize_converter_entry(entry: dict) -> dict:
    """Return a copy of ``entry`` with keys in the canonical schema order."""
    normalized = {key: entry[key] for key in CONVERTER_FIELD_ORDER if key in entry}
    for key, value in entry.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


def write_capability_file(package_name: str, entry: dict, packages_dir: Path | None = None) -> Path:
    path = capability_file_path(package_name, packages_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    body = normalize_converter_entry(entry)
    document: dict = {"$schema": "../../converter-capabilities.schema.json", **body}
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def normalize_all(packages_dir: Path | None = None) -> list[Path]:
    """Rewrite every existing package-local capability file in canonical form."""
    written = []
    for loaded in discover_capability_files(packages_dir):
        if loaded.data is None or loaded.error is not None or not isinstance(loaded.data, dict):
            continue
        entry = {key: value for key, value in loaded.data.items() if key != "$schema"}
        written.append(write_capability_file(loaded.package_name, entry, packages_dir))
    return written