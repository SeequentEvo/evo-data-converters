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

"""Parsers for AGSi supporting geometry files (WKT, DXF and STL) into numpy arrays."""

import io
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

import numpy as np
import numpy.typing as npt
import shapely
from shapely.errors import GEOSException

import evo.logging

from .errors import AGSIInvalidDataError

logger = evo.logging.getLogger("data_converters")

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


class GeometryFileFormat(str, Enum):
    WKT = "WKT"
    DXF = "DXF"
    STL = "STL"


_FORMAT_ALIASES = {
    "WKT": GeometryFileFormat.WKT,
    "TXT": GeometryFileFormat.WKT,
    "DXF": GeometryFileFormat.DXF,
    "STL": GeometryFileFormat.STL,
    "STLA": GeometryFileFormat.STL,
    "STLB": GeometryFileFormat.STL,
}

_WKT_PREFIX = re.compile(
    rb"^\s*(SRID=\d+\s*;\s*)?(POINT|LINESTRING|LINEARRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\b",
    re.IGNORECASE,
)
_EWKT_SRID = re.compile(r"^\s*SRID=(\d+)\s*;\s*", re.IGNORECASE)
# Some Wolfram Language WKT exports write small numbers in two-line "exponent above" form,
# e.g. "    -9\n1.19787 10" for 1.19787e-9. These patterns match either side of the line break.
_EXPONENT_LINE_END = re.compile(r"(?:^|(?<=[\s,(]))(-?\d+)[ \t\r]*$")
_MANTISSA_LINE_START = re.compile(r"[ \t]*(-?\d+(?:\.\d*)?)[ \t]+10(?=[\s,)]|$)")


def _repair_wolfram_exponents(text: str) -> tuple[str, int]:
    pieces = text.split("\n")
    out = [pieces[0]]
    count = 0
    for piece in pieces[1:]:
        previous = out[-1]
        # Only the last few characters can hold the exponent; avoid scanning long lines.
        tail_start = max(0, len(previous) - 32)
        exponent = _EXPONENT_LINE_END.search(previous, tail_start)
        mantissa = _MANTISSA_LINE_START.match(piece) if exponent else None
        if exponent and mantissa:
            out[-1] = f"{previous[: exponent.start()]}{mantissa.group(1)}e{exponent.group(1)}{piece[mantissa.end() :]}"
            count += 1
        else:
            out.append(piece)
    return "\n".join(out), count


@dataclass
class TriangleMesh:
    """Indexed triangle mesh: ``vertices`` (N, 3) and zero-based ``triangles`` (M, 3)."""

    vertices: FloatArray
    triangles: IntArray


@dataclass
class GeometryData:
    """Geometry parsed from a supporting file, in the file's own coordinates.

    ``lines`` and ``points`` hold (N, 2) or (N, 3) arrays. ``polygons`` holds a list of rings
    per polygon (exterior first, closing vertex retained). ``mesh`` is populated for triangle
    data: DXF 3DFACE / polyface meshes, STL, and WKT collections made only of 3D triangles
    (TINs), which are not repeated in ``polygons``.
    """

    source_format: GeometryFileFormat
    lines: list[FloatArray] = field(default_factory=list)
    polygons: list[list[FloatArray]] = field(default_factory=list)
    points: list[FloatArray] = field(default_factory=list)
    mesh: Optional[TriangleMesh] = None
    srid: Optional[int] = None

    @property
    def dimension(self) -> int:
        """Coordinate dimension (2 or 3) of the parsed geometry; 0 if empty."""
        arrays = [*self.lines, *self.points, *(ring for rings in self.polygons for ring in rings)]
        dims = [a.shape[1] for a in arrays if a.size]
        if self.mesh is not None and len(self.mesh.vertices):
            dims.append(3)
        return max(dims, default=0)

    @property
    def is_empty(self) -> bool:
        return not (self.lines or self.polygons or self.points or (self.mesh is not None and len(self.mesh.triangles)))

    def single_line(self, tolerance: float = 1e-9) -> FloatArray:
        """Return the geometry as one polyline, joining connected parts (e.g. DXF LINE chains).

        :raise AGSIInvalidDataError: If there are no lines or they do not form one connected line.
        """
        if not self.lines:
            raise AGSIInvalidDataError("Geometry file does not contain a line.")
        if len(self.lines) == 1:
            return self.lines[0]
        chains = chain_lines(self.lines, tolerance)
        if len(chains) != 1:
            raise AGSIInvalidDataError(f"Expected a single connected line but found {len(chains)} separate lines.")
        return chains[0]

    def to_triangle_mesh(self) -> TriangleMesh:
        """Return a triangle mesh built from ``mesh`` and/or triangular polygons (WKT TINs).

        Polygons with more than three vertices are fan-triangulated, which assumes convex
        facets. Duplicate vertices are merged exactly.

        :raise AGSIInvalidDataError: For 2D geometry or polygons with holes.
        """
        tris: list[FloatArray] = []
        if self.mesh is not None and len(self.mesh.triangles):
            tris.append(self.mesh.vertices[self.mesh.triangles])
        for rings in self.polygons:
            if len(rings) > 1:
                raise AGSIInvalidDataError("Cannot build a triangle mesh from polygons with holes.")
            ring = rings[0]
            if ring.shape[1] != 3:
                raise AGSIInvalidDataError("Cannot build a triangle mesh from 2D polygons.")
            if len(ring) > 1 and np.array_equal(ring[0], ring[-1]):
                ring = ring[:-1]
            if len(ring) < 3:
                continue
            fan = np.stack([np.repeat(ring[:1], len(ring) - 2, axis=0), ring[1:-1], ring[2:]], axis=1)
            tris.append(fan)
        if not tris:
            raise AGSIInvalidDataError("Geometry file does not contain any triangles.")
        return _indexed_mesh(np.concatenate(tris).reshape(-1, 3))


