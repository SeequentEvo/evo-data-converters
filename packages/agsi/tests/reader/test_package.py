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
import zipfile
from pathlib import Path

import numpy as np
import pytest
from conftest import zip_folder

from evo.data_converters.agsi.reader import (
    AGSIDataFileIOError,
    AGSIInvalidDataError,
    AgsiGeometryAreaFromLines,
    AgsiPackage,
    GeometryFileFormat,
)


def _write_zip(path: Path, members: dict[str, object]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content if isinstance(content, (str, bytes)) else json.dumps(content))
    return path


def _assert_mini_v06(package: AgsiPackage) -> None:
    assert package.source_version == "0.6"
    assert package.is_legacy
    assert package.document.ags_file is not None and package.document.ags_file.title == "Silvertown mini"
    (model,) = package.models
    surficial, alluvium = model.agsi_model_element
    assert all(isinstance(e.agsi_geometry, AgsiGeometryAreaFromLines) for e in (surficial, alluvium))
    assert [role for role, _ in surficial.geometry_files()] == ["top", "bottom"]
    assert [role for role, _ in alluvium.geometry_files()] == ["top"]

    lines = {
        (e.element_id, role): package.read_geometry(g).single_line()
        for e in (surficial, alluvium)
        for role, g in e.geometry_files()
    }
    for line in lines.values():
        assert line.shape == (6, 2)
    np.testing.assert_allclose(lines[("Profile Surficial Alignment NB", "top")][0], [0.0, 4.61849])
    # Base of one unit is the top of the next.
    np.testing.assert_array_equal(
        lines[("Profile Surficial Alignment NB", "bottom")], lines[("Profile Alluvium Alignment NB", "top")]
    )


class TestOpen:
    def test_zip(self, v06_zip: Path) -> None:
        package = AgsiPackage.open(v06_zip)
        assert package.is_zip and package.main_file == "Silvertown_mini.json"
        _assert_mini_v06(package)
        assert package.warnings == []
        assert sorted(package.list_files()) == [
            "Profiles/NB-01-Surficial-Base.txt",
            "Profiles/NB-01-Surficial-Top.txt",
            "Profiles/NB-02-Alluvium-Top.txt",
            "Silvertown_mini.json",
            "index.json",
        ]

    def test_zip_with_any_extension(self, v06_dir: Path, tmp_path: Path) -> None:
        _assert_mini_v06(AgsiPackage.open(zip_folder(v06_dir, tmp_path / "package.zip")))

    @pytest.mark.parametrize("relative", ["", "index.json", "Silvertown_mini.json"])
    def test_folder_index_or_main_json(self, v06_dir: Path, relative: str) -> None:
        package = AgsiPackage.open(v06_dir / relative if relative else v06_dir)
        assert not package.is_zip
        _assert_mini_v06(package)

    def test_v1_bare_json(self, v1_dir: Path) -> None:
        package = AgsiPackage.open(str(v1_dir / "model.json"))
        assert package.source_version == "1.0.1" and not package.is_legacy
        assert package.notes == []
        assert package.index == {}
        model = package.models[0]
        surface = package.read_geometry(model.agsi_model_element[0].geometry_files()[0][1])
        assert surface.srid == 27700
        assert surface.to_triangle_mesh().triangles.shape == (2, 3)
        alignment = model.agsi_model_alignment[0].agsi_geometry
        assert alignment is not None
        assert package.read_geometry(alignment).single_line().shape == (3, 2)

    def test_v1_folder_and_zip_without_index(self, v1_dir: Path, tmp_path: Path) -> None:
        for path in (v1_dir, zip_folder(v1_dir, tmp_path / "v1.agsi")):
            package = AgsiPackage.open(path)
            assert package.main_file == "model.json"
            assert package.read_bytes("Surfaces/alluvium-top.wkt").startswith(b"SRID=27700;")

    def test_index_in_subfolder(self, v06_dir: Path, tmp_path: Path) -> None:
        path = zip_folder(v06_dir, tmp_path / "nested.agsi", lambda name, data: (f"package/{name}", data))
        package = AgsiPackage.open(path)
        assert package.main_file == "package/Silvertown_mini.json"
        _assert_mini_v06(package)


