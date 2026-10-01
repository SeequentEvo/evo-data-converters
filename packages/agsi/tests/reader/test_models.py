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

import json
from pathlib import Path
from typing import Any

from evo.data_converters.agsi.reader import (
    AgsiDocument,
    AgsiGeometryAreaFromLines,
    AgsiGeometryFromFile,
    AgsiGeometryLayer,
    AgsiGeometryPlane,
    AgsiGeometryVolFromSurfaces,
    AgsiModelElement,
)


def _profile(uri: str) -> dict[str, Any]:
    return {"geometryType": "Profile", "fileFormat": "WKT", "fileURI": uri}


def _surface(uri: str) -> dict[str, Any]:
    return {"geometryType": "Surface", "fileFormat": "WKT", "fileURI": uri}


def test_document_round_trip_preserves_unknown_fields(v1_dir: Path) -> None:
    raw = json.loads((v1_dir / "model.json").read_text(encoding="utf-8"))
    document = AgsiDocument.model_validate(raw)
    assert document.to_agsi() == raw
    element = document.agsi_model[0].agsi_model_element[0]
    assert element.extra_attributes == {"vendorExtension": {"source": "tests"}}


def test_v1_document_contents(v1_dir: Path) -> None:
    document = AgsiDocument.model_validate_json((v1_dir / "model.json").read_bytes())
    assert document.ags_schema is not None and document.ags_schema.version == "1.0.1"
    model = document.agsi_model[0]
    assert model.alignment_id == "NB"
    assert model.agsi_model_alignment[0].start_chainage == 100.0
    assert model.agsi_model_boundary is not None and model.agsi_model_boundary.bottom_elevation == -50

    alluvium, london_clay = model.agsi_model_element
    assert isinstance(alluvium.agsi_geometry, AgsiGeometryVolFromSurfaces)
    assert isinstance(alluvium.agsi_geometry.agsi_geometry_top, AgsiGeometryFromFile)
    assert isinstance(alluvium.agsi_geometry.agsi_geometry_bottom, AgsiGeometryPlane)
    assert alluvium.agsi_geometry.agsi_geometry_bottom.elevation == -5.0
    assert [role for role, _ in alluvium.geometry_files()] == ["top"]
    assert alluvium.agsi_data_parameter_value[0].value_numeric == 18.0
    assert alluvium.colour_rgb == "#a0522d"
    assert isinstance(london_clay.agsi_geometry, AgsiGeometryLayer)
    assert london_clay.geometry_files() == []
    assert model.elements_by_geometry("agsiGeometryLayer") == [london_clay]


def test_coordinate_system_lookup(v1_dir: Path) -> None:
    document = AgsiDocument.model_validate_json((v1_dir / "model.json").read_bytes())
    system = document.coordinate_system(document.agsi_model[0])
    assert system is not None and system.system_id == "CS-BNG" and system.global_xy_system == "EPSG:27700"
    default = document.coordinate_system()
    assert default is not None and default.system_id == "CS-LOCAL"
    assert AgsiDocument.model_validate({}).coordinate_system() is None


def test_geometry_object_selects_class() -> None:
    # AreaFromLines and VolFromSurfaces have the same attributes; geometryObject decides.
    geometry = {"agsiGeometryTop": _surface("a.txt"), "agsiGeometryBottom": _surface("b.txt")}
    area = AgsiModelElement.model_validate({"geometryObject": "agsiGeometryAreaFromLines", "agsiGeometry": geometry})
    volume = AgsiModelElement.model_validate(
        {"geometryObject": "agsiGeometryVolFromSurfaces", "agsiGeometry": geometry}
    )
    assert isinstance(area.agsi_geometry, AgsiGeometryAreaFromLines)
    assert isinstance(volume.agsi_geometry, AgsiGeometryVolFromSurfaces)
    assert area.geometry_object_name == "agsiGeometryAreaFromLines"
    assert [(role, g.file_uri) for role, g in area.geometry_files()] == [("top", "a.txt"), ("bottom", "b.txt")]


def test_geometry_object_inferred_when_missing() -> None:
    lines = AgsiModelElement.model_validate({"agsiGeometry": {"agsiGeometryTop": _profile("a.txt")}})
    surfaces = AgsiModelElement.model_validate({"agsiGeometry": {"agsiGeometryTop": _surface("a.txt")}})
    from_file = AgsiModelElement.model_validate({"agsiGeometry": _surface("a.txt")})
    plane = AgsiModelElement.model_validate({"agsiGeometry": {"elevation": 3}})
    layer = AgsiModelElement.model_validate({"agsiGeometry": {"topElevation": 3, "bottomElevation": 1}})
    assert isinstance(lines.agsi_geometry, AgsiGeometryAreaFromLines)
    assert isinstance(surfaces.agsi_geometry, AgsiGeometryVolFromSurfaces)
    assert isinstance(from_file.agsi_geometry, AgsiGeometryFromFile)
    assert [role for role, _ in from_file.geometry_files()] == ["geometry"]
    assert isinstance(plane.agsi_geometry, AgsiGeometryPlane)
    assert isinstance(layer.agsi_geometry, AgsiGeometryLayer)


def test_to_agsi_uses_agsi_attribute_names() -> None:
    element = AgsiModelElement.model_validate(
        {
            "elementID": "E1",
            "geometryObject": "agsiGeometryAreaFromLines",
            "agsiGeometry": {"agsiGeometryTop": {**_profile("t.txt"), "filePart": "TOP"}},
            "agsiGeometryAreaLimit": {"fileURI": "limit.txt"},
        }
    )
    dumped = element.to_agsi()
    assert dumped["elementID"] == "E1"
    assert dumped["agsiGeometry"]["agsiGeometryTop"]["fileURI"] == "t.txt"
    assert dumped["agsiGeometry"]["agsiGeometryTop"]["filePart"] == "TOP"
    assert dumped["agsiGeometryAreaLimit"] == {"fileURI": "limit.txt"}
    assert [role for role, _ in element.geometry_files()] == ["top", "area_limit"]