def _indexed_mesh(corners: FloatArray) -> TriangleMesh:
    """Build an indexed mesh from (3M, 3) triangle corners, merging identical vertices."""
    vertices, inverse = np.unique(corners, axis=0, return_inverse=True)
    return TriangleMesh(vertices=vertices.astype(np.float64), triangles=inverse.reshape(-1, 3).astype(np.int64))


def chain_lines(lines: list[FloatArray], tolerance: float = 1e-9) -> list[FloatArray]:
    """Join polylines that share end points into as few polylines as possible.

    Parts are joined end-to-start in either direction, so the order and orientation of
    DXF LINE entities does not matter.
    """
    chains: list[list[FloatArray]] = []
    for line in lines:
        part = np.asarray(line, dtype=np.float64)
        if not len(part):
            continue
        # Cheap pass for the common case of parts already in drawing order.
        if chains and _close(chains[-1][-1][-1], part[0], tolerance):
            chains[-1].append(part)
        else:
            chains.append([part])
    merged = True
    while merged and len(chains) > 1:
        merged = False
        for i in range(len(chains)):
            head = chains[i]
            for j in range(len(chains)):
                if i == j:
                    continue
                other = chains[j]
                if _close(head[-1][-1], other[0][0], tolerance):
                    chains[i] = head + other
                elif _close(head[-1][-1], other[-1][-1], tolerance):
                    chains[i] = head + [part[::-1] for part in reversed(other)]
                elif _close(head[0][0], other[-1][-1], tolerance):
                    chains[i] = other + head
                elif _close(head[0][0], other[0][0], tolerance):
                    chains[i] = [part[::-1] for part in reversed(other)] + head
                else:
                    continue
                del chains[j]
                merged = True
                break
            if merged:
                break
    result = []
    for parts in chains:
        joined = [parts[0]] + [
            part[1:] if _close(prev[-1], part[0], tolerance) else part for prev, part in zip(parts, parts[1:])
        ]
        result.append(np.concatenate(joined))
    return result


def _close(a: FloatArray, b: FloatArray, tolerance: float) -> bool:
    return a.shape == b.shape and bool(np.all(np.abs(a - b) <= tolerance))


# --- Format detection --------------------------------------------------------------------


def normalise_file_format(file_format: Optional[str]) -> Optional[GeometryFileFormat]:
    """Map an AGSi ``fileFormat`` value (e.g. ``"WKT"``, ``"dxf"``) to a supported format."""
    if not file_format:
        return None
    return _FORMAT_ALIASES.get(file_format.strip().upper())


def sniff_format(data: bytes) -> Optional[GeometryFileFormat]:
    """Detect the format of a geometry file from its content."""
    if _is_binary_stl(data):
        return GeometryFileFormat.STL
    head = data[:4096]
    if head.startswith(b"\xef\xbb\xbf"):
        head = head[3:]
    if _WKT_PREFIX.match(head):
        return GeometryFileFormat.WKT
    stripped = head.lstrip()
    if stripped[:5].lower() == b"solid" and b"facet" in head.lower():
        return GeometryFileFormat.STL
    if head.startswith(b"AutoCAD Binary DXF"):
        return GeometryFileFormat.DXF
    if re.search(rb"(^|\n)\s*0\s*\r?\n\s*SECTION\s*\r?\n", head):
        return GeometryFileFormat.DXF
    return None


