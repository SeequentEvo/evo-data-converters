from __future__ import annotations

import argparse
import sys

from scripts.converter_capabilities_utils import (
    PACKAGES_DIR,
    capability_file_path,
    normalize_all,
    validate_all,
    write_capability_file,
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
    errors = validate_all()
    if errors:
        print("Validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1
    print("All packages/*/converter-capabilities.json files are valid.")
    return 0


def cmd_normalize(_: argparse.Namespace) -> int:
    written = normalize_all()
    print(f"Normalized {len(written)} converter-capabilities.json file(s).")
    return cmd_validate(_)


def cmd_add(args: argparse.Namespace) -> int:
    package_dir = PACKAGES_DIR / args.id
    if not package_dir.is_dir():
        print(f"Package directory 'packages/{args.id}' does not exist. Scaffold it first with create-converter.")
        return 1

    capability_path = capability_file_path(args.id)
    if capability_path.exists():
        print(f"Converter capability file already exists: packages/{args.id}/converter-capabilities.json")
        return 1

    write_capability_file(args.id, _scaffold_converter_entry(args.id, args.name, args.status))
    print(f"Added converter capability file for '{args.id}' at packages/{args.id}/converter-capabilities.json")
    print("Next steps:")
    print("- Fill in formats, supported objects, and limitations")
    print("- Run: uv run --project packages/common python -m scripts.manage_converter_capabilities validate")
    print("- Run: uv run --project packages/common python -m scripts.render_converter_capabilities")
    return cmd_validate(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage packages/*/converter-capabilities.json files safely")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate all converter-capabilities.json files")
    validate_parser.set_defaults(func=cmd_validate)

    normalize_parser = subparsers.add_parser(
        "normalize", help="Normalize the key order of all converter-capabilities.json files"
    )
    normalize_parser.set_defaults(func=cmd_normalize)

    add_parser = subparsers.add_parser("add", help="Add a new converter capability file")
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