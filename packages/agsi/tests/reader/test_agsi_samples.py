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

"""Integration tests against the published AGSi Silvertown example packages.

The examples (up to ~80 MB) are not committed. Download the ``Silvertown2D_*`` and
``Silvertown3D_*`` ``.agsi`` files from the AGSi guidance pages and point ``AGSI_SAMPLE_DIR``
at the folder holding them to run these tests.
"""

import os
from pathlib import Path

import pytest

from evo.data_converters.agsi.reader import AgsiGeometryFromFile, AgsiPackage

SAMPLE_DIR = os.environ.get("AGSI_SAMPLE_DIR")
SAMPLE_NAMES = [
    "Silvertown2D_wkt_1",
    "Silvertown2D_wkt_3",
    "Silvertown2D_dxf_1",
    "Silvertown2D_dxf_3",
    "Silvertown3D_wkt",
    "Silvertown3D_dxf",
    "Silvertown3D_stl",
]

pytestmark = pytest.mark.skipif(not SAMPLE_DIR, reason="Set AGSI_SAMPLE_DIR to run the AGSi sample tests")

AREA = "agsiGeometryAreaFromLines"
VOLUME = "agsiGeometryVolFromSurfaces"


def _file_refs(package: AgsiPackage, geometry_object: str) -> list[AgsiGeometryFromFile]:
    elements = package.models[0].elements_by_geometry(geometry_object)
    return [
        geometry for element in elements for role, geometry in element.geometry_files() if role in ("top", "bottom")
    ]


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_sample_package(name: str) -> None:
    path = Path(str(SAMPLE_DIR)) / f"{name}.agsi"
    if not path.is_file():
        pytest.skip(f"{path} not found")
    package = AgsiPackage.open(path)
    assert package.source_version == "0.6" and package.is_legacy
    assert len(package.models) == 1
    elements = package.models[0].agsi_model_element

    profiles = _file_refs(package, AREA)
    if name.startswith("Silvertown2D"):
        assert len(elements) == 11
        assert len(profiles) == 21
        expected_dimension = 2
    else:
        assert len(elements) == 33
        surfaces = _file_refs(package, VOLUME)
        assert len(package.models[0].elements_by_geometry(VOLUME)) == 11
        assert len(package.models[0].elements_by_geometry(AREA)) == 22
        assert len(surfaces) == 21
        assert len(profiles) == 42
        expected_dimension = 3

        mesh = package.read_geometry(surfaces[0]).to_triangle_mesh()
        assert len(mesh.triangles) > 0 and mesh.vertices.shape[1] == 3

        boundary = package.models[0].agsi_model_boundary
        assert boundary is not None and boundary.agsi_geometry_boundary_xy is not None
        assert package.read_geometry(boundary.agsi_geometry_boundary_xy).dimension == 3

    for profile in profiles:
        line = package.read_geometry(profile).single_line()
        assert line.shape[0] >= 2 and line.shape[1] == expected_dimension