def parse_geometry(
    data: bytes,
    file_format: Optional[str] = None,
    file_part: Optional[str] = None,
    name: str = "<bytes>",
) -> GeometryData:
    """Parse a supporting geometry file.

    The declared ``file_format`` (AGSi ``fileFormat``) is checked against the content; when
    they disagree the detected format wins and a warning is logged. ``file_part`` selects a
    DXF layer.

    :raise AGSIInvalidDataError: If the format is unsupported or the content cannot be parsed.
    """
    declared = normalise_file_format(file_format)
    detected = sniff_format(data)
    fmt = detected or declared
    if declared is not None and detected is not None and declared != detected:
        logger.info(
            f"{name}: declared fileFormat '{file_format}' but content is {detected.value}; using {detected.value}."
        )
    if fmt is None:
        raise AGSIInvalidDataError(f"{name}: unsupported or unrecognised geometry file format '{file_format}'.")
    try:
        if fmt is GeometryFileFormat.WKT:
            return parse_wkt(data)
        if fmt is GeometryFileFormat.DXF:
            return parse_dxf(data, layer=file_part)
        return parse_stl(data)
    except AGSIInvalidDataError as e:
        raise AGSIInvalidDataError(f"{name}: {e}") from e


# --- WKT ---------------------------------------------------------------------------------


def parse_wkt(data: Union[bytes, str]) -> GeometryData:
    """Parse WKT (optionally EWKT with an ``SRID=n;`` prefix) into :class:`GeometryData`."""
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    srid = None
    match = _EWKT_SRID.match(text)
    if match:
        srid = int(match.group(1))
        text = text[match.end() :]
    text = text.strip()
    if "\n" in text:
        text, count = _repair_wolfram_exponents(text)
        if count:
            logger.debug(f"WKT: repaired {count} numbers written in two-line exponent form.")
    try:
        geometry = shapely.from_wkt(text)
    except (GEOSException, ValueError) as e:
        raise AGSIInvalidDataError(f"Invalid WKT: {e}") from e
    result = GeometryData(source_format=GeometryFileFormat.WKT, srid=srid)
    _collect_shapely(geometry, result)
    return result


_POINT, _LINESTRING, _LINEARRING, _POLYGON = 0, 1, 2, 3


def _coords(geometry: Any) -> FloatArray:
    return np.asarray(shapely.get_coordinates(geometry, include_z=shapely.has_z(geometry)), dtype=np.float64)


def _collect_shapely(geometry: Any, out: GeometryData) -> None:
    if geometry is None or shapely.is_empty(geometry):
        return
    type_id = int(shapely.get_type_id(geometry))
    if type_id == _POINT:
        out.points.append(_coords(geometry))
    elif type_id in (_LINESTRING, _LINEARRING):
        out.lines.append(_coords(geometry))
    elif type_id == _POLYGON:
        holes = [shapely.get_interior_ring(geometry, i) for i in range(int(shapely.get_num_interior_rings(geometry)))]
        out.polygons.append([_coords(r) for r in (shapely.get_exterior_ring(geometry), *holes)])
    else:
        parts = shapely.get_parts(geometry)
        simple_polygons = (shapely.get_type_id(parts) == _POLYGON) & (shapely.get_num_interior_rings(parts) == 0)
        has_z = shapely.has_z(parts)
        if len(parts) > 1 and simple_polygons.all() and (has_z.all() or not has_z.any()):
            # Fast path for large TINs encoded as collections of simple polygons.
            exteriors = shapely.get_exterior_ring(parts)
            coords, index = shapely.get_coordinates(exteriors, include_z=bool(has_z.all()), return_index=True)
            counts = np.bincount(index, minlength=len(parts))
            closed_triangles = coords.shape[1] == 3 and bool(np.all(counts == 4))
            if closed_triangles:
                corners = coords.reshape(-1, 4, 3)[:, :3].reshape(-1, 3)
                if out.mesh is not None:
                    corners = np.concatenate([out.mesh.vertices[out.mesh.triangles].reshape(-1, 3), corners])
                out.mesh = _indexed_mesh(corners)
                return
            splits = np.flatnonzero(np.diff(index)) + 1
            out.polygons.extend([[ring.astype(np.float64)] for ring in np.split(coords, splits)])
            return
        for part in parts:
            _collect_shapely(part, out)


# --- DXF ---------------------------------------------------------------------------------


