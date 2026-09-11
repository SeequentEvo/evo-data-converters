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

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from evo.data_converters.kml.importer.exceptions import InvalidKMLError
from evo.data_converters.kml.importer.implementation.kml_or_kmz_reader import KmlOrKmzReader
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components.crs import Crs_V1_0_1


_logger = logging.getLogger(__name__)


KmlCoordinate = tuple[float, float, float]
KmlGeometryKind = Literal["point", "line"]

_KML_NS = "http://www.opengis.net/kml/2.2"      # standard KML namespace
_NS = {"kml": _KML_NS}                          # namespace map passed to ElementTree XPath calls

# store the KML <Point> geometry for a placemark.
@dataclass(slots=True)
class KmlPointGeometry:
    kind: Literal["point"] = "point"
    coordinates: KmlCoordinate = (0.0, 0.0, 0.0)

# store the KML <LineString> geometry for a placemark.
@dataclass(slots=True)
class KmlLineGeometry:
    kind: Literal["line"] = "line"
    coordinates: list[KmlCoordinate] = field(default_factory=list)

KmlGeometry = KmlPointGeometry | KmlLineGeometry

@dataclass(slots=True)
class KmlPlacemark:
    name: str | None
    description: str | None
    folder_path: tuple[str, ...]
    geometries: list[KmlGeometry]

@dataclass(slots=True)
class KmlDocument:
    source_path: Path
    source_format: Literal["kml", "kmz"]
    document_name: str | None
    document_description: str | None
    folder_names: list[tuple[str, ...]]
    placemarks: list[KmlPlacemark]

class KmlDocumentParser:
    """
    Parse KML or KMZ into an intermediate representation for later Evo mapping (in kml_evo_object_builder).

    This parser performs semantic parsing of KML features. It extracts
    Document/Folder/Placemark structure, Point and LineString geometries,
    and basic metadata, then returns intermediate KmlDocument/KmlPlacemark models.

    This parser does not construct Evo objects yet.
    """

    def __init__(
        self,
        path: str,
        data_client: ObjectDataClient,
        crs: Crs_V1_0_1,
        tags: dict[str, str] | None = None,
    ):
        self.path = Path(path)
        self.data_client = data_client
        self.crs = crs
        self.tags = tags or {}

    def parse(self) -> KmlDocument:
        return self.parse_kml()

    def parse_kml(self) -> KmlDocument:
        """Open, validate, and parse a `.kml` or `.kmz` file into an intermediate document model."""

        source = KmlOrKmzReader(self.path).read()
        root = source.root

        document_element = self._find_document_or_folder(root)
        document_name = self._find_text(document_element, "kml:name") if document_element is not None else None
        document_description = (
            self._find_text(document_element, "kml:description") if document_element is not None else None
        )

        folder_names: list[tuple[str, ...]] = []
        placemarks: list[KmlPlacemark] = []

        self._walk_features(root, tuple(), folder_names, placemarks)

        return KmlDocument(
            source_path=source.source_path,
            source_format=source.source_format,
            document_name=document_name,
            document_description=document_description,
            folder_names=folder_names,
            placemarks=placemarks,
        )

    # KML features are hierarchical (Document → Folder → nested Folder → Placemark)
    # Ensure that placemarks are parsed no matter how deeply nested they are, with the right context attached.
    # Initially folder_path = empty. When _walk_features sees a Folder, it builds next_path = folder_path + (folder_name,)
    def _walk_features(
        self,
        element: ET.Element,
        folder_path: tuple[str, ...],
        folder_names: list[tuple[str, ...]],
        placemarks: list[KmlPlacemark],
    ) -> None:
        """Traverse KML Document/Folder/Placemark nodes and preserve folder context for placemarks."""
        for child in list(element):
            local_name = self._local_name(child.tag)
            if local_name == "Folder":
                folder_name = self._find_text(child, "kml:name") or ""
                next_path = folder_path + ((folder_name,) if folder_name else tuple())
                folder_names.append(next_path)
                self._walk_features(child, next_path, folder_names, placemarks)
            elif local_name == "Document":
                self._walk_features(child, folder_path, folder_names, placemarks)
            elif local_name == "Placemark":
                placemark = self._parse_placemark(child, folder_path)
                if placemark is not None:
                    placemarks.append(placemark)

     def _parse_placemark(
        self,
        placemark_element: ET.Element,
        folder_path: tuple[str, ...],
    ) -> KmlPlacemark | None:
        """Convert one raw Placemark element into a normalized placemark model, skipping unsupported geometries."""
        geometries = self._parse_geometries(placemark_element)
        if not geometries:
            placemark_name = self._find_text(placemark_element, "kml:name") or "<unnamed>"
            _logger.warning("Skipping placemark '%s' because it contains no supported geometry.", placemark_name)
            return None

        return KmlPlacemark(
            name=self._find_text(placemark_element, "kml:name"),
            description=self._find_text(placemark_element, "kml:description"),
            folder_path=folder_path,
            geometries=geometries,
        )

    def _parse_geometries(self, placemark_element: ET.Element) -> list[KmlGeometry]:
        """Extract supported point and line geometries from a Placemark element."""
        geometries: list[KmlGeometry] = []

        # Point
        for point_element in placemark_element.findall(".//kml:Point", _NS):
            coordinates = self._parse_coordinate_text(self._find_text(point_element, "kml:coordinates"))
            if len(coordinates) != 1:
                raise InvalidKMLError("A KML Point must contain exactly one coordinate tuple.")
            geometries.append(KmlPointGeometry(coordinates=coordinates[0]))  # single coordinate tuple

        # LineString
        for line_element in placemark_element.findall(".//kml:LineString", _NS):
            coordinates = self._parse_coordinate_text(self._find_text(line_element, "kml:coordinates"))
            geometries.append(KmlLineGeometry(coordinates=coordinates))  # list of coordinate tuples

        return geometries

    def _parse_coordinate_text(self, text: str | None) -> list[KmlCoordinate]:
        """Parse KML coordinate text into longitude/latitude/altitude tuples."""
        if text is None:
            return []

        coordinates: list[KmlCoordinate] = []
        for raw_tuple in text.split():
            parts = [part.strip() for part in raw_tuple.split(",") if part.strip()]
            if len(parts) not in {2, 3}:
                raise InvalidKMLError(f"Invalid coordinate tuple '{raw_tuple}'. Expected lon,lat[,alt].")

            longitude = float(parts[0])
            latitude = float(parts[1])
            altitude = float(parts[2]) if len(parts) == 3 else 0.0
            coordinates.append((longitude, latitude, altitude))

        return coordinates

    def _find_document_or_folder(self, root: ET.Element) -> ET.Element | None:
        """Return the top-level Document node, or the top-level Folder if no Document exists."""
        document_element = root.find("kml:Document", _NS)
        if document_element is not None:
            return document_element
        return root.find("kml:Folder", _NS)

    def _find_text(self, element: ET.Element | None, xpath: str) -> str | None:
        """Find text under an optional element and normalize whitespace-only values to None."""
        if element is None:
            return None
        child = element.find(xpath, _NS)
        return self._clean_text(child.text if child is not None else None)

    def _clean_text(self, value: str | None) -> str | None:
        """Trim surrounding whitespace and convert empty strings to None."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _local_name(self, tag: str) -> str:
        """Return the namespace-free local XML tag name."""
        return tag.split("}", maxsplit=1)[-1]

