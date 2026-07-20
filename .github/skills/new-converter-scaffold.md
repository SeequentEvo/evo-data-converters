# Skill: Scaffold a new data converter package

Use this skill when asked to create a new converter package from scratch (e.g.
"add a converter for format X", "scaffold a new package", "create a new
data converter"). It covers every file that needs to be created and every
existing file that needs to be updated.

---

## Step 1 — Decide the format slug

Choose a short lowercase slug for the format (e.g. `las`, `e57`, `csv`). This
slug is used everywhere: directory name, Python package name, namespace path,
PyPI package name.

```
FORMAT = <slug>           # e.g. "las"
PACKAGE_NAME = evo-data-converters-<slug>
NAMESPACE_PATH = evo/data_converters/<slug>
```

---

## Step 2 — Create the directory tree

Create the following files (all empty except `__init__.py` stubs):

```
packages/<format>/
  LICENSE.md                        ← copy from any existing package
  README.md                         ← brief description (update later)
  pyproject.toml                    ← see Step 3
  src/
    evo/
      __init__.py                   ← namespace marker, see Step 4
      data_converters/
        __init__.py                 ← namespace marker, see Step 4
        <format>/
          __init__.py               ← public API re-exports
          importer/
            __init__.py             ← re-exports convert_<format>
            <format>_to_evo.py     ← top-level entry point
  tests/
    conftest.py                     ← data_client fixture
    importer/
      __init__.py
      test_<format>_to_evo.py      ← initial test stubs
    data/                           ← small sample input files
```

---

## Step 3 — Create `packages/<format>/pyproject.toml`

Use this template exactly, substituting `<format>` and adding any
format-specific dependencies:

```toml
[project]
name = "evo-data-converters-<format>"
description = "Python data converters for <FORMAT> files to Evo geoscience objects"
version = "0.0.1"
requires-python = ">=3.10"
license-files = ["LICENSE.md"]
dynamic = ["readme"]
authors = [
    { name = "Seequent", email = "support@seequent.com" }
]
dependencies = [
    "evo-data-converters-common",
    "numpy>=1.19.0",
    "pyarrow",
    "pyproj",
    # add format-specific reader library here
]

[project.urls]
Source = "https://github.com/SeequentEvo/evo-data-converters"
Tracker = "https://github.com/SeequentEvo/evo-data-converters/issues"
Homepage = "https://www.seequent.com/"
Documentation = "https://developer.seequent.com/"

[dependency-groups]
dev = [
    "pytest",
]

[tool.ruff]
src = ["src", "tests"]
line-length = 120

[build-system]
requires = ["hatchling", "hatch-fancy-pypi-readme"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.sdist]
include = ["src"]

[tool.hatch.build.targets.wheel]
packages = ["src/evo"]

[tool.hatch.metadata.hooks.fancy-pypi-readme]
content-type = "text/markdown"

[[tool.hatch.metadata.hooks.fancy-pypi-readme.fragments]]
path = "README.md"
```

> **Note:** The root `pyproject.toml` uses `[tool.uv.workspace] members =
> ["packages/*"]` so the new package is **automatically discovered** — no
> changes to the root `pyproject.toml` are needed.

---

## Step 4 — Namespace `__init__.py` files

The `src/evo/` and `src/evo/data_converters/` directories are **PEP 420
namespace packages**. Their `__init__.py` files must be empty (or contain only
a comment). Do NOT add imports to them.

```python
# This file intentionally left empty — namespace package marker.
```

The `src/evo/data_converters/<format>/__init__.py` re-exports the public API:

```python
from .importer import convert_<format>

__all__ = ["convert_<format>"]
```

---

## Step 5 — Write the top-level entry point

Create `packages/<format>/src/evo/data_converters/<format>/importer/<format>_to_evo.py`.
Follow the converter entry-point pattern from `new-converter.instructions.md`:

```python
#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License"); ...

from typing import Optional

import evo.logging
from evo_schemas.components import BaseSpatialDataProperties_V1_0_1

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects_sync,
    crs_from_any,
)

logger = evo.logging.getLogger("data_converters")


def convert_<format>(
    filepath: str,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    coordinate_reference_system: str | int | None = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
) -> list[BaseSpatialDataProperties_V1_0_1]:
    """Converts a <FORMAT> file into Evo Geoscience Objects.

    :param filepath: Path to the <FORMAT> file.
    :param evo_workspace_metadata: Evo workspace credentials and config.
    :param coordinate_reference_system: EPSG code (int or "EPSG:NNNN" string),
        OGC WKT string, or None for unspecified.
    :param upload_path: Path prefix objects will be published under.
    :param publish_objects: Set False to return objects without publishing.
    :param overwrite_existing_objects: Set True to overwrite existing objects.
    :return: List of Geoscience Objects, or ObjectMetadata if published.
    """
    crs = crs_from_any(coordinate_reference_system)
    object_service_client, data_client = create_evo_object_service_and_data_client(evo_workspace_metadata)

    objects = _read_and_convert(filepath, data_client, crs)

    if publish_objects:
        return publish_geoscience_objects_sync(
            objects,
            object_service_client,
            data_client,
            path_prefix=upload_path,
            overwrite_existing_objects=overwrite_existing_objects,
        )
    return objects


def _read_and_convert(filepath, data_client, crs):
    # TODO: implement source file reading and per-object conversion
    raise NotImplementedError
```

---

## Step 6 — Write `tests/conftest.py`

```python
import pytest
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)


@pytest.fixture(scope="session")
def evo_metadata(tmp_path_factory):
    cache_root = tmp_path_factory.mktemp("cache")
    return EvoWorkspaceMetadata(
        workspace_id="00000000-0000-0000-0000-000000000000",
        cache_root=str(cache_root),
    )


@pytest.fixture(scope="session")
def data_client(evo_metadata):
    _, client = create_evo_object_service_and_data_client(evo_metadata)
    return client
```

---

## Step 7 — Update `packages/<format>/src/evo/data_converters/<format>/importer/__init__.py`

```python
from .<format>_to_evo import convert_<format>

__all__ = ["convert_<format>"]
```

---

## Step 8 — Register in the root `pyproject.toml`

Because `[tool.uv.workspace] members = ["packages/*"]` is a glob, the new
package is **already a workspace member** once the directory exists. No edit
needed.

However, if you want the root `evo-data-converters` meta-package to depend on
the new converter (so `uv sync --all-packages` installs it), add it to the root
`pyproject.toml`:

```toml
# in [project].dependencies
"evo-data-converters-<format>",

# in [tool.uv.sources]
evo-data-converters-<format> = { workspace = true }
```

---

## Step 9 — Verify the scaffold

```powershell
uv sync --all-packages
uv run pytest packages/<format>/tests/
```

If `uv sync` fails with a missing package error, check the `pyproject.toml`
dependencies and ensure the format-specific reader library is available on PyPI
or declared as a workspace source.

---

## Checklist

- [ ] `pyproject.toml` created with correct name, version `0.0.1`, and dependencies
- [ ] Namespace `__init__.py` files are empty (not importing anything)
- [ ] Top-level `convert_<format>()` function created with correct signature
- [ ] `conftest.py` has `data_client` fixture
- [ ] `uv sync --all-packages` succeeds
- [ ] `uv run pytest packages/<format>/tests/` runs (tests may be stubs — that's fine)
- [ ] Root `pyproject.toml` updated if the package should be in the meta-package
