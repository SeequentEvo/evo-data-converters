from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.converter_capabilities_utils import normalize_registry, validate_registry, write_registry


REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO_ROOT / "converter-capabilities.json"
OUTPUT_DIR = REPO_ROOT / "docs"
OUTPUT_MD = OUTPUT_DIR / "converter-capabilities.md"
OUTPUT_HTML = OUTPUT_DIR / "converter-capabilities.html"


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _join(items: list[str]) -> str:
    return ", ".join(items) if items else "-"


def _read_registry() -> dict:
    with INPUT_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _render_markdown(registry: dict, generated_utc: str) -> str:
    lines: list[str] = []
    lines.append("# Converter Capability Matrix\n")
    lines.append("This page is generated from `converter-capabilities.json`.\n")
    lines.append(f"Generated (UTC): {generated_utc}\n")
    lines.append(
      "| Converter | Status | Import | Export | Source Formats | Evo Objects (Import) | Key Limitations |\n"
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
            + _join(conv["formats"])
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
        lines.append(f"- Source formats: {_join(conv['formats'])}\n")
        lines.append(f"- Platform/runtime notes: {_join(conv.get('platform', []))}\n")
        lines.append(f"- Import source types: {_join(conv['import']['source_types'])}\n")
        lines.append(f"- Evo objects produced: {_join(conv['import']['produces_evo_objects'])}\n")
        lines.append(f"- Evo objects export supports: {_join(conv['export']['supports_evo_objects'])}\n")
        lines.append(f"- Limitations: {_join(conv['limitations'])}\n")
        lines.append("\n")

    return "".join(lines)


def _render_html(registry: dict, generated_utc: str) -> str:
    rows = []
    for conv in sorted(registry["converters"], key=lambda c: c["id"]):
        row = (
            "<tr>"
            f"<td>{html.escape(conv['name'])}</td>"
            f"<td>{html.escape(conv['status'])}</td>"
            f"<td>{_yes_no(conv['import']['supported'])}</td>"
            f"<td>{_yes_no(conv['export']['supported'])}</td>"
            f"<td>{html.escape(_join(conv['formats']))}</td>"
            f"<td>{html.escape(_join(conv['import']['produces_evo_objects']))}</td>"
            f"<td>{html.escape(_join(conv['limitations']))}</td>"
            "</tr>"
        )
        rows.append(row)

    table_rows = "\n".join(rows)

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Converter Capability Matrix</title>
  <style>
    :root {{
      --bg: #f4f7f9;
      --card: #ffffff;
      --ink: #0f2430;
      --muted: #47606d;
      --line: #d7e1e8;
      --head: #e9f0f5;
      --accent: #006d77;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(900px 420px at 100% -10%, #d6e9f2 0%, transparent 60%),
        radial-gradient(700px 360px at -5% 110%, #dcefe8 0%, transparent 58%),
        var(--bg);
    }}
    .wrap {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 2rem 1rem 3rem;
    }}
    .hero {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 1.1rem 1.2rem;
      box-shadow: 0 8px 22px rgba(15, 36, 48, 0.06);
      margin-bottom: 1rem;
    }}
    h1 {{ margin: 0 0 0.5rem; font-size: 1.5rem; }}
    .meta {{ color: var(--muted); font-size: 0.95rem; }}
    .controls {{
      display: flex;
      gap: 0.6rem;
      flex-wrap: wrap;
      margin: 0.9rem 0 1rem;
    }}
    input, select {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.55rem 0.65rem;
      font-size: 0.95rem;
      background: #fff;
      min-width: 180px;
    }}
    .table-card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: auto;
      box-shadow: 0 8px 22px rgba(15, 36, 48, 0.06);
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 900px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 0.65rem; text-align: left; vertical-align: top; }}
    th {{ background: var(--head); font-weight: 600; }}
    tr:hover td {{ background: #f8fbfd; }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 0.12rem 0.5rem;
      font-size: 0.8rem;
      border: 1px solid var(--line);
      color: var(--muted);
      background: #fbfdff;
    }}
    .yes {{ color: #0a6a40; font-weight: 600; }}
    .no {{ color: #8e2a2a; font-weight: 600; }}
    .footer-note {{ margin-top: 0.85rem; color: var(--muted); font-size: 0.9rem; }}
    @media (max-width: 700px) {{
      h1 {{ font-size: 1.25rem; }}
      .hero {{ padding: 0.9rem; }}
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <section class=\"hero\">
      <h1>Evo Data Converter Capability Matrix</h1>
      <div class=\"meta\">Generated (UTC): {html.escape(generated_utc)}</div>
      <div class=\"controls\">
        <input id=\"search\" type=\"search\" placeholder=\"Filter converters, objects, limitations...\" />
        <select id=\"importFilter\">
          <option value=\"all\">Import: All</option>
          <option value=\"yes\">Import: Yes</option>
          <option value=\"no\">Import: No</option>
        </select>
        <select id=\"exportFilter\">
          <option value=\"all\">Export: All</option>
          <option value=\"yes\">Export: Yes</option>
          <option value=\"no\">Export: No</option>
        </select>
      </div>
      <span class=\"pill\">Source of truth: converter-capabilities.json</span>
    </section>

    <section class=\"table-card\">
      <table id=\"capabilityTable\">
        <thead>
          <tr>
            <th>Converter</th>
            <th>Status</th>
            <th>Import</th>
            <th>Export</th>
            <th>Formats</th>
            <th>Import Objects</th>
            <th>Limitations</th>
          </tr>
        </thead>
        <tbody>
{table_rows}
        </tbody>
      </table>
    </section>
    <div class=\"footer-note\">Regenerate with: uv run python scripts/render_converter_capabilities.py</div>
  </div>

  <script>
    const search = document.getElementById('search');
    const importFilter = document.getElementById('importFilter');
    const exportFilter = document.getElementById('exportFilter');
    const table = document.getElementById('capabilityTable');
    const rows = Array.from(table.querySelectorAll('tbody tr'));

    function applyFilters() {{
      const q = search.value.trim().toLowerCase();
      const iVal = importFilter.value;
      const eVal = exportFilter.value;

      rows.forEach((row) => {{
        const cells = row.querySelectorAll('td');
        const text = row.textContent.toLowerCase();
        const iText = cells[2].textContent.trim().toLowerCase();
        const eText = cells[3].textContent.trim().toLowerCase();
        const iMatch = iVal === 'all' || iText === iVal;
        const eMatch = eVal === 'all' || eText === eVal;
        const qMatch = !q || text.includes(q);
        row.style.display = (iMatch && eMatch && qMatch) ? '' : 'none';

        cells[2].className = iText === 'yes' ? 'yes' : 'no';
        cells[3].className = eText === 'yes' ? 'yes' : 'no';
      }});
    }}

    search.addEventListener('input', applyFilters);
    importFilter.addEventListener('change', applyFilters);
    exportFilter.addEventListener('change', applyFilters);
    applyFilters();
  </script>
</body>
</html>
"""


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

  generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

  markdown = _render_markdown(registry, generated_utc)
  OUTPUT_MD.write_text(markdown, encoding="utf-8")

  html_report = _render_html(registry, generated_utc)
  OUTPUT_HTML.write_text(html_report, encoding="utf-8")

  print(f"Normalized {INPUT_FILE}")
  print(f"Wrote {OUTPUT_MD}")
  print(f"Wrote {OUTPUT_HTML}")


if __name__ == "__main__":
    main()