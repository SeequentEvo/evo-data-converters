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

"""Loading AGSi packages: ``.agsi`` ZIP archives, extracted folders, or bare JSON files."""

import json
import posixpath
import zipfile
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import unquote, urlparse

from pydantic import ValidationError

import evo.logging

from .adapter import detect_version, is_legacy_version, normalise_document
from .errors import AGSIDataFileIOError, AGSIInvalidDataError
from .geometry_files import GeometryData, parse_geometry
from .models import AgsiDocument, AgsiGeometryFromFile, AgsiModel

logger = evo.logging.getLogger("data_converters")

INDEX_FILE_NAME = "index.json"
# Extensions tried, in order, when a fileURI does not exist in the package (some published
# examples reference ``.txt`` files but ship ``.dxf`` ones).
ALTERNATIVE_EXTENSIONS = (".txt", ".wkt", ".dxf", ".stl")


class AgsiPackage:
    """An AGSi file set: main JSON document plus supporting geometry files.

    Use :meth:`open` to load from any of:

    * a ``.agsi`` (or ``.zip``) archive containing ``index.json``, the main JSON file and the
      supporting files;
    * a folder holding the extracted contents of such an archive;
    * the main JSON file itself (supporting files are resolved relative to its folder), or the
      package's ``index.json``.

    The document is normalised to the AGSi 1.0.x layout (see :mod:`.adapter`); the version found
    in the source is kept in :attr:`source_version`.
    """

    def __init__(
        self,
        path: Path,
        root: Path,
        main_file: str,
        raw: dict[str, Any],
        index: Optional[dict[str, Any]] = None,
        is_zip: bool = False,
    ) -> None:
        self.path = path
        self.root = root
        self.main_file = main_file
        self.raw = raw
        self.index = index or {}
        self.is_zip = is_zip
        self.warnings: list[str] = []
        self._names_cache: Optional[list[str]] = None

        index_version = self.index.get("fileVersion")
        self.source_version = detect_version(raw, str(index_version) if index_version else None)
        normalised, self.notes = normalise_document(
            raw, self.source_version, title=self.index.get("name"), file_name=posixpath.basename(main_file)
        )
        try:
            self.document = AgsiDocument.model_validate(normalised)
        except ValidationError as e:
            raise AGSIInvalidDataError(f"{path}: invalid AGSi document: {e}") from e

    # --- construction ---------------------------------------------------------------------

    @classmethod
    def open(cls, path: Union[str, Path]) -> "AgsiPackage":
        """Open an AGSi package from a ZIP archive, folder, main JSON file or ``index.json``.

        :raise AGSIDataFileIOError: If the path cannot be read or has no AGSi main file.
        :raise AGSIInvalidDataError: If the main file is not a valid AGSi document.
        """
        path = Path(path)
        if not path.exists():
            raise AGSIDataFileIOError(f"AGSi path does not exist: {path}")
        if path.is_dir():
            return cls._open_directory(path)
        if zipfile.is_zipfile(path):
            return cls._open_zip(path)
        root = path.parent
        if path.name.lower() == INDEX_FILE_NAME:
            index = _read_index(path.read_bytes(), str(path))
            main_file = _main_file_from_index(index, str(path))
            return cls(path, root, main_file, _read_json(_read_file(root / main_file), main_file), index)
        index_path = root / INDEX_FILE_NAME
        sibling_index = _read_index(index_path.read_bytes(), str(index_path)) if index_path.is_file() else None
        return cls(path, root, path.name, _read_json(_read_file(path), str(path)), sibling_index)

    @classmethod
    def _open_directory(cls, path: Path) -> "AgsiPackage":
        index_path = path / INDEX_FILE_NAME
        if index_path.is_file():
            index = _read_index(index_path.read_bytes(), str(index_path))
            main_file = _main_file_from_index(index, str(index_path))
            return cls(path, path, main_file, _read_json(_read_file(path / main_file), main_file), index)
        for candidate in sorted(path.glob("*.json")):
            document = _try_read_agsi_json(candidate.read_bytes())
            if document is not None:
                return cls(path, path, candidate.name, document)
        raise AGSIDataFileIOError(f"No AGSi main JSON file found in folder: {path}")

    @classmethod
    def _open_zip(cls, path: Path) -> "AgsiPackage":
        try:
            with zipfile.ZipFile(path) as archive:
                names = [n for n in archive.namelist() if not n.endswith("/")]
                # Archives created by zipping a folder may wrap everything in that folder.
                index_names = [n for n in names if posixpath.basename(n).casefold() == INDEX_FILE_NAME]
                index_name = min(index_names, key=lambda n: n.count("/")) if index_names else None
                if index_name is not None:
                    index = _read_index(archive.read(index_name), f"{path}!{index_name}")
                    main_file = _main_file_from_index(index, f"{path}!{index_name}")
                    base = posixpath.dirname(index_name)
                    main_name = _find_name(names, posixpath.join(base, main_file) if base else main_file)
                    if main_name is None:
                        raise AGSIDataFileIOError(f"{path}: main file '{main_file}' listed in index.json is missing.")
                    return cls(path, Path(), main_name, _read_json(archive.read(main_name), main_name), index, True)
                for name in sorted(n for n in names if n.lower().endswith(".json") and "/" not in n):
                    document = _try_read_agsi_json(archive.read(name))
                    if document is not None:
                        return cls(path, Path(), name, document, is_zip=True)
        except (zipfile.BadZipFile, OSError) as e:
            raise AGSIDataFileIOError(f"Unable to read AGSi archive {path}: {e}") from e
        raise AGSIDataFileIOError(f"No AGSi main JSON file found in archive: {path}")

    # --- document access ------------------------------------------------------------------

    @property
    def is_legacy(self) -> bool:
        """True if the source document was pre-1.0 and has been normalised."""
        return is_legacy_version(self.source_version)

    @property
    def models(self) -> list[AgsiModel]:
        return self.document.agsi_model

    def list_files(self) -> list[str]:
        """Package-relative paths of all files in the package (POSIX separators)."""
        return list(self._names)

    @property
    def _names(self) -> list[str]:
        if self._names_cache is None:
            if self.is_zip:
                try:
                    with zipfile.ZipFile(self.path) as archive:
                        self._names_cache = [n for n in archive.namelist() if not n.endswith("/")]
                except (zipfile.BadZipFile, OSError) as e:
                    raise AGSIDataFileIOError(f"Unable to read AGSi archive {self.path}: {e}") from e
            else:
                files = (p for p in self.root.rglob("*") if p.is_file())
                self._names_cache = sorted(p.relative_to(self.root).as_posix() for p in files)
        return self._names_cache

    # --- supporting files -----------------------------------------------------------------

    def resolve_uri(self, uri: str) -> str:
        """Resolve an AGSi ``fileURI`` to a package-relative path.

        Relative URIs are resolved against the folder of the main JSON file (falling back to the
        package root). When there is no exact match the lookup is retried case-insensitively and
        then with alternative extensions (``.txt``/``.wkt``/``.dxf``/``.stl``); fallbacks are
        recorded in :attr:`warnings`.

        :raise AGSIDataFileIOError: If the URI is absolute/remote, escapes the package, or no
            matching file exists.
        """
        relative = _relative_path_from_uri(uri)
        base = posixpath.dirname(self.main_file)
        candidates = [posixpath.normpath(posixpath.join(base, relative))] if base else []
        candidates.append(posixpath.normpath(relative))
        candidates = [c for c in dict.fromkeys(candidates) if c != ".." and not c.startswith("../")]
        if not candidates:
            raise AGSIDataFileIOError(f"fileURI '{uri}' points outside the AGSi package.")

        names = set(self._names)
        for candidate in candidates:
            if candidate in names:
                return candidate
        for candidate in candidates:
            match = _find_name(self._names, candidate)
            if match is not None:
                self._warn(f"fileURI '{uri}' matched '{match}' case-insensitively.")
                return match
        for candidate in candidates:
            stem, _ = posixpath.splitext(candidate)
            for extension in ALTERNATIVE_EXTENSIONS:
                match = _find_name(self._names, stem + extension)
                if match is not None:
                    self._warn(f"fileURI '{uri}' not found; using '{match}' instead.")
                    return match
        raise AGSIDataFileIOError(f"fileURI '{uri}' not found in AGSi package {self.path}.")

    def read_bytes(self, uri: str) -> bytes:
        """Read a supporting file by its AGSi ``fileURI``."""
        name = self.resolve_uri(uri)
        if self.is_zip:
            try:
                with zipfile.ZipFile(self.path) as archive:
                    return archive.read(name)
            except (zipfile.BadZipFile, OSError, KeyError) as e:
                raise AGSIDataFileIOError(f"Unable to read '{name}' from {self.path}: {e}") from e
        return _read_file(self.root / name)

    def read_geometry(self, geometry: Union[AgsiGeometryFromFile, str]) -> GeometryData:
        """Read and parse a geometry file referenced by an ``agsiGeometryFromFile`` (or a URI)."""
        if isinstance(geometry, str):
            return parse_geometry(self.read_bytes(geometry), name=geometry)
        return parse_geometry(
            self.read_bytes(geometry.file_uri),
            file_format=geometry.file_format,
            file_part=geometry.file_part,
            name=geometry.file_uri,
        )

    def _warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
            logger.info(f"{self.path}: {message}")

    def __repr__(self) -> str:
        return f"AgsiPackage(path={str(self.path)!r}, main_file={self.main_file!r}, version={self.source_version!r})"