class TestFileResolution:
    def test_dxf_package_declaring_wkt_txt(self, v06_dxf_zip: Path) -> None:
        package = AgsiPackage.open(v06_dxf_zip)
        _assert_mini_v06(package)
        assert len(package.warnings) == 3
        assert "using 'Profiles/NB-01-Surficial-Top.dxf' instead" in package.warnings[0]
        top = package.models[0].agsi_model_element[0].geometry_files()[0][1]
        assert package.read_geometry(top).source_format is GeometryFileFormat.DXF

    def test_case_insensitive_match(self, v06_dir: Path, tmp_path: Path) -> None:
        path = zip_folder(
            v06_dir, tmp_path / "case.agsi", lambda name, data: (name.replace("Profiles/", "profiles/"), data)
        )
        package = AgsiPackage.open(path)
        _assert_mini_v06(package)
        assert all("case-insensitively" in w for w in package.warnings)

    def test_percent_encoded_and_dot_segments(self, tmp_path: Path) -> None:
        path = _write_zip(
            tmp_path / "encoded.agsi",
            {
                "index.json": {"agsiIndex": {"filePath": "Model/main.json", "fileVersion": "1.0.1"}},
                "Model/main.json": {"agsSchema": {"name": "AGSi", "version": "1.0.1"}, "agsiModel": []},
                "Model/Profiles/My Profile.txt": "LINESTRING (0 0, 1 1)",
                "Shared/line.txt": "LINESTRING (0 0, 2 2)",
            },
        )
        package = AgsiPackage.open(path)
        assert package.resolve_uri("Profiles/My%20Profile.txt") == "Model/Profiles/My Profile.txt"
        assert package.resolve_uri("./Profiles/My%20Profile.txt") == "Model/Profiles/My Profile.txt"
        assert package.resolve_uri("../Shared/line.txt") == "Shared/line.txt"
        assert package.resolve_uri("Shared/line.txt") == "Shared/line.txt"  # package-root fallback
        assert package.read_geometry("Shared/line.txt").lines[0][-1, 0] == 2

    @pytest.mark.parametrize(
        "uri",
        [
            "../outside.txt",
            "Profiles/../../outside.txt",
            "http://example.com/a.txt",
            "/abs.txt",
            "C:/a.txt",
            "file:///a.txt",
        ],
    )
    def test_rejects_uris_outside_package(self, v06_zip: Path, uri: str) -> None:
        with pytest.raises(AGSIDataFileIOError):
            AgsiPackage.open(v06_zip).resolve_uri(uri)

    def test_missing_file(self, v06_dir: Path) -> None:
        package = AgsiPackage.open(v06_dir)
        with pytest.raises(AGSIDataFileIOError, match="not found"):
            package.read_bytes("Profiles/does-not-exist.txt")


class TestErrors:
    def test_path_does_not_exist(self, tmp_path: Path) -> None:
        with pytest.raises(AGSIDataFileIOError, match="does not exist"):
            AgsiPackage.open(tmp_path / "missing.agsi")

    def test_zip_without_agsi_json(self, tmp_path: Path) -> None:
        with pytest.raises(AGSIDataFileIOError, match="No AGSi main JSON"):
            AgsiPackage.open(_write_zip(tmp_path / "x.agsi", {"other.json": {"a": 1}, "readme.txt": "hi"}))

    def test_folder_without_agsi_json(self, tmp_path: Path) -> None:
        (tmp_path / "other.json").write_text("{}")
        with pytest.raises(AGSIDataFileIOError, match="No AGSi main JSON"):
            AgsiPackage.open(tmp_path)

    def test_index_points_to_missing_file(self, tmp_path: Path) -> None:
        path = _write_zip(tmp_path / "x.agsi", {"index.json": {"agsiIndex": {"filePath": "main.json"}}})
        with pytest.raises(AGSIDataFileIOError, match="main.json"):
            AgsiPackage.open(path)

    def test_index_without_file_path(self, tmp_path: Path) -> None:
        with pytest.raises(AGSIInvalidDataError, match="filePath"):
            AgsiPackage.open(_write_zip(tmp_path / "x.agsi", {"index.json": {"agsiIndex": {}}}))

    def test_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "main.json"
        path.write_text("{not json")
        with pytest.raises(AGSIInvalidDataError, match="invalid JSON"):
            AgsiPackage.open(path)

    def test_not_agsi_json(self, tmp_path: Path) -> None:
        path = tmp_path / "main.json"
        path.write_text('{"something": "else"}')
        with pytest.raises(AGSIInvalidDataError, match="not an AGSi document"):
            AgsiPackage.open(path)

    def test_invalid_structure(self, tmp_path: Path) -> None:
        path = tmp_path / "main.json"
        path.write_text(json.dumps({"agsSchema": {"version": "1.0.1"}, "agsiModel": "nope"}))
        with pytest.raises(AGSIInvalidDataError, match="invalid AGSi document"):
            AgsiPackage.open(path)

    def test_utf8_bom(self, tmp_path: Path) -> None:
        path = tmp_path / "main.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"agsiModel": [{"modelName": "BOM"}]}).encode())
        assert AgsiPackage.open(path).models[0].model_name == "BOM"
