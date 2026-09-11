from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET
import zipfile

from evo.data_converters.kml.importer.exceptions import InvalidKMLError

KmlSourceFormat = Literal["kml", "kmz"]


@dataclass(slots=True)
class KmlOrKmzSource:
    source_path: Path
    source_format: KmlSourceFormat
    root: ET.Element


class KmlOrKmzReader:
    """
    Low-level reader for KML and KMZ sources.

    Semantic extraction is handled by KmlDocumentParser,
    which consumes the normalized root returned by this reader.

    Responsibilities:
    - validate the source path and extension
    - open '.kml' directly or extract the main '.kml' from a '.kmz'
    - parse the XML root

    Non-responsibilities:
    - semantic parsing of placemarks, geometries, styles, or ExtendedData
    - Evo object construction

    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> KmlOrKmzSource:
        """
        Read a `.kml` or `.kmz` file and return normalized source metadata.

        :raise InvalidKMLError:
            - If the file extension is not `.kml` or `.kmz`.
            - If a KMZ contains no `.kml` member.
            - If XML parsing fails or the XML root is not `<kml>`.
            - If file I/O or archive decoding fails.
        """
        source_format = self._get_source_format()

        try:
            if source_format == "kml":
                return self._read_kml()
            return self._read_kmz()
        except (OSError, UnicodeDecodeError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise InvalidKMLError(f"Could not read KML/KMZ file '{self.path}': {exc}") from exc

    def _get_source_format(self) -> KmlSourceFormat:
        suffix = self.path.suffix.lower()
        if suffix == ".kml":
            return "kml"
        if suffix == ".kmz":
            return "kmz"
        raise InvalidKMLError(f"Expected a .kml or .kmz file, got: {self.path.suffix}")

    def _read_kml(self) -> KmlOrKmzSource:
        # Read bytes so XML encoding declarations are handled by the XML parser.
        raw_kml_bytes = self.path.read_bytes()
        root = ET.fromstring(raw_kml_bytes)
        self._validate_root(root)

        return KmlOrKmzSource(
            source_path=self.path,
            source_format="kml",
            root=root,
        )

    def _read_kmz(self) -> KmlOrKmzSource:
        with zipfile.ZipFile(self.path) as archive:
            archive_members = archive.namelist()
            kml_members = [name for name in archive_members if name.lower().endswith(".kml")]
            if not kml_members:
                raise InvalidKMLError("KMZ archive does not contain any .kml file.")

            main_kml_name = self._select_main_kml_name(kml_members)
            with archive.open(main_kml_name) as kml_file:
                # Keep bytes until parsing so the declared XML encoding is respected.
                raw_kml_bytes = kml_file.read()

        root = ET.fromstring(raw_kml_bytes)
        self._validate_root(root)

        return KmlOrKmzSource(
            source_path=self.path,
            source_format="kmz",
            root=root,
        )

    def _select_main_kml_name(self, kml_members: list[str]) -> str:
        for name in kml_members:
            if Path(name).name.lower() == "doc.kml":
                return name
        return kml_members[0]

    def _validate_root(self, root: ET.Element) -> None:
        if self._local_name(root.tag) != "kml":
            raise InvalidKMLError("The input file is XML, but its root element is not <kml>.")

    def _local_name(self, tag: str) -> str:
        return tag.split("}", maxsplit=1)[-1]
