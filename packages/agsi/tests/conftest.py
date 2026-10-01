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

import io
import zipfile
from pathlib import Path
from typing import Callable, Optional

import ezdxf
import numpy as np
import pytest
import shapely

DATA_DIR = Path(__file__).parent / "data"
V06_PACKAGE_DIR = DATA_DIR / "silvertown_mini_v06"
V1_PACKAGE_DIR = DATA_DIR / "agsi_v1_minimal"


def wkt_line_to_dxf(wkt: str) -> bytes:
    """Write a WKT LINESTRING as a chain of DXF LINE entities (as in the published DXF examples)."""
    # 2D WKT gives NaN Z; the published 2D DXF examples use Z = 0.
    coords = np.nan_to_num(shapely.get_coordinates(shapely.from_wkt(wkt), include_z=True))
    doc = ezdxf.new()
    msp = doc.modelspace()
    for start, end in zip(coords[:-1], coords[1:]):
        msp.add_line(tuple(start), tuple(end))
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def zip_folder(folder: Path, target: Path, rename: Optional[Callable[[str, bytes], tuple[str, bytes]]] = None) -> Path:
    """Zip ``folder`` into ``target``; ``rename`` may change each member's name and content."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            name, data = path.relative_to(folder).as_posix(), path.read_bytes()
            if rename is not None:
                name, data = rename(name, data)
            archive.writestr(name, data)
    return target


@pytest.fixture
def v06_dir() -> Path:
    return V06_PACKAGE_DIR


@pytest.fixture
def v1_dir() -> Path:
    return V1_PACKAGE_DIR


@pytest.fixture
def v06_zip(tmp_path: Path) -> Path:
    return zip_folder(V06_PACKAGE_DIR, tmp_path / "silvertown_mini.agsi")


@pytest.fixture
def v06_dxf_zip(tmp_path: Path) -> Path:
    """Like the published ``*_dxf`` examples: JSON says WKT ``.txt`` but the package holds ``.dxf`` files."""

    def to_dxf(name: str, data: bytes) -> tuple[str, bytes]:
        if name.startswith("Profiles/"):
            return name.replace(".txt", ".dxf"), wkt_line_to_dxf(data.decode())
        return name, data

    return zip_folder(V06_PACKAGE_DIR, tmp_path / "silvertown_mini_dxf.agsi", to_dxf)
