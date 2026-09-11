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

from dataclasses import dataclass

import pyarrow as pa
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components import (
    BoundingBox_V1_0_1,
    Crs_V1_0_1,
    Segments_V1_2_0,
    Segments_V1_2_0_Indices,
    Segments_V1_2_0_Vertices,
)
from evo_schemas.elements import FloatArray3_V1_0_1, IndexArray2_V1_0_1
from evo_schemas.objects.line_segments import LineSegments_V2_2_0, LineSegments_V2_2_0_Parts
from evo_schemas.objects.pointset import Pointset_V1_3_0, Pointset_V1_3_0_Locations

from evo.data_converters.kml.importer.implementation.kml_document_parser import (
    KmlCoordinate,
    KmlDocument,
    KmlLineGeometry,
    KmlPlacemark,
    KmlPointGeometry,
)


@dataclass(slots=True)
class KmlEvoObjectBuilder:
    """Build Evo point (Pointset_V1_3_0) and line (LineSegments_V2_2_0) objects from parsed KML content."""

    data_client: ObjectDataClient
    crs: Crs_V1_0_1
    tags: dict[str, str] | None = None

    def build(self, document: KmlDocument) -> list[Pointset_V1_3_0 | LineSegments_V2_2_0]:
        """Build Evo objects for every parsed placemark in the KML/KMZ document."""
        objects: list[Pointset_V1_3_0 | LineSegments_V2_2_0] = []
        for placemark_index, placemark in enumerate(document.placemarks):
            objects.extend(self._build_placemark_objects(document, placemark, placemark_index))
        return objects

    def _build_placemark_objects(
        self, document: KmlDocument, placemark: KmlPlacemark, placemark_index: int
    ) -> list[Pointset_V1_3_0 | LineSegments_V2_2_0]:
        """Split one placemark into point and line Evo objects based on its geometry types."""
        point_geometries = [geometry for geometry in placemark.geometries if isinstance(geometry, KmlPointGeometry)]
        line_geometries = [geometry for geometry in placemark.geometries if isinstance(geometry, KmlLineGeometry)]

        objects: list[Pointset_V1_3_0 | LineSegments_V2_2_0] = []
        if point_geometries:
            objects.append(self._build_pointset(document, placemark, placemark_index, point_geometries))
        if line_geometries:
            objects.append(self._build_line_segments(document, placemark, placemark_index, line_geometries))
        return objects

    def _build_pointset(
        self,
        document: KmlDocument,
        placemark: KmlPlacemark,
        placemark_index: int,
        geometries: list[KmlPointGeometry],
    ) -> Pointset_V1_3_0:
        """Convert one or more KML Point geometries into a single Evo Pointset object."""
        points = [geometry.coordinates for geometry in geometries]
        bounding_box = self._bounding_box(points)
        coordinates_info = self.data_client.save_table(self._points_to_table(points))
        locations = Pointset_V1_3_0_Locations(coordinates=FloatArray3_V1_0_1(**coordinates_info), attributes=None)

        return Pointset_V1_3_0(
            name=self._object_name(document, placemark, placemark_index, "points"),
            uuid=None,
            description=placemark.description,
            bounding_box=bounding_box,
            coordinate_reference_system=self.crs,
            locations=locations,
            tags=self._merged_tags(document, placemark),
        )

    def _build_line_segments(
        self,
        document: KmlDocument,
        placemark: KmlPlacemark,
        placemark_index: int,
        geometries: list[KmlLineGeometry],
    ) -> LineSegments_V2_2_0:
        """Convert one or more KML LineString geometries into an Evo LineSegments object."""
        vertices: list[KmlCoordinate] = []
        indices: list[tuple[int, int]] = []
        parts: list[tuple[int, int]] = []

        for geometry in geometries:
            if len(geometry.coordinates) < 2:
                raise ValueError("A KML LineString must contain at least two coordinate tuples.")

            start_vertex = len(vertices)
            start_segment = len(indices)
            vertices.extend(geometry.coordinates)
            for vertex_index in range(start_vertex, len(vertices) - 1):
                indices.append((vertex_index, vertex_index + 1))
            parts.append((start_segment, len(indices) - start_segment))

        bounding_box = self._bounding_box(vertices)
        vertices_info = self.data_client.save_table(self._vertices_to_table(vertices))
        indices_info = self.data_client.save_table(self._indices_to_table(indices))

        segments = Segments_V1_2_0(
            vertices=Segments_V1_2_0_Vertices(**vertices_info, attributes=None),
            indices=Segments_V1_2_0_Indices(**indices_info, attributes=None),
        )

        # Provide grouping information for multiple separate KML LineString geometries
        parts_obj = None
        if parts:
            parts_info = self.data_client.save_table(self._parts_to_table(parts))
            parts_obj = LineSegments_V2_2_0_Parts(
                chunks=IndexArray2_V1_0_1(**parts_info),
                attributes=None,
            )

        return LineSegments_V2_2_0(
            name=self._object_name(document, placemark, placemark_index, "lines"),
            uuid=None,
            description=placemark.description,
            bounding_box=bounding_box,
            coordinate_reference_system=self.crs,
            segments=segments,
            parts=parts_obj,
            tags=self._merged_tags(document, placemark),
        )

    def _points_to_table(self, points: list[KmlCoordinate]) -> pa.Table:
        """Store point coordinates in a 3-column table matching the Evo FloatArray3 layout."""
        return pa.table(
            {
                "x": [point[0] for point in points],
                "y": [point[1] for point in points],
                "z": [point[2] for point in points],
            },
            schema=pa.schema([("x", pa.float64()), ("y", pa.float64()), ("z", pa.float64())]),
        )

    def _vertices_to_table(self, vertices: list[KmlCoordinate]) -> pa.Table:
        """Reuse the point-table layout for line vertices because both store x/y/z coordinates."""
        return self._points_to_table(vertices)

    def _indices_to_table(self, indices: list[tuple[int, int]]) -> pa.Table:
        """Store segment connectivity as pairs of vertex indices."""
        return pa.table(
            {
                "n0": [segment[0] for segment in indices],
                "n1": [segment[1] for segment in indices],
            },
            schema=pa.schema([("n0", pa.uint64()), ("n1", pa.uint64())]),
        )

    def _parts_to_table(self, parts: list[tuple[int, int]]) -> pa.Table:
        """Store line-part grouping as offset/count pairs so separate LineStrings can be reconstructed."""
        return pa.table(
            {
                "offset": [part[0] for part in parts],
                "count": [part[1] for part in parts],
            },
            schema=pa.schema([("offset", pa.uint64()), ("count", pa.uint64())]),
        )

    def _bounding_box(self, coordinates: list[KmlCoordinate]) -> BoundingBox_V1_0_1:
        """Compute the bounding box for all coordinates included in the output object."""
        xs = [coordinate[0] for coordinate in coordinates]
        ys = [coordinate[1] for coordinate in coordinates]
        zs = [coordinate[2] for coordinate in coordinates]
        return BoundingBox_V1_0_1(
            min_x=min(xs),
            max_x=max(xs),
            min_y=min(ys),
            max_y=max(ys),
            min_z=min(zs),
            max_z=max(zs),
        )

    def _object_name(self, document: KmlDocument, placemark: KmlPlacemark, placemark_index: int, suffix: str) -> str:
        """Create a stable object name based on the placemark, document, and object type suffix."""
        base_name = placemark.name or document.document_name or document.source_path.stem
        return f"{base_name} - {suffix}" if placemark_index == 0 else f"{base_name} - {suffix} {placemark_index + 1}"

    def _merged_tags(self, document: KmlDocument, placemark: KmlPlacemark) -> dict[str, str]:
        """Merge caller-provided tags with KML-derived metadata without overwriting explicit values."""
        merged_tags = dict(self.tags or {})
        merged_tags.setdefault("Source", document.source_path.name)
        if placemark.name:
            merged_tags.setdefault("Placemark", placemark.name)
        if placemark.folder_path:
            merged_tags.setdefault("FolderPath", "/".join(placemark.folder_path))
        return merged_tags
