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

import io
import logging

import ezdxf
import numpy as np
import pytest
from ezdxf.document import Drawing

from evo.data_converters.agsi.reader import (
    AGSIInvalidDataError,
    GeometryFileFormat,
    chain_lines,
    parse_dxf,
    parse_geometry,
    parse_stl,
    parse_wkt,
    sniff_format,
)
from evo.data_converters.agsi.reader import geometry_files


def _dxf_bytes(doc: Drawing) -> bytes:
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def _stl_binary(triangles: np.ndarray) -> bytes:
    header = b"Created with the Wolfram Language".ljust(80, b" ")
    records = np.zeros(len(triangles), dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])
    records["v"] = triangles
    return header + np.uint32(len(triangles)).tobytes() + records.tobytes()


TWO_TRIANGLES = np.array(
    [[[0, 0, 1], [10, 0, 1.5], [0, 10, 2]], [[10, 0, 1.5], [10, 10, 2.5], [0, 10, 2]]], dtype=float
)


class TestWkt:
    def test_2d_linestring(self) -> None:
        result = parse_wkt(b"LINESTRING (0. 4.61849, 4.543 4.51569, 9.08601 4.40242)")
        assert result.dimension == 2
        np.testing.assert_allclose(result.single_line(), [[0, 4.61849], [4.543, 4.51569], [9.08601, 4.40242]])

    def test_3d_linestring(self) -> None:
        result = parse_wkt("LINESTRING (539642.5 180075.25 -8.8, 539647 180072 -8.9)")
        assert result.dimension == 3
        np.testing.assert_array_equal(result.lines[0][:, 2], [-8.8, -8.9])

    def test_polygon_z_keeps_closing_vertex(self) -> None:
        result = parse_wkt("POLYGON ((0 0 0, 10 0 0, 10 10 0, 0 0 0))")
        assert len(result.polygons) == 1
        assert result.polygons[0][0].shape == (4, 3)

    def test_polygon_with_hole(self) -> None:
        result = parse_wkt("POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0), (2 2, 3 2, 3 3, 2 2))")
        assert [ring.shape for ring in result.polygons[0]] == [(5, 2), (4, 2)]

    def test_tin_geometry_collection_becomes_mesh(self) -> None:
        result = parse_wkt(
            "GEOMETRYCOLLECTION (POLYGON ((0 0 1, 10 0 1.5, 0 10 2, 0 0 1)), "
            "POLYGON ((10 0 1.5, 10 10 2.5, 0 10 2, 10 0 1.5)))"
        )
        assert result.mesh is not None and not result.polygons
        assert result.mesh.vertices.shape == (4, 3)
        np.testing.assert_array_equal(result.mesh.vertices[result.mesh.triangles], TWO_TRIANGLES)
        np.testing.assert_array_equal(result.to_triangle_mesh().triangles, result.mesh.triangles)

    def test_non_triangle_polygons_fan_triangulated(self) -> None:
        result = parse_wkt(
            "GEOMETRYCOLLECTION (POLYGON ((0 0 0, 1 0 0, 1 1 0, 0 1 0, 0 0 0)), POLYGON ((2 0 0, 3 0 0, 3 1 0, 2 0 0)))"
        )
        assert len(result.polygons) == 2
        assert result.to_triangle_mesh().triangles.shape == (3, 3)

    def test_mixed_geometry_collection(self) -> None:
        result = parse_wkt("GEOMETRYCOLLECTION (POINT (1 2), LINESTRING (0 0, 1 1), POLYGON ((0 0, 1 0, 1 1, 0 0)))")
        assert len(result.points) == 1 and len(result.lines) == 1 and len(result.polygons) == 1
        assert result.mesh is None
        with pytest.raises(AGSIInvalidDataError, match="2D"):
            result.to_triangle_mesh()

    def test_ewkt_srid(self) -> None:
        result = parse_wkt("SRID=27700;LINESTRING (1 2 3, 4 5 6)")
        assert result.srid == 27700

    def test_wolfram_two_line_exponent(self) -> None:
        # As found in the published Silvertown 3D WKT example.
        result = parse_wkt(
            "POLYGON ((540274. 180248.           -9\n1.19787 10, 540269. 180244. 0.1, 540274. 180242. 0.09, "
            "540274. 180248.           -9\n1.19787 10))"
        )
        assert result.polygons[0][0][0, 2] == pytest.approx(1.19787e-9)

    def test_multiline_wkt_is_untouched(self) -> None:
        result = parse_wkt("LINESTRING (1 2,\n3 4,\n5 10)")
        np.testing.assert_array_equal(result.lines[0], [[1, 2], [3, 4], [5, 10]])

    def test_invalid(self) -> None:
        with pytest.raises(AGSIInvalidDataError):
            parse_wkt("LINESTRING (1 2,")