def parse_dxf(data: bytes, layer: Optional[str] = None, drop_zero_z: bool = True) -> GeometryData:
    """Parse DXF entities into :class:`GeometryData`.

    Supported: LINE (joined into polylines), LWPOLYLINE, 2D/3D POLYLINE, polyface POLYLINE,
    3DFACE and POINT. Other entity types are skipped with a warning.

    ASCII DXF files that only contain LINE, 3DFACE and POINT entities (typical of exported
    sections and TIN surfaces) are read with a fast tag scanner; anything else is read with
    ``ezdxf``.

    :param layer: Only read entities on this layer (case-insensitive), e.g. AGSi ``filePart``.
    :param drop_zero_z: Return 2D coordinates when every Z value is zero (2D drawings such as
        cross-sections drawn in chainage/elevation space).
    """
    layer_key = layer.casefold() if layer else None
    simple = _read_simple_ascii_dxf(data, layer_key)
    entities = simple if simple is not None else _read_dxf_with_ezdxf(data, layer_key)

    lines = list(entities.lines)
    if entities.segments:
        lines.extend(chain_lines(entities.segments))
    points = [np.asarray(entities.points, dtype=np.float64).reshape(-1, 3)] if entities.points else []

    triangles = list(entities.triangles)
    if entities.quads:
        quads = np.asarray(entities.quads, dtype=np.float64).reshape(-1, 4, 3)
        triangles.append(quads[:, :3])
        is_quad = np.any(quads[:, 2] != quads[:, 3], axis=1)
        triangles.append(quads[is_quad][:, [0, 2, 3]])

    mesh = None
    if triangles:
        corners = np.concatenate([t.reshape(-1, 3) for t in triangles])
        vertices, inverse = np.unique(corners, axis=0, return_inverse=True)
        mesh = TriangleMesh(vertices=vertices, triangles=inverse.reshape(-1, 3).astype(np.int64))

    if drop_zero_z and mesh is None:
        arrays = [*lines, *points]
        if arrays and all(not np.any(a[:, 2]) for a in arrays):
            lines = [a[:, :2].copy() for a in lines]
            points = [a[:, :2].copy() for a in points]

    return GeometryData(source_format=GeometryFileFormat.DXF, lines=lines, points=points, mesh=mesh)


@dataclass
class _DxfEntities:
    segments: list[FloatArray] = field(default_factory=list)
    lines: list[FloatArray] = field(default_factory=list)
    points: list[tuple[float, float, float]] = field(default_factory=list)
    quads: list[tuple[float, ...]] = field(default_factory=list)
    triangles: list[FloatArray] = field(default_factory=list)


# Entity types handled by the fast reader, with their number of vertices (group codes 1x/2x/3x).
_SIMPLE_DXF_ENTITIES = {b"LINE": 2, b"3DFACE": 4, b"POINT": 1}


def _read_simple_ascii_dxf(data: bytes, layer_key: Optional[str]) -> Optional[_DxfEntities]:
    """Read LINE/3DFACE/POINT entities from an ASCII DXF; ``None`` if ezdxf is needed instead."""
    if data.startswith(b"AutoCAD Binary DXF"):
        return None
    raw = data.split(b"\n")
    codes, values = raw[0::2], raw[1::2]
    count = min(len(codes), len(values))
    start = None
    for i in range(count - 1):
        if values[i].strip() == b"SECTION" and values[i + 1].strip() == b"ENTITIES" and codes[i].strip() == b"0":
            start = i + 2
            break
    if start is None:
        return None

    out = _DxfEntities()
    entity: Optional[bytes] = None
    group: dict[int, float] = {}
    layer = "0"
    paper_space = False
    try:
        for i in range(start, count):
            code = int(codes[i])
            value = values[i].strip()
            if code == 0:
                if entity is not None and not paper_space and (layer_key is None or layer.casefold() == layer_key):
                    _add_simple_entity(out, entity, group)
                if value == b"ENDSEC":
                    return out
                if value not in _SIMPLE_DXF_ENTITIES:
                    return None
                entity, group, layer, paper_space = value, {}, "0", False
            elif code == 8:
                layer = value.decode("utf-8", errors="replace")
            elif code == 67:
                paper_space = value == b"1"
            elif 10 <= code <= 39:
                group[code] = float(value)
    except ValueError:
        return None
    return None


def _add_simple_entity(out: _DxfEntities, entity: bytes, group: dict[int, float]) -> None:
    vertices = [
        (group.get(10 + k, 0.0), group.get(20 + k, 0.0), group.get(30 + k, 0.0))
        for k in range(_SIMPLE_DXF_ENTITIES[entity])
    ]
    if entity == b"LINE":
        out.segments.append(np.array(vertices, dtype=np.float64))
    elif entity == b"3DFACE":
        out.quads.append(tuple(c for v in vertices for c in v))
    else:
        out.points.append(vertices[0])


