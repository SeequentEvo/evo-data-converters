#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import argparse
from datetime import date
from pathlib import Path

from copier import run_copy

# This file lives at <repo>/scripts/create_converter.py.
REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = Path(__file__).resolve().parent / "converter_template"
WORKFLOW_TEMPLATE_DIR = Path(__file__).resolve().parent / "workflow_template"

EXPORT_CHOICES = ("Import only", "Import and Export")

# ANSI escape codes for prettier terminal output.
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


def _success(message: str) -> None:
    print(f"  {_GREEN}✓{_RESET} {message}")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="create-converter",
        description=("Scaffold a new Evo data converter package and register it in pyproject.toml and README.md."),
    )
    parser.add_argument(
        "--converter-type",
        help="Short, lowercase format name (e.g. obj, shp, xyz). Becomes the package and module name.",
    )
    parser.add_argument(
        "--export-support",
        choices=EXPORT_CHOICES,
        help="Whether the converter supports exporting as well as importing.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    data = {"year": date.today().year}
    if args.converter_type is not None:
        data["converter_type"] = args.converter_type
    if args.export_support is not None:
        data["export_support"] = args.export_support

    # When all answers are supplied on the command line, run without prompting.
    non_interactive = args.converter_type is not None and args.export_support is not None
    worker = run_copy(str(TEMPLATE_DIR), str(REPO_ROOT / "packages"), data, defaults=non_interactive)

    converter_name = worker.answers.combined["converter_type"]

    print(f"\n{_BOLD}Updating repository configuration for {_CYAN}{converter_name}{_RESET}{_BOLD}...{_RESET}")

    _update_pyproject_scripts(converter_name)
    _success(
        f"Updated {_BOLD}packages/common/pyproject.toml{_RESET} with the {_DIM}test-{converter_name}{_RESET} script"
    )

    _update_readme(converter_name)
    _success(f"Updated {_BOLD}README.md{_RESET} with the package listing and code samples")

    _create_publish_workflow(converter_name)
    _success(
        f"Created {_BOLD}.github/workflows/publish-{converter_name}.yaml{_RESET} for building and publishing the package"
    )

    _update_run_all_tests(converter_name)
    _success(
        f"Updated {_BOLD}.github/workflows/run-all-tests.yaml{_RESET} with the {_DIM}{converter_name}{_RESET} package"
    )

    _print_next_steps(converter_name)


def _print_next_steps(converter_name: str) -> None:
    package = f"evo-data-converters-{converter_name}"
    print(f"\n{_BOLD}{_GREEN}Done!{_RESET} Your new converter {_CYAN}{package}{_RESET} is ready.\n")
    print(f"{_BOLD}Next steps:{_RESET}")
    print(f"  {_YELLOW}1.{_RESET} Review the generated package in {_DIM}packages/{converter_name}{_RESET}")
    print(f"  {_YELLOW}2.{_RESET} Install the package:           {_DIM}cd packages/{converter_name} && uv sync{_RESET}")
    print(f"  {_YELLOW}3.{_RESET} Implement your converter in    {_DIM}packages/{converter_name}/src{_RESET}")
    print(f"  {_YELLOW}4.{_RESET} Run the tests (from packages/common): {_DIM}uv run test-{converter_name}{_RESET}")
    print()


def _update_pyproject_scripts(converter_name: str) -> None:
    pyproject_path = REPO_ROOT / "packages" / "common" / "pyproject.toml"
    lines = pyproject_path.read_text().splitlines(keepends=True)

    new_line = f'test-{converter_name} = "evo.data_converters.common._dev_tasks:test_package"\n'
    if any(line.startswith(f"test-{converter_name} =") for line in lines):
        return

    def is_test_script(line: str) -> bool:
        return line.startswith("test-") and "_dev_tasks:test_package" in line

    lines = _insert_sorted(lines, new_line=new_line, is_member=is_test_script)
    pyproject_path.write_text("".join(lines))


def _update_readme(converter_name: str) -> None:
    readme_path = REPO_ROOT / "README.md"
    lines = readme_path.read_text().splitlines(keepends=True)

    package = f"evo-data-converters-{converter_name}"

    table_row = (
        f"| [{package}](packages/{converter_name}/README.md) "
        f'| <a href="https://pypi.org/project/{package}/">'
        f'<img alt="PyPI - Version" src="https://img.shields.io/pypi/v/{package}" /></a> |\n'
    )
    if package not in "".join(lines):
        lines = _insert_sorted(
            lines,
            new_line=table_row,
            is_member=lambda line: line.startswith("| [evo-data-converters-"),
        )

    sample_line = f"   * [{converter_name.upper()}](packages/{converter_name}/code-samples)\n"
    if sample_line not in lines:
        lines = _insert_sorted(
            lines,
            new_line=sample_line,
            is_member=lambda line: line.lstrip().startswith("* [") and "code-samples)" in line,
        )

    readme_path.write_text("".join(lines))


def _create_publish_workflow(converter_name: str) -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / f"publish-{converter_name}.yaml"
    if workflow_path.exists():
        return

    # Render the workflow template into the repository root, producing
    # .github/workflows/publish-<type>.yaml.
    run_copy(
        str(WORKFLOW_TEMPLATE_DIR),
        str(REPO_ROOT),
        {"converter_type": converter_name},
        defaults=True,
        overwrite=True,
        quiet=True,
    )


def _update_run_all_tests(converter_name: str) -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "run-all-tests.yaml"
    lines = workflow_path.read_text().splitlines(keepends=True)

    new_line = f"          - {converter_name}\n"
    if new_line in lines:
        return

    # Locate the "package:" key in the test matrix and the block of entries beneath it.
    try:
        start = lines.index("        package:\n") + 1
    except ValueError:
        return

    entry_prefix = "          - "
    end = start
    while end < len(lines) and lines[end].startswith(entry_prefix):
        end += 1

    # Keep the block sorted, leaving "common" first.
    insert_at = end
    for i in range(start, end):
        if lines[i] > new_line:
            insert_at = i
            break

    lines = lines[:insert_at] + [new_line] + lines[insert_at:]
    workflow_path.write_text("".join(lines))


def _insert_sorted(lines, new_line, is_member):
    """Insert new_line into lines, keeping the block of member lines sorted."""
    member_indices = [i for i, line in enumerate(lines) if is_member(line)]
    if not member_indices:
        return lines

    insert_at = member_indices[-1] + 1
    for i in member_indices:
        if lines[i] > new_line:
            insert_at = i
            break

    return lines[:insert_at] + [new_line] + lines[insert_at:]


if __name__ == "__main__":
    main()
