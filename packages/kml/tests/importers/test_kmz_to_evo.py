from pathlib import Path

import pyarrow.parquet as pq
import pytest
from evo_schemas.components.crs import Crs_V1_0_1_EpsgCode
from evo_schemas.objects.line_segments import LineSegments_V2_2_0
from evo_schemas.objects.pointset import Pointset_V1_3_0

from evo.data_converters.kml.importer import convert_kml_kmz
from evo.data_converters.kml.importer.exceptions import InvalidKMLError

this_dir = Path(__file__).resolve().parent.parent
WGS84_CRS = Crs_V1_0_1_EpsgCode(epsg_code=4326)


def _assert_common_tags(tags: dict[str, str], source: str) -> None:
    assert tags["Source"] == source
    assert tags["Stage"] == "Experimental"
    assert tags["InputType"] == "KML/KMZ"


def _read_saved_table(upload_path: Path, data_path: str):
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
    file_name = this_dir / "data" / "not_file.kmz"
    with pytest.raises(InvalidKMLError, match="Could not read KML/KMZ file"):
        convert_kml_kmz(str(file_name), publish_objects=False)


def test_convert_kmz_mixed_point_line_polygon_skips_polygon_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    file_name = this_dir / "data" / "KML_Test.kmz"
    tags = {"Source": "KMZ Test case", "SourceKind": "KMZ"}

    # The KMZ sample contains a point, a line, and a polygon.
    # The polygon is unsupported, so the converter should skip it and keep the supported features.
    result = convert_kml_kmz(str(file_name), tags=tags, upload_path=str(tmp_path), publish_objects=False)

    # Assert that the result contains one point object and one line object, and that a warning about the skipped polygon is logged.
    assert len(result) == 2
    assert isinstance(result[0], Pointset_V1_3_0)
    assert isinstance(result[1], LineSegments_V2_2_0)
    assert "Skipping placemark 'TestPolygon' because it contains no supported geometry." in caplog.text

    # ------ Point object assertions ------
    # Extract the generated point and line objects so their saved coordinate tables can be checked.
    point_object = next(item for item in result if isinstance(item, Pointset_V1_3_0))
    
    # Assert that the point object has the expected name, CRS, and tags.
    assert point_object.name == "AGS_office - points"
    assert point_object.coordinate_reference_system == WGS84_CRS
    _assert_common_tags(point_object.tags, "KMZ Test case")
    assert point_object.tags["SourceKind"] == "KMZ"
    assert point_object.tags["Placemark"] == "AGS_office"
    assert point_object.tags["FolderPath"] == "KML_Test"

    # Assert that the point coordinates saved by the converter match the source KML/KMZ data.
    point_table = _read_saved_table(tmp_path, point_object.locations.coordinates.data)
    assert _rows_as_xyz(point_table) == pytest.approx([(10.21113635344518, 56.15387141183808, 0.0)])

    # ------ Line object assertions ------
    # Extract the generated line object
    line_object = next(item for item in result if isinstance(item, LineSegments_V2_2_0))
    
    # Assert that the line object has the expected name, CRS, and tags.    
    assert line_object.name == "TestLine - lines 2"
    assert line_object.coordinate_reference_system == WGS84_CRS
    _assert_common_tags(line_object.tags, "KMZ Test case")
    assert line_object.tags["SourceKind"] == "KMZ"
    assert line_object.tags["Placemark"] == "TestLine"
    assert line_object.tags["FolderPath"] == "KML_Test"

    # Assert that the line vertices were saved in the same order as the source file.
    line_vertices_table = _read_saved_table(tmp_path, line_object.segments.vertices.data)
    assert _rows_as_xyz(line_vertices_table) == pytest.approx(
        [
            (10.21122776272251, 56.15382735484665, 0.0),
            (10.21222368632829, 56.15326129528336, 0.0),
            (10.21133517191103, 56.15250091564997, 0.0),
            (10.21071653952973, 56.15187938686141, 0.0),
            (10.20834299265099, 56.15226137840068, 0.0),
            (10.20747567551576, 56.15116884425976, 0.0),
        ]
    )