def _read_dxf_with_ezdxf(data: bytes, layer_key: Optional[str]) -> _DxfEntities:
    from ezdxf import recover
    from ezdxf.entities import Face3d, Line, LWPolyline, Point, Polyface, Polyline
    from ezdxf.lldxf.const import DXFError

    try:
        doc, _auditor = recover.read(io.BytesIO(data))
    except (DXFError, OSError, UnicodeDecodeError) as e:
        raise AGSIInvalidDataError(f"Invalid DXF: {e}") from e

    out = _DxfEntities()
    skipped: dict[str, int] = {}
    for entity in doc.modelspace():
        if layer_key is not None and str(entity.dxf.layer).casefold() != layer_key:
            continue
        if isinstance(entity, Line):
            out.segments.append(np.array([tuple(entity.dxf.start), tuple(entity.dxf.end)], dtype=np.float64))
        elif isinstance(entity, LWPolyline):
            elevation = float(entity.dxf.elevation) if entity.dxf.hasattr("elevation") else 0.0
            xy = np.array([(p[0], p[1]) for p in entity.get_points("xy")], dtype=np.float64).reshape(-1, 2)
            line = np.column_stack([xy, np.full(len(xy), elevation)])
            out.lines.append(_close_ring(line) if entity.closed else line)
        elif isinstance(entity, Polyface):
            out.triangles.extend(_polyface_triangles(entity))
        elif isinstance(entity, Polyline) and (entity.is_2d_polyline or entity.is_3d_polyline):
            line = np.array([tuple(v.dxf.location) for v in entity.vertices], dtype=np.float64).reshape(-1, 3)
            out.lines.append(_close_ring(line) if entity.is_closed else line)
        elif isinstance(entity, Face3d):
            out.quads.append(tuple(c for i in range(4) for c in entity.dxf.get(f"vtx{i}")))
        elif isinstance(entity, Point):
            out.points.append(tuple(entity.dxf.location))
        else:
            kind = entity.dxftype()
            skipped[kind] = skipped.get(kind, 0) + 1
    if skipped:
        logger.warning(f"DXF: skipped unsupported entities {skipped}.")
    return out


def _close_ring(line: FloatArray) -> FloatArray:
    if len(line) and not np.array_equal(line[0], line[-1]):
        return np.vstack([line, line[:1]])
    return line


def _polyface_triangles(entity: Any) -> list[FloatArray]:
    triangles = []
    for face in entity.faces():
        # ezdxf yields the face's vertices followed by the face record itself.
        corners = np.array([tuple(v.dxf.location) for v in face[:-1]], dtype=np.float64)
        unique = [c for i, c in enumerate(corners) if i == 0 or not np.array_equal(c, corners[i - 1])]
        for k in range(1, len(unique) - 1):
            triangles.append(np.array([unique[0], unique[k], unique[k + 1]]))
    return triangles


# --- STL ---------------------------------------------------------------------------------

_STL_BINARY_DTYPE = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
_STL_ASCII_VERTEX = re.compile(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", re.IGNORECASE)


def _is_binary_stl(data: bytes) -> bool:
    if len(data) < 84:
        return False
    count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
    return len(data) == 84 + 50 * count


def parse_stl(data: bytes) -> GeometryData:
    """Parse binary or ASCII STL into a triangle mesh.

    Binary STL stores float32 coordinates, so large projected coordinates lose precision
    (roughly 1 part in 10^7).
    """
    if _is_binary_stl(data):
        count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
        records = np.frombuffer(data, dtype=_STL_BINARY_DTYPE, count=count, offset=84)
        corners = records["vertices"].reshape(-1, 3).astype(np.float64)
    else:
        try:
            values = _STL_ASCII_VERTEX.findall(data)
            corners = np.array(values, dtype=np.float64).reshape(-1, 3)
        except ValueError as e:
            raise AGSIInvalidDataError(f"Invalid ASCII STL: {e}") from e
        if not len(corners) or len(corners) % 3:
            raise AGSIInvalidDataError("Invalid STL: no triangles found.")
    vertices, inverse = np.unique(corners, axis=0, return_inverse=True)
    mesh = TriangleMesh(vertices=vertices, triangles=inverse.reshape(-1, 3).astype(np.int64))
    return GeometryData(source_format=GeometryFileFormat.STL, mesh=mesh)
