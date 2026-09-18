from __future__ import annotations

import argparse
import sys

from scripts.converter_capabilities_utils import (
    load_registry,
    normalize_registry,
    validate_registry,
    write_registry,
)


def _scaffold_converter_entry(converter_id: str, name: str, status: str) -> dict:
    return {
        "id": converter_id,
        "name": name,
        "package": f"evo-data-converters-{converter_id}",
        "status": status,
        "extensions": [
            ".ext"
        ],
        "platform": [
            "Cross-platform (Python)"
        ],
        "import": {
            "supported": False,
            "source_types": [],
            "produces_evo_objects": []
        },
        "export": {
            "supported": False,
            "supports_evo_objects": []
        },
        "limitations": [
            "TODO: document current limitations."
        ]
    }


def cmd_validate(_: argparse.Namespace) -> int:
    registry = load_registry()
    errors = validate_registry(registry)
    if errors:
        print("Validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1
    print("converter-capabilities.json is valid.")
    return 0


def cmd_normalize(_: argparse.Namespace) -> int:
    registry = normalize_registry(load_registry())
    write_registry(registry)
    print("Normalized converter-capabilities.json (sorted by converter id).")
    return cmd_validate(_)


def cmd_add(args: argparse.Namespace) -> int:
    registry = load_registry()
    existing = {c.get("id") for c in registry.get("converters", [])}
    if args.id in existing:
        print(f"Converter id '{args.id}' already exists.")
        return 1

    registry.setdefault("converters", []).append(_scaffold_converter_entry(args.id, args.name, args.status))
    normalize_registry(registry)
    write_registry(registry)
    print(f"Added converter scaffold for '{args.id}'.")
    print("Next steps:")
    print("- Fill in formats, supported objects, and limitations")
    print("- Run: make converter-capabilities-validate")
    print("- Run: make converter-capabilities")
    return cmd_validate(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage converter-capabilities.json safely")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate converter-capabilities.json")
    validate_parser.set_defaults(func=cmd_validate)

    normalize_parser = subparsers.add_parser("normalize", help="Sort and normalize converter-capabilities.json")
    normalize_parser.set_defaults(func=cmd_normalize)

    add_parser = subparsers.add_parser("add", help="Add a new converter scaffold entry")
    add_parser.add_argument("--id", required=True, help="Converter id, for example my-format")
    add_parser.add_argument("--name", required=True, help="Display name, for example My Format")
    add_parser.add_argument(
        "--status",
        default="planned",
        choices=["implemented", "template_only", "planned"],
        help="Initial status",
    )
    add_parser.set_defaults(func=cmd_add)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())