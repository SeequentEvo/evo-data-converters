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

import pytest

from evo.data_converters.agsi.reader import CURRENT_VERSION, AgsiDocument, detect_version, normalise_document
from evo.data_converters.agsi.reader.adapter import is_legacy_version


@pytest.mark.parametrize(
    "document, index_version, expected",
    [
        ({"agsSchema": {"name": "AGSi", "version": "1.0.1"}}, "0.6", "1.0.1"),
        ({"agsiModel": []}, "0.6", "0.6"),
        ({"agsiModel": []}, None, "0.6"),
        ({"agsiSchema": {"version": "0.5"}}, None, "0.5"),
    ],
)
def test_detect_version(document: dict, index_version: str, expected: str) -> None:
    assert detect_version(document, index_version) == expected


def test_is_legacy_version() -> None:
    assert is_legacy_version("0.6")
    assert not is_legacy_version("1.0.1")
    assert not is_legacy_version("unknown")


def test_v1_document_is_unchanged(v1_dir: Path) -> None:
    raw = json.loads((v1_dir / "model.json").read_text(encoding="utf-8"))
    normalised, notes = normalise_document(raw, "1.0.1")
    assert normalised == raw and normalised is not raw
    assert notes == []


def test_newer_major_version_noted() -> None:
    _, notes = normalise_document({"agsSchema": {"version": "2.0.0"}}, "2.0.0")
    assert "newer" in notes[0]


def test_v06_document_normalised(v06_dir: Path) -> None:
    raw = json.loads((v06_dir / "Silvertown_mini.json").read_text(encoding="utf-8"))
    normalised, notes = normalise_document(raw, "0.6", title="Silvertown mini", file_name="Silvertown_mini.json")
    assert list(normalised)[:3] == ["agsSchema", "agsFile", "agsProject"]
    assert normalised["agsSchema"] == {"name": "AGSi", "version": CURRENT_VERSION}
    assert normalised["agsFile"]["title"] == "Silvertown mini"
    assert normalised["agsFile"]["fileURI"] == "Silvertown_mini.json"
    assert "0.6" in normalised["agsFile"]["remarks"]
    assert normalised["agsProject"]["projectName"] == "Silvertown mini"
    assert normalised["agsiModel"] == raw["agsiModel"]
    assert "agsSchema" not in raw  # input not mutated
    assert len(notes) == 3
    AgsiDocument.model_validate(normalised)


def test_v06_legacy_shapes() -> None:
    raw = {
        "agsiFile": {"title": "Old", "producedBy": "Someone"},
        "agsiProject": {"projectName": "P", "agsiProjectCoordinateSystem": [{"systemID": "CS1"}]},
        "agsiModel": {
            "modelName": "M",
            "agsiModelElement": {
                "elementID": "E1",
                "agsiGeometry": {
                    "geometryObject": "agsiGeometryVolFromSurfaces",
                    "agsiGeometryTop": {"geometryType": "Profile", "fileURI": "a.txt"},
                },
            },
        },
    }
    normalised, _ = normalise_document(raw, "0.6")
    assert normalised["agsFile"] == {"title": "Old", "producedBy": "Someone"}
    assert normalised["agsProject"]["agsProjectCoordinateSystem"] == [{"systemID": "CS1"}]
    element = normalised["agsiModel"][0]["agsiModelElement"][0]
    assert element["geometryObject"] == "agsiGeometryVolFromSurfaces"
    assert "geometryObject" not in element["agsiGeometry"]

    document = AgsiDocument.model_validate(normalised)
    assert document.coordinate_system() is not None
    # The explicit geometryObject wins over inference from geometryType "Profile".
    assert document.agsi_model[0].agsi_model_element[0].geometry_object_name == "agsiGeometryVolFromSurfaces"


def test_title_falls_back_to_model_name() -> None:
    normalised, _ = normalise_document({"agsiModel": [{"modelName": "Model A"}]}, "0.6")
    assert normalised["agsFile"]["title"] == "Model A"
    assert "fileURI" not in normalised["agsFile"]
