import argparse
from datetime import date
from pathlib import Path

from copier import run_copy

REPO_ROOT = Path(__file__).resolve().parent.parent

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
        description=(
            "Scaffold a new Evo data converter package and register it in the "
            "Makefile, README.md, and root pyproject.toml."
        ),
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
    worker = run_copy("scripts/converter_template", "packages", data, defaults=non_interactive)

    converter_name = worker.answers.combined["converter_type"]

    print(f"\n{_BOLD}Updating repository configuration for {_CYAN}{converter_name}{_RESET}{_BOLD}...{_RESET}")

    _update_makefile(converter_name)
    _success(f"Updated {_BOLD}Makefile{_RESET} with the {_DIM}test-{converter_name}{_RESET} target")

    _update_readme(converter_name)
    _success(f"Updated {_BOLD}README.md{_RESET} with the package listing and code samples")

    _update_pyproject(converter_name)
    _success(f"Updated {_BOLD}pyproject.toml{_RESET} with the workspace dependency")

    _print_next_steps(converter_name)


def _print_next_steps(converter_name: str) -> None:
    package = f"evo-data-converters-{converter_name}"
    print(f"\n{_BOLD}{_GREEN}Done!{_RESET} Your new converter {_CYAN}{package}{_RESET} is ready.\n")
    print(f"{_BOLD}Next steps:{_RESET}")
    print(f"  {_YELLOW}1.{_RESET} Review the generated package in {_DIM}packages/{converter_name}{_RESET}")
    print(f"  {_YELLOW}2.{_RESET} Sync the workspace:            {_DIM}uv sync{_RESET}")
    print(f"  {_YELLOW}3.{_RESET} Implement your converter in    {_DIM}packages/{converter_name}/src{_RESET}")
    print(f"  {_YELLOW}4.{_RESET} Run the tests:                 {_DIM}make test-{converter_name}{_RESET}")
    print()


def _update_makefile(converter_name: str) -> None:
    makefile_path = REPO_ROOT / "Makefile"
    lines = makefile_path.read_text().splitlines(keepends=True)

    if any(line.startswith(f"test-{converter_name}:") for line in lines):
        return

    command = f"\tuv run --package evo-data-converters-{converter_name} pytest packages/{converter_name}/tests\n"

    # Find the first test-* target that is alphabetically after the new one.
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("test-") and line.rstrip().endswith(":"):
            existing_name = line[len("test-") :].rstrip()[:-1]
            if existing_name > converter_name:
                insert_at = i
                break

    if insert_at is None:
        content = "".join(lines).rstrip("\n") + "\n\n"
        content += f"test-{converter_name}:\n" + command
        makefile_path.write_text(content)
        return

    new_block = [f"test-{converter_name}:\n", command, "\n"]
    lines = lines[:insert_at] + new_block + lines[insert_at:]
    makefile_path.write_text("".join(lines))


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


def _update_pyproject(converter_name: str) -> None:
    pyproject_path = REPO_ROOT / "pyproject.toml"
    lines = pyproject_path.read_text().splitlines(keepends=True)

    package = f"evo-data-converters-{converter_name}"

    dependency_line = f'  "{package}",\n'
    if not any(line.strip().strip('"').startswith(package) for line in lines):
        lines = _insert_sorted(
            lines,
            new_line=dependency_line,
            is_member=lambda line: line.lstrip().startswith('"evo-data-converters-'),
        )

    source_line = f"{package} = {{ workspace = true }}\n"
    if source_line not in lines:
        lines = _insert_sorted(
            lines,
            new_line=source_line,
            is_member=lambda line: line.startswith("evo-data-converters-") and "workspace = true" in line,
        )

    pyproject_path.write_text("".join(lines))


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
