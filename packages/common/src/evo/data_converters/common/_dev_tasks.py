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

"""Developer task entry points, exposed as ``[project.scripts]`` in pyproject.toml.

These back the ``uv run`` workflows that previously lived in the Makefile, e.g.
``uv run lint``, ``uv run test``, and ``uv run test-<type>``. They are intended to be
run from within ``packages/common`` (where the dev dependencies live).
"""

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "packages").is_dir() and (parent / "README.md").is_file():
            return parent
    raise RuntimeError("Could not locate the repository root from _dev_tasks.py")


def _package_env() -> dict[str, str]:
    """Environment for per-package uv subprocesses.

    These run from within packages/common's environment, so ``VIRTUAL_ENV`` points at
    common's ``.venv``. Drop it so uv resolves each package's own project environment
    instead of warning about the mismatch.
    """
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    return env


def _run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def lint() -> None:
    """Check formatting and lint rules in the invoking package."""
    package_dir = Path.cwd()
    _run(["ruff", "check", str(package_dir)], cwd=package_dir)
    _run(["ruff", "format", "--check", str(package_dir)], cwd=package_dir)


def lint_fix() -> None:
    """Apply lint and formatting fixes in the invoking package."""
    package_dir = Path.cwd()
    _run(["ruff", "check", "--fix", str(package_dir)], cwd=package_dir)
    _run(["ruff", "format", str(package_dir)], cwd=package_dir)


def create_converter() -> None:
    """Scaffold a new converter package with the repository-level CLI."""
    root = _repo_root()
    script = root / "scripts" / "create_converter.py"
    _run([sys.executable, str(script), *sys.argv[1:]], cwd=root)


def _test_package(package: str) -> int:
    """Sync and run the tests for a single package. Returns its exit code."""
    package_dir = _repo_root() / "packages" / package
    env = _package_env()
    print(f"=== {package} ===")
    sync = subprocess.run(["uv", "sync"], cwd=package_dir, env=env)
    if sync.returncode != 0:
        return sync.returncode
    return subprocess.run(["uv", "run", "pytest", "tests"], cwd=package_dir, env=env).returncode


def test_all() -> None:
    """Run the tests for the package from which the command is invoked."""
    package_dir = Path.cwd()
    returncode = _test_package(package_dir.name)
    # Exit code 5 means "no tests collected", which is not a failure here.
    if returncode not in (0, 5):
        sys.exit(returncode)


def test_package() -> None:
    """Run the tests for a single package, chosen from the invoked script name.

    All ``test-<type>`` entry points map to this function; the package name is
    derived from the console script name, e.g. ``test-xyz`` -> ``xyz``.
    """
    invoked = Path(sys.argv[0]).name
    prefix = "test-"
    if not invoked.startswith(prefix):
        raise RuntimeError(f"test_package invoked as {invoked!r}, expected a 'test-<type>' script name")
    package = invoked[len(prefix) :]
    returncode = _test_package(package)
    if returncode not in (0, 5):
        sys.exit(returncode)
