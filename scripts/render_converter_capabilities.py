from __future__ import annotations

import json
from pathlib import Path

from scripts.converter_capabilities_utils import normalize_registry, validate_registry, write_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO_ROOT / "converter-capabilities.json"
OUTPUT_DIR = REPO_ROOT / "docs"
OUTPUT_MD = OUTPUT_DIR / "converter-capabilities.md"


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _join(items: list[str]) -> str:
    return ", ".join(items) if items else "-"


def _read_registry() -> dict:
    with INPUT_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _render_markdown(registry: dict) -> str:
    lines: list[str] = []
    lines.append("# Converter Capability Matrix\n")
    lines.append("This page is generated from `converter-capabilities.json`.\n")
    lines.append(
      "| Converter | Status | Import | Export | Extensions | Evo Objects (Import) | Key Limitations |\n"
    )
    lines.append("|---|---|---|---|---|---|---|\n")

    for conv in sorted(registry["converters"], key=lambda c: c["id"]):
        lines.append(
            "| "
            + conv["name"]
            + " | "
            + conv["status"]
            + " | "
            + _yes_no(conv["import"]["supported"])
            + " | "
            + _yes_no(conv["export"]["supported"])
            + " | "
            + _join(conv.get("extensions", []))
            + " | "
            + _join(conv["import"]["produces_evo_objects"])
            + " | "
            + _join(conv["limitations"])
            + " |\n"
        )

    lines.append("\n## Detailed Capabilities\n")

    for conv in sorted(registry["converters"], key=lambda c: c["id"]):
        lines.append(f"### {conv['name']}\n")
        lines.append(f"- Package: `{conv['package']}`\n")
        lines.append(f"- Status: `{conv['status']}`\n")
        lines.append(f"- Import supported: `{_yes_no(conv['import']['supported'])}`\n")
        lines.append(f"- Export supported: `{_yes_no(conv['export']['supported'])}`\n")
        lines.append(f"- Extensions: {_join(conv.get('extensions', []))}\n")
        lines.append(f"- Platform/runtime notes: {_join(conv.get('platform', []))}\n")
        lines.append(f"- Import source types: {_join(conv['import']['source_types'])}\n")
        lines.append(f"- Evo objects produced: {_join(conv['import']['produces_evo_objects'])}\n")
        lines.append(f"- Evo objects export supports: {_join(conv['export']['supports_evo_objects'])}\n")
        lines.append(f"- Limitations: {_join(conv['limitations'])}\n")
        lines.append("\n")

    return "".join(lines)


def main() -> None:
  registry = normalize_registry(_read_registry())
  errors = validate_registry(registry)
  if errors:
    print("converter-capabilities.json is invalid:")
    for err in errors:
      print(f"- {err}")
    raise SystemExit(1)

  # Rewriting is idempotent, so an already-normalized file produces no diff.
  write_registry(registry)

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

  markdown = _render_markdown(registry)
  OUTPUT_MD.write_text(markdown, encoding="utf-8")

  print(f"Normalized {INPUT_FILE}")
  print(f"Wrote {OUTPUT_MD}")


if __name__ == "__main__":
    main()