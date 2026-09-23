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
import scripts.render_converter_capabilities as render_module
from scripts.converter_capabilities_utils import (
    REPO_ROOT,
    build_registry,
    discover_converter_packages,
    normalize_all,
    validate_all,
    validate_registry,
    write_capability_file,
)
from scripts.manage_converter_capabilities import cmd_add, cmd_validate

VALID_ENTRY = {
    "id": "widget",
    "name": "Widget",
    "package": "evo-data-converters-widget",
    "status": "implemented",
    "extensions": [".widget"],
    "platform": ["Cross-platform (Python)"],
    "import": {"supported": True, "source_types": ["Widget"], "produces_evo_objects": ["Pointset"]},
    "export": {"supported": False, "supports_evo_objects": []},
    "limitations": ["None."],
}


def _make_package(packages_dir: Path, name: str) -> Path:
    package_dir = packages_dir / name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    return package_dir


class TestDiscovery:
    def test_finds_only_directories_with_pyproject(self, tmp_path: Path) -> None:
        _make_package(tmp_path, "alpha")
        _make_package(tmp_path, "beta")
        (tmp_path / "not_a_package").mkdir()
        (tmp_path / "common").mkdir()
        (tmp_path / "common" / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

        assert discover_converter_packages(tmp_path) == ["alpha", "beta"]

    def test_missing_packages_dir_returns_empty(self, tmp_path: Path) -> None:
        assert discover_converter_packages(tmp_path / "does-not-exist") == []


class TestBuildRegistry:
    def test_reports_missing_capability_file(self, tmp_path: Path) -> None:
        _make_package(tmp_path, "alpha")

        registry, errors = build_registry(tmp_path)

        assert registry["converters"] == []
        assert any("packages/alpha is missing converter-capabilities.json" in err for err in errors)

    def test_reports_malformed_json(self, tmp_path: Path) -> None:
        package_dir = _make_package(tmp_path, "alpha")
        (package_dir / "converter-capabilities.json").write_text("{not valid json", encoding="utf-8")

        registry, errors = build_registry(tmp_path)

        assert registry["converters"] == []
        assert any("invalid JSON" in err for err in errors)

    def test_reports_id_package_mismatch(self, tmp_path: Path) -> None:
        package_dir = _make_package(tmp_path, "alpha")
        entry = {**VALID_ENTRY, "id": "not-alpha", "package": "evo-data-converters-not-alpha"}
        (package_dir / "converter-capabilities.json").write_text(json.dumps(entry), encoding="utf-8")

        registry, errors = build_registry(tmp_path)

        assert len(registry["converters"]) == 1
        assert any("does not match package directory 'packages/alpha'" in err for err in errors)

    def test_aggregates_valid_entries(self, tmp_path: Path) -> None:
        package_dir = _make_package(tmp_path, "widget")
        (package_dir / "converter-capabilities.json").write_text(json.dumps(VALID_ENTRY), encoding="utf-8")

        registry, errors = build_registry(tmp_path)

        assert errors == []
        assert [c["id"] for c in registry["converters"]] == ["widget"]

    def test_excludes_common(self, tmp_path: Path) -> None:
        _make_package(tmp_path, "common")

        registry, errors = build_registry(tmp_path)

        assert registry["converters"] == []
        assert errors == []


class TestValidateRegistry:
    def test_detects_duplicate_ids(self) -> None:
        registry = {
            "schema_version": "1.0",
            "converters": [VALID_ENTRY, {**VALID_ENTRY}],
        }

        errors = validate_registry(registry)

        assert any("duplicate id" in err for err in errors)

    def test_detects_missing_required_field(self) -> None:
        entry = {k: v for k, v in VALID_ENTRY.items() if k != "limitations"}
        registry = {"schema_version": "1.0", "converters": [entry]}

        errors = validate_registry(registry)

        assert any("missing required field: limitations" in err for err in errors)

    def test_detects_bad_nested_import_field(self) -> None:
        entry = {**VALID_ENTRY, "import": {"supported": True, "source_types": "not-a-list", "produces_evo_objects": []}}
        registry = {"schema_version": "1.0", "converters": [entry]}

        errors = validate_registry(registry)

        assert any("import.source_types must be a list of strings" in err for err in errors)

    def test_valid_entry_has_no_errors(self) -> None:
        registry = {"schema_version": "1.0", "converters": [VALID_ENTRY]}

        assert validate_registry(registry) == []


class TestValidateAll:
    def test_repo_packages_are_all_valid(self) -> None:
        # Exercise the real repository state (no packages_dir override) as an integration check.
        errors = validate_all()
        assert errors == []

    def test_repo_matches_expected_converter_ids(self) -> None:
        expected = {"duf", "gocad", "image", "obj", "omf", "resqml", "shp", "ubc", "vtk", "xyz"}
        assert set(discover_converter_packages()) == expected
        assert "common" not in discover_converter_packages()


class TestWriteAndNormalize:
    def test_write_capability_file_round_trips(self, tmp_path: Path) -> None:
        _make_package(tmp_path, "widget")

        write_capability_file("widget", VALID_ENTRY, tmp_path)

        written = json.loads((tmp_path / "widget" / "converter-capabilities.json").read_text(encoding="utf-8"))
        assert written["$schema"] == "../../converter-capabilities.schema.json"
        assert written["id"] == "widget"
        # Keys after $schema follow the canonical schema order.
        assert list(written.keys())[1:] == list(VALID_ENTRY.keys())

    def test_normalize_all_rewrites_existing_files(self, tmp_path: Path) -> None:
        package_dir = _make_package(tmp_path, "widget")
        # Write with keys in a scrambled order plus an existing $schema field.
        scrambled = {"limitations": VALID_ENTRY["limitations"], "$schema": "x", "id": "widget", **VALID_ENTRY}
        (package_dir / "converter-capabilities.json").write_text(json.dumps(scrambled), encoding="utf-8")

        written = normalize_all(tmp_path)

        assert len(written) == 1
        data = json.loads(written[0].read_text(encoding="utf-8"))
        assert list(data.keys())[1:] == list(VALID_ENTRY.keys())


class TestCmdAdd:
    def test_fails_when_package_dir_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setattr("scripts.manage_converter_capabilities.PACKAGES_DIR", tmp_path)

        class Args:
            id = "ghost"
            name = "Ghost"
            status = "planned"

        result = cmd_add(Args())

        assert result == 1
        assert "does not exist" in capsys.readouterr().out

    def test_fails_when_capability_file_already_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        package_dir = _make_package(tmp_path, "widget")
        (package_dir / "converter-capabilities.json").write_text(json.dumps(VALID_ENTRY), encoding="utf-8")
        monkeypatch.setattr("scripts.manage_converter_capabilities.PACKAGES_DIR", tmp_path)
        monkeypatch.setattr("scripts.converter_capabilities_utils.PACKAGES_DIR", tmp_path)

        class Args:
            id = "widget"
            name = "Widget"
            status = "planned"

        result = cmd_add(Args())

        assert result == 1
        assert "already exists" in capsys.readouterr().out

    def test_writes_stub_and_validates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        _make_package(tmp_path, "widget")
        monkeypatch.setattr("scripts.manage_converter_capabilities.PACKAGES_DIR", tmp_path)
        monkeypatch.setattr("scripts.converter_capabilities_utils.PACKAGES_DIR", tmp_path)

        class Args:
            id = "widget"
            name = "Widget"
            status = "planned"

        result = cmd_add(Args())

        capability_path = tmp_path / "widget" / "converter-capabilities.json"
        assert result == 0
        assert capability_path.is_file()
        data = json.loads(capability_path.read_text(encoding="utf-8"))
        assert data["id"] == "widget"
        assert data["status"] == "planned"


def test_root_registry_file_removed() -> None:
    assert not (REPO_ROOT / "converter-capabilities.json").exists()


def test_cmd_validate_passes_for_real_repo(capsys: pytest.CaptureFixture) -> None:
    assert cmd_validate(None) == 0
    assert "valid" in capsys.readouterr().out


class TestRender:
    def test_render_markdown_lists_each_converter(self) -> None:
        registry = {"schema_version": "1.0", "converters": [VALID_ENTRY]}

        markdown = render_module._render_markdown(registry)

        assert "# Converter Capability Matrix" in markdown
        assert "| Widget | implemented | Yes | No |" in markdown
        assert "### Widget" in markdown

    def test_render_json_strips_schema_hint_and_preserves_key_order(self) -> None:
        entry_with_schema = {"$schema": "../../converter-capabilities.schema.json", **VALID_ENTRY}
        registry = {"schema_version": "1.0", "converters": [entry_with_schema]}

        document = json.loads(render_module._render_json(registry))

        assert document["$schema"] == "./converter-capabilities.schema.json"
        assert document["schema_version"] == "1.0"
        assert len(document["converters"]) == 1
        rendered_entry = document["converters"][0]
        assert "$schema" not in rendered_entry
        assert list(rendered_entry.keys()) == list(VALID_ENTRY.keys())

    def test_render_from_real_repo_matches_committed_docs(self) -> None:
        # Guards against docs/converter-capabilities.{md,json} drifting from packages/*/converter-capabilities.json.
        registry, errors = build_registry()
        assert errors == []
        assert validate_registry(registry) == []

        markdown = render_module._render_markdown(registry)
        assert markdown == (REPO_ROOT / "docs" / "converter-capabilities.md").read_text(encoding="utf-8")

        rendered_json = json.loads(render_module._render_json(registry))
        committed_json = json.loads((REPO_ROOT / "docs" / "converter-capabilities.json").read_text(encoding="utf-8"))
        assert rendered_json == committed_json