class TestDxf:
    def test_line_chain_2d(self) -> None:
        doc = ezdxf.new()
        msp = doc.modelspace()
        points = [(0, 4.6, 0), (4.5, 4.5, 0), (9.1, 4.4, 0), (13.6, 4.3, 0)]
        # Out of order and with one reversed segment to exercise chaining.
        msp.add_line(points[2], points[3])
        msp.add_line(points[1], points[0])
        msp.add_line(points[1], points[2])
        result = parse_dxf(_dxf_bytes(doc))
        assert result.dimension == 2
        line = result.single_line()
        if line[0, 0] != 0:
            line = line[::-1]
        np.testing.assert_allclose(line, np.array(points)[:, :2])

    def test_keep_zero_z(self) -> None:
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0, 0), (1, 1, 0))
        assert parse_dxf(_dxf_bytes(doc), drop_zero_z=False).dimension == 3

    def test_line_chain_3d_fast_path_matches_ezdxf(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = ezdxf.new()
        msp = doc.modelspace()
        points = [(539642.0, 180075.0, -8.8), (539647.0, 180072.0, -8.9), (539650.0, 180076.0, -8.91)]
        for start, end in zip(points[:-1], points[1:]):
            msp.add_line(start, end)
        data = _dxf_bytes(doc)
        fast = parse_dxf(data)
        monkeypatch.setattr(geometry_files, "_read_simple_ascii_dxf", lambda *args: None)
        slow = parse_dxf(data)
        np.testing.assert_array_equal(fast.single_line(), points)
        np.testing.assert_array_equal(slow.single_line(), points)

    @pytest.mark.parametrize("use_fast_path", [True, False])
    def test_3dface_mesh(self, use_fast_path: bool, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = ezdxf.new()
        msp = doc.modelspace()
        for triangle in TWO_TRIANGLES:
            msp.add_3dface([*map(tuple, triangle), tuple(triangle[2])])
        msp.add_3dface([(20, 0, 0), (30, 0, 0), (30, 10, 0), (20, 10, 0)])  # quad -> 2 triangles
        if not use_fast_path:
            monkeypatch.setattr(geometry_files, "_read_simple_ascii_dxf", lambda *args: None)
        result = parse_dxf(_dxf_bytes(doc))
        assert result.mesh is not None
        assert result.mesh.triangles.shape == (4, 3)
        np.testing.assert_array_equal(result.mesh.vertices[result.mesh.triangles[:2]], TWO_TRIANGLES)

    def test_fast_path_layer_filter(self) -> None:
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0, 1), (1, 1, 1), dxfattribs={"layer": "Top"})
        doc.modelspace().add_line((0, 0, -1), (1, 1, -1), dxfattribs={"layer": "Base"})
        data = _dxf_bytes(doc)
        assert geometry_files._read_simple_ascii_dxf(data, "base") is not None
        np.testing.assert_array_equal(parse_dxf(data, layer="BASE").single_line()[:, 2], [-1, -1])

    def test_lwpolyline_polyline_and_layer_filter(self) -> None:
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (1, 1), (2, 0)], dxfattribs={"layer": "TOP", "elevation": 5.0})
        msp.add_polyline3d([(0, 0, 1), (1, 1, 2)], dxfattribs={"layer": "BASE"})
        data = _dxf_bytes(doc)
        assert geometry_files._read_simple_ascii_dxf(data, None) is None
        top = parse_dxf(data, layer="top")
        np.testing.assert_array_equal(top.single_line(), [[0, 0, 5], [1, 1, 5], [2, 0, 5]])
        base = parse_dxf(data, layer="BASE")
        np.testing.assert_array_equal(base.single_line(), [[0, 0, 1], [1, 1, 2]])
        assert len(parse_dxf(data).lines) == 2

    def test_polyface_mesh(self) -> None:
        doc = ezdxf.new()
        polyface = doc.modelspace().add_polyface()
        polyface.append_face([(0, 0, 0), (1, 0, 0), (1, 1, 1)])
        polyface.append_face([(0, 0, 0), (1, 1, 1), (0, 1, 0), (0, 0.5, 0)])
        polyface.optimize()
        result = parse_dxf(_dxf_bytes(doc))
        assert result.mesh is not None and len(result.mesh.triangles) == 3

    def test_unsupported_entities_are_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        doc = ezdxf.new()
        doc.modelspace().add_circle((0, 0), 1)
        doc.modelspace().add_line((0, 0), (1, 1))
        with caplog.at_level(logging.WARNING):
            result = parse_dxf(_dxf_bytes(doc))
        assert len(result.lines) == 1
        assert "CIRCLE" in caplog.text

    def test_invalid(self) -> None:
        with pytest.raises(AGSIInvalidDataError):
            parse_dxf(b"\x00\x01 not a dxf")