# --- helpers ---------------------------------------------------------------------------------


def _read_file(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as e:
        raise AGSIDataFileIOError(f"Unable to read {path}: {e}") from e


def _decode_json(data: bytes, name: str) -> Any:
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise AGSIInvalidDataError(f"{name}: invalid JSON: {e}") from e


def _read_json(data: bytes, name: str) -> dict[str, Any]:
    document = _decode_json(data, name)
    if not isinstance(document, dict) or not ({"agsiModel", "agsSchema", "agsFile"} & document.keys()):
        raise AGSIInvalidDataError(f"{name}: not an AGSi document (no 'agsiModel' or 'agsSchema').")
    return document


def _try_read_agsi_json(data: bytes) -> Optional[dict[str, Any]]:
    try:
        return _read_json(data, "")
    except AGSIInvalidDataError:
        return None


def _read_index(data: bytes, name: str) -> dict[str, Any]:
    index = _decode_json(data, name)
    entry = index.get("agsiIndex", index) if isinstance(index, dict) else None
    if not isinstance(entry, dict):
        raise AGSIInvalidDataError(f"{name}: unexpected index.json content.")
    return entry


def _main_file_from_index(index: dict[str, Any], name: str) -> str:
    file_path = index.get("filePath")
    if not isinstance(file_path, str) or not file_path:
        raise AGSIInvalidDataError(f"{name}: index.json has no 'filePath'.")
    return _relative_path_from_uri(file_path)


def _relative_path_from_uri(uri: str) -> str:
    parsed = urlparse(uri)
    # A single letter scheme is a Windows drive (e.g. "C:/..."), which is equally not allowed.
    if parsed.scheme or parsed.netloc or uri.startswith(("/", "\\")):
        raise AGSIDataFileIOError(f"fileURI '{uri}' is not a relative path within the AGSi package.")
    return unquote(parsed.path).replace("\\", "/")


def _find_name(names: list[str], wanted: str) -> Optional[str]:
    wanted_key = wanted.casefold()
    for name in names:
        if name.casefold() == wanted_key:
            return name
    return None
