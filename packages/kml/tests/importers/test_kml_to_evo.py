from pathlib import Path

import pyarrow.parquet as pq
import pytest
from evo_schemas.components.crs import Crs_V1_0_1_EpsgCode
from evo_schemas.objects.line_segments import LineSegments_V2_2_0
from evo_schemas.objects.pointset import Pointset_V1_3_0

from evo.data_converters.kml.importer import convert_kml_kmz
from evo.data_converters.kml.importer.exceptions import InvalidKMLError

this_dir = Path(__file__).resolve().parent.parent
WGS84_CRS = Crs_V1_0_1_EpsgCode(epsg_code=4326)  # Expected CRS for KML/KMZ longitude/latitude coordinates.


def _assert_common_tags(tags: dict[str, str], source: str) -> None:
    assert tags["Source"] == source
    assert tags["Stage"] == "Experimental"
    assert tags["InputType"] == "KML/KMZ"


def _read_saved_table(upload_path: Path, data_path: str):
    # Helper functions for reading the saved table and extracting coordinates from it
    return pq.read_table(upload_path / data_path)


def _rows_as_xyz(table) -> list[tuple[float, float, float]]:
    return [
        (
            table["x"][row_index].as_py(),
            table["y"][row_index].as_py(),
            table["z"][row_index].as_py(),
        )
        for row_index in range(table.num_rows)
    ]


def test_failed_to_read_file() -> None:
    file_name = this_dir / "data" / "not_file.kml"
    with pytest.raises(InvalidKMLError, match="Could not read KML/KMZ file"):
        convert_kml_kmz(str(file_name), publish_objects=False)


def test_convert_point_object(tmp_path: Path) -> None:
    tags = {"CustomTag": "custom-value"}

    file_name = this_dir / "data" / "test_point.kml"

    # Transform test_point.kml into Evo Point object (without publishing them)
    result = convert_kml_kmz(str(file_name), tags=tags, upload_path=str(tmp_path), publish_objects=False)

    # Assert that the result is a list containing a single Pointset_V1_3_0 object with the expected properties
    assert len(result) == 1
    assert isinstance(result[0], Pointset_V1_3_0)
    assert result[0].name == "Test Point - points"
    assert result[0].coordinate_reference_system == WGS84_CRS
    _assert_common_tags(result[0].tags, "test_point.kml (via Evo Data Converters)")
    assert result[0].tags["CustomTag"] == "custom-value"
    assert result[0].tags["Placemark"] == "Test Point"

    # Assert that the coordinates in the generated Evo object match the coordinates from the original KML file
    coordinates_table = _read_saved_table(tmp_path, result[0].locations.coordinates.data)

    source_kml_coordinates = [(10.197, 56.162, 0.0)]  # Coordinates from original source file: tests/data/test_point.kml
    evo_object_coordinates = _rows_as_xyz(coordinates_table)  # Coordinates produced in generated Evo object

    assert evo_object_coordinates == pytest.approx(source_kml_coordinates)


def test_convert_line_object(tmp_path: Path) -> None:
    file_name = this_dir / "data" / "test_line.kml"

    # Transform test_line.kml into Evo LineSegments object (without publishing them)
    result = convert_kml_kmz(str(file_name), upload_path=str(tmp_path), publish_objects=False)

    # Assert that the result is a list containing a single LineSegments_V2_2_0 object with the expected properties
    assert len(result) == 1
    assert isinstance(result[0], LineSegments_V2_2_0)
    assert result[0].name == "Test Line - lines"
    assert result[0].coordinate_reference_system == WGS84_CRS

    # Assert that the coordinates in the generated Evo object match the coordinates from the original KML file
    vertices_table = _read_saved_table(tmp_path, result[0].segments.vertices.data)

    # Coordinates from original source file: tests/data/test_line.kml
    source_kml_coordinates = [
        (10.197, 56.162, 0.0),
        (10.2, 56.165, 0.0),
        (10.205, 56.17, 0.0),
    ]
    # Coordinates produced in generated Evo object
    evo_object_coordinates = _rows_as_xyz(vertices_table)

    assert evo_object_coordinates == pytest.approx(source_kml_coordinates)

    # Assert that the indices in the generated Evo object match line connectivity.
    # For 3 vertices in order [0, 1, 2], Evo stores 2 connected segments: 0->1 and 1->2.
    indices_table = _read_saved_table(tmp_path, result[0].segments.indices.data)

    assert indices_table.num_rows == 2
    assert indices_table["n0"][0].as_py() == 0  # first segment starts at first vertex
    assert indices_table["n1"][0].as_py() == 1  # first segment ends at second vertex
    assert indices_table["n0"][1].as_py() == 1  # second segment starts at second vertex
    assert indices_table["n1"][1].as_py() == 2  # second segment ends at third vertex


def test_kml_test_mixed_point_line_polygon_skips_polygon_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    file_name = this_dir / "data" / "KML_Test.kml"
    tags = {"Source": "KML Test case", "SourceKind": "KML"}

    # KML_Test.kml contains Point, LineString and Polygon placemarks.
    # Assert that "Polygon" is unsupported and should be skipped with a warning while supported geometries are converted.
    result = convert_kml_kmz(str(file_name), tags=tags, upload_path=str(tmp_path), publish_objects=False)
    assert len(result) == 2
    assert isinstance(result[0], Pointset_V1_3_0)
    assert isinstance(result[1], LineSegments_V2_2_0)
    assert "Skipping placemark 'TestPolygon' because it contains no supported geometry." in caplog.text

    # Assert that the Point coordinates from original source file match the generated Evo point object coordinates
    source_kml_point_coordinates = [(10.21113635344518, 56.15387141183808, 0.0)]
    point_object = next(item for item in result if isinstance(item, Pointset_V1_3_0))
    assert point_object.name == "AGS_office - points"
    _assert_common_tags(point_object.tags, "KML Test case")
    assert point_object.tags["SourceKind"] == "KML"
    assert point_object.tags["Placemark"] == "AGS_office"
    assert point_object.tags["FolderPath"] == "KML_Test"
    point_table = _read_saved_table(tmp_path, point_object.locations.coordinates.data)
    evo_point_coordinates = _rows_as_xyz(point_table)
    assert evo_point_coordinates == pytest.approx(source_kml_point_coordinates)

    # Assert that the LineString coordinates from original source file match the generated Evo LineSegment object coordinates
    source_kml_line_coordinates = [
        (10.21122776272251, 56.15382735484665, 0.0),
        (10.21222368632829, 56.15326129528336, 0.0),
        (10.21133517191103, 56.15250091564997, 0.0),
        (10.21071653952973, 56.15187938686141, 0.0),
        (10.20834299265099, 56.15226137840068, 0.0),
        (10.20747567551576, 56.15116884425976, 0.0),
    ]
    line_object = next(item for item in result if isinstance(item, LineSegments_V2_2_0))
    assert line_object.name == "TestLine - lines 2"
    _assert_common_tags(line_object.tags, "KML Test case")
    assert line_object.tags["SourceKind"] == "KML"
    assert line_object.tags["Placemark"] == "TestLine"
    assert line_object.tags["FolderPath"] == "KML_Test"
    line_vertices_table = _read_saved_table(tmp_path, line_object.segments.vertices.data)
    evo_line_coordinates = _rows_as_xyz(line_vertices_table)
    assert evo_line_coordinates == pytest.approx(source_kml_line_coordinates)