class TestStl:
    def test_binary(self) -> None:
        result = parse_stl(_stl_binary(TWO_TRIANGLES))
        assert result.mesh is not None
        np.testing.assert_allclose(result.mesh.vertices[result.mesh.triangles], TWO_TRIANGLES)

    def test_ascii(self) -> None:
        facets = "".join(
            "facet normal 0 0 1\nouter loop\n"
            + "".join(f"vertex {x} {y} {z}\n" for x, y, z in t)
            + "endloop\nendfacet\n"
            for t in TWO_TRIANGLES
        )
        result = parse_stl(f"solid test\n{facets}endsolid test\n".encode())
        assert result.mesh is not None
        np.testing.assert_allclose(result.mesh.vertices[result.mesh.triangles], TWO_TRIANGLES)

    def test_binary_header_starting_with_solid(self) -> None:
        data = _stl_binary(TWO_TRIANGLES)
        data = b"solid binary".ljust(80, b" ") + data[80:]
        result = parse_stl(data)
        assert result.mesh is not None and len(result.mesh.triangles) == 2


class TestFormatDetection:
    def test_sniff(self) -> None:
        assert sniff_format(b"  LINESTRING (0 0, 1 1)") is GeometryFileFormat.WKT
        assert sniff_format(b"SRID=4326;POINT (0 0)") is GeometryFileFormat.WKT
        assert sniff_format(_dxf_bytes(ezdxf.new())) is GeometryFileFormat.DXF
        assert sniff_format(b"999\nCreated with the Wolfram Language\n0\nSECTION\n") is GeometryFileFormat.DXF
        assert sniff_format(_stl_binary(TWO_TRIANGLES)) is GeometryFileFormat.STL
        assert sniff_format(b"hello") is None

    def test_content_wins_over_declared_format(self) -> None:
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0), (1, 1))
        result = parse_geometry(_dxf_bytes(doc), file_format="WKT", name="Profiles/x.txt")
        assert result.source_format is GeometryFileFormat.DXF

    def test_unrecognised_content(self) -> None:
        with pytest.raises(AGSIInvalidDataError, match="x.txt"):
            parse_geometry(b"hello", file_format="WKT", name="x.txt")
        with pytest.raises(AGSIInvalidDataError, match="unsupported"):
            parse_geometry(b"hello", file_format="IFC")


class TestChainLines:
    def test_joins_and_reverses(self) -> None:
        parts = [np.array([[2.0, 0], [3, 0]]), np.array([[1.0, 0], [0, 0]]), np.array([[1.0, 0], [2, 0]])]
        chains = chain_lines(parts)
        assert len(chains) == 1
        line = chains[0] if chains[0][0, 0] == 0 else chains[0][::-1]
        np.testing.assert_array_equal(line[:, 0], [0, 1, 2, 3])

    def test_disconnected(self) -> None:
        parts = [np.array([[0.0, 0], [1, 0]]), np.array([[5.0, 0], [6, 0]])]
        assert len(chain_lines(parts)) == 2

    def test_single_line_rejects_disconnected(self) -> None:
        result = parse_wkt("MULTILINESTRING ((0 0, 1 0), (5 0, 6 0))")
        with pytest.raises(AGSIInvalidDataError, match="2 separate lines"):
            result.single_line()
