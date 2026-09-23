from __future__ import annotations

import json
from pathlib import Path

from scripts.converter_capabilities_utils import build_registry, normalize_converter_entry, validate_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs"
OUTPUT_MD = OUTPUT_DIR / "converter-capabilities.md"
OUTPUT_JSON = OUTPUT_DIR / "converter-capabilities.json"


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _join(items: list[str]) -> str:
    return ", ".join(items) if items else "-"


def _render_markdown(registry: dict) -> str:
    lines: list[str] = []
    lines.append("# Converter Capability Matrix\n")
    lines.append("This page is generated from `packages/*/converter-capabilities.json`.\n")
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


def _render_json(registry: dict) -> str:
    # Machine-readable export for external consumers (e.g. the developer portal); "$schema"
    # is a per-file editor hint and isn't meaningful on the aggregated collection, so it's dropped.
    converters = [
        normalize_converter_entry({k: v for k, v in conv.items() if k != "$schema"})
        for conv in sorted(registry["converters"], key=lambda c: c["id"])
    ]
    document = {
        "$schema": "./converter-capabilities.schema.json",
        "schema_version": registry["schema_version"],
        "converters": converters,
    }
    return json.dumps(document, indent=2) + "\n"


def main() -> None:
  registry, coverage_errors = build_registry()
  errors = [*coverage_errors, *validate_registry(registry)]
  if errors:
    print("packages/*/converter-capabilities.json are invalid:")
    for err in errors:
      print(f"- {err}")
    raise SystemExit(1)

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

  markdown = _render_markdown(registry)
  OUTPUT_MD.write_text(markdown, encoding="utf-8")
  print(f"Wrote {OUTPUT_MD}")

  OUTPUT_JSON.write_text(_render_json(registry), encoding="utf-8")
  print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()