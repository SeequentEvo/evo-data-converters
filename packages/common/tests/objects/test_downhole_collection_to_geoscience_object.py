#  Copyright © 2025 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import pytest
import pandas as pd
import pyarrow as pa
from unittest.mock import Mock
from evo.data_converters.common.objects.downhole_collection import (
    DownholeCollection,
    IntervalTable as IntervalMeasurementTable,
    DistanceTable as DistanceMeasurementTable,
)
from evo.data_converters.common.objects.downhole_collection_to_geoscience_object import (
    DownholeCollectionToGeoscienceObject,
)


@pytest.fixture
def collars_df():
    """Common collars dataframe for testing."""
    return pd.DataFrame(
        {
            "hole_index": [1, 2],
            "hole_id": ["DH-001", "DH-002"],
            "x": [100.0, 200.0],
            "y": [500.0, 600.0],
            "z": [50.0, 55.0],
            "final_depth": [100.0, 150.0],
        }
    )


@pytest.fixture
def distance_measurements_df():
    """Common distance measurements dataframe."""
    return pd.DataFrame(
        {
            "hole_index": [1, 1, 1, 2, 2],
            "penetrationLength": [10.0, 20.0, 30.0, 15.0, 25.0],
            "density": [2.5, 2.6, 2.7, 2.4, 2.5],
            "porosity": [0.15, 0.18, 0.20, 0.12, 0.16],
        }
    )


@pytest.fixture
def interval_measurements_df():
    """Common interval measurements dataframe."""
    return pd.DataFrame(
        {
            "hole_index": [1, 1, 1, 2, 2],
            "SCPP_TOP": [0.0, 10.0, 20.0, 0.0, 15.0],
            "SCPP_BASE": [10.0, 20.0, 30.0, 15.0, 25.0],
            "lithology_code": [1, 2, 1, 3, 2],
            "grade": [0.5, 1.2, 0.8, 0.3, 1.5],
        }
    )


@pytest.fixture
def distance_table_mock(distance_measurements_df):
    """Mock distance measurement table."""
    mock = Mock(spec=DistanceMeasurementTable)
    mock.df = distance_measurements_df
    mock.get_depth_values.return_value = distance_measurements_df["penetrationLength"].tolist()
    mock.get_primary_column.return_value = "penetrationLength"
    mock.get_attribute_columns.return_value = ["density", "porosity"]
    mock.get_nan_values.return_value = []
    return mock


@pytest.fixture
def interval_table_mock(interval_measurements_df):
    """Mock interval measurement table."""
    mock = Mock(spec=IntervalMeasurementTable)
    mock.df = interval_measurements_df
    mock.get_from_column.return_value = "SCPP_TOP"
    mock.get_to_column.return_value = "SCPP_BASE"
    mock.get_attribute_columns.return_value = ["lithology_code", "grade"]
    mock.get_nan_values.return_value = []
    return mock


@pytest.fixture
def dhc_distance(collars_df, distance_table_mock):
    """Create a DownholeCollection mock with distance measurements."""
    collars_mock = Mock()
    collars_mock.df = collars_df
    collars_mock.get_attribute_column_names.return_value = []

    dhc_mock = Mock(spec=DownholeCollection)
    dhc_mock.name = "Test Distance Collection"
    dhc_mock.coordinate_reference_system = 32633
    dhc_mock.collars = collars_mock
    dhc_mock.get_bounding_box.return_value = [100.0, 200.0, 500.0, 600.0, 50.0, 55.0]
    dhc_mock.get_measurement_tables.return_value = [distance_table_mock]
    return dhc_mock


@pytest.fixture
def dhc_interval(collars_df, interval_table_mock, distance_table_mock):
    """Create a DownholeCollection mock with interval measurements."""
    collars_mock = Mock()
    collars_mock.df = collars_df
    collars_mock.get_attribute_column_names.return_value = []

    dhc_mock = Mock(spec=DownholeCollection)
    dhc_mock.name = "Test Interval Collection"
    dhc_mock.coordinate_reference_system = 32633
    dhc_mock.collars = collars_mock
    dhc_mock.get_bounding_box.return_value = [100.0, 200.0, 500.0, 600.0, 50.0, 55.0]

    # Mock to return interval for main loop but distance for path calculation
    def get_tables_side_effect(filter=None):
        if filter and DistanceMeasurementTable in filter:
            return [distance_table_mock]
        return [interval_table_mock]

    dhc_mock.get_measurement_tables.side_effect = get_tables_side_effect
    return dhc_mock


@pytest.fixture
def dhc_mixed(collars_df, distance_table_mock, interval_table_mock):
    """Create a DownholeCollection mock with both distance and interval measurements."""
    collars_mock = Mock()
    collars_mock.df = collars_df
    collars_mock.get_attribute_column_names.return_value = []

    dhc_mock = Mock(spec=DownholeCollection)
    dhc_mock.name = "Test Mixed Collection"
    dhc_mock.coordinate_reference_system = 32633
    dhc_mock.collars = collars_mock
    dhc_mock.get_bounding_box.return_value = [100.0, 200.0, 500.0, 600.0, 50.0, 55.0]
    dhc_mock.get_measurement_tables.return_value = [distance_table_mock, interval_table_mock]
    return dhc_mock


@pytest.fixture
def converter_distance(dhc_distance, mock_data_client):
    """Create a converter instance with distance measurements."""
    return DownholeCollectionToGeoscienceObject(dhc=dhc_distance, data_client=mock_data_client)


@pytest.fixture
def converter_interval(dhc_interval, mock_data_client):
    """Create a converter instance with interval measurements."""
    return DownholeCollectionToGeoscienceObject(dhc=dhc_interval, data_client=mock_data_client)


@pytest.fixture
def converter_mixed(dhc_mixed, mock_data_client):
    """Create a converter instance with mixed measurements."""
    return DownholeCollectionToGeoscienceObject(dhc=dhc_mixed, data_client=mock_data_client)


class TestConvert:
    def test_convert_creates_geoscience_object(self, converter_distance):
        result = converter_distance.convert()

        assert result is not None
        assert result.name == "Test Distance Collection"
        assert result.coordinate_reference_system.epsg_code == 32633
        assert result.bounding_box is not None
        assert result.location is not None
        assert result.collections is not None

    def test_convert_with_mixed_measurements(self, converter_mixed):
        result = converter_mixed.convert()

        assert result.name == "Test Mixed Collection"
        assert len(result.collections) == 2

    def test_convert_calls_data_client(self, converter_distance, mock_data_client):
        converter_distance.convert()

        assert mock_data_client.save_table.call_count >= 5


class TestCreateCoordinateReferenceSystem:
    def test_creates_epsg_crs(self, dhc_distance, mock_data_client) -> None:
        dhc_distance.coordinate_reference_system = 32633
        converter = DownholeCollectionToGeoscienceObject(dhc_distance, mock_data_client)

        crs = converter.create_coordinate_reference_system()

        assert crs.epsg_code == 32633

    def test_creates_wkt_crs(self, dhc_distance, mock_data_client) -> None:
        ogc_wkt_string = """
PROJCS["NZGD2000 / New Zealand Transverse Mercator 2000",
    GEOGCS["NZGD2000",
        DATUM["New Zealand Geodetic Datum 2000",
            SPHEROID["GRS 1980", 6378137, 298.257222101],
            TOWGS84[0,0,0,0,0,0,0]
        ],
        PRIMEM["Greenwich", 0],
        UNIT["degree", 0.0174532925199433],
        AUTHORITY["EPSG","4167"]
    ],
    PROJECTION["Transverse_Mercator"],
    PARAMETER["latitude_of_origin", 0],
    PARAMETER["central_meridian", 173],
    PARAMETER["scale_factor", 0.9996],
    PARAMETER["false_easting", 1600000],
    PARAMETER["false_northing", 10000000],
    UNIT["metre",1],
    AUTHORITY["EPSG","2193"]
]
"""
        expected_ogc_wkt = """BOUNDCRS[SOURCECRS[PROJCRS["NZGD2000 / New Zealand Transverse Mercator 2000",BASEGEOGCRS["NZGD2000",DATUM["New Zealand Geodetic Datum 2000",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4167]],CONVERSION["unnamed",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",173,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",1600000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",10000000,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],ID["EPSG",2193]]],TARGETCRS[GEOGCRS["WGS 84",DATUM["World Geodetic System 1984",ELLIPSOID["WGS 84",6378137,298.257223563,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],CS[ellipsoidal,2],AXIS["latitude",north,ORDER[1],ANGLEUNIT["degree",0.0174532925199433]],AXIS["longitude",east,ORDER[2],ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4326]]],ABRIDGEDTRANSFORMATION["Transformation from NZGD2000 to WGS84",METHOD["Position Vector transformation (geog2D domain)",ID["EPSG",9606]],PARAMETER["X-axis translation",0,ID["EPSG",8605]],PARAMETER["Y-axis translation",0,ID["EPSG",8606]],PARAMETER["Z-axis translation",0,ID["EPSG",8607]],PARAMETER["X-axis rotation",0,ID["EPSG",8608]],PARAMETER["Y-axis rotation",0,ID["EPSG",8609]],PARAMETER["Z-axis rotation",0,ID["EPSG",8610]],PARAMETER["Scale difference",1,ID["EPSG",8611]]]]"""

        dhc_distance.coordinate_reference_system = ogc_wkt_string
        converter = DownholeCollectionToGeoscienceObject(dhc_distance, mock_data_client)

        crs = converter.create_coordinate_reference_system()

        assert crs.ogc_wkt == expected_ogc_wkt

    def test_creates_unspecified_crs_from_none(self, dhc_distance, mock_data_client) -> None:
        dhc_distance.coordinate_reference_system = None
        converter = DownholeCollectionToGeoscienceObject(dhc_distance, mock_data_client)

        crs = converter.create_coordinate_reference_system()

        assert crs == "unspecified"


class TestCreateBoundingBox:
    def test_creates_bounding_box_from_collar_data(self, converter_distance) -> None:
        bbox = converter_distance.create_bounding_box()

        assert bbox.min_x == 100.0
        assert bbox.max_x == 200.0
        assert bbox.min_y == 500.0
        assert bbox.max_y == 600.0
        assert bbox.min_z == 50.0
        assert bbox.max_z == 55.0


class TestCreateDhcLocation:
    def test_creates_location_with_all_components(self, converter_distance) -> None:
        location = converter_distance.create_dhc_location()

        assert location.coordinates is not None
        assert location.distances is not None
        assert location.holes is not None
        assert location.hole_id is not None
        assert location.path is not None


class TestCreateDhcLocationAttributes:
    def test_returns_none_when_no_attributes(self, converter_distance) -> None:
        result = converter_distance.create_dhc_location_attributes()

        assert result is None or result == []

    def test_creates_attributes_when_present(self, dhc_distance, mock_data_client) -> None:
        dhc_distance.collars.get_attribute_column_names.return_value = ["wind_speed"]
        dhc_distance.collars.df["wind_speed"] = [5.5, 6.5]
        converter = DownholeCollectionToGeoscienceObject(dhc_distance, mock_data_client)

        result = converter.create_dhc_location_attributes()

        assert result is not None


class TestCreateDhcLocationCoordinates:
    def test_creates_float_array_3(self, converter_distance) -> None:
        coordinates = converter_distance.create_dhc_location_coordinates()

        assert coordinates is not None
        assert coordinates.length == 2


class TestCreateDhcLocationDistances:
    def test_creates_distances_float_array_3(self, converter_distance) -> None:
        distances = converter_distance.create_dhc_location_distances()

        assert distances is not None
        assert distances.length == 2


class TestCreateDhcHoleChunks:
    def test_creates_hole_chunks(self, converter_distance, distance_table_mock) -> None:
        chunks = converter_distance.create_dhc_hole_chunks(distance_table_mock)

        assert chunks is not None
        assert chunks.length == 2


class TestCreateDhcLocationHoleId:
    def test_creates_category_data(self, converter_distance) -> None:
        hole_id = converter_distance.create_dhc_location_hole_id()

        assert hole_id is not None
        assert hole_id.table is not None
        assert hole_id.values is not None


class TestCreateDhcLocationPath:
    def test_creates_direction_vector(self, converter_distance) -> None:
        path = converter_distance.create_dhc_location_path()

        assert path is not None
        assert path.length == 5  # Total measurements


class TestCreateDhcCollections:
    def test_creates_distance_collection(self, converter_distance) -> None:
        collections = converter_distance.create_dhc_collections()

        assert len(collections) == 1
        assert hasattr(collections[0], "distance")

    def test_creates_mixed_collections(self, converter_mixed) -> None:
        collections = converter_mixed.create_dhc_collections()

        assert len(collections) == 2
        assert hasattr(collections[0], "distance")
        assert hasattr(collections[1], "from_to")


class TestCreateDhcCollectionDistance:
    def test_creates_distance_table_with_attributes(self, converter_distance, distance_table_mock) -> None:
        distance_collection = converter_distance.create_dhc_collection_distance(distance_table_mock)

        assert distance_collection.name == "distances"
        assert distance_collection.distance is not None
        assert distance_collection.distance.values is not None
        assert distance_collection.holes is not None


class TestCreateCollectionAttributes:
    def test_returns_none_when_no_attributes(self, converter_distance, distance_table_mock) -> None:
        distance_table_mock.get_attribute_columns.return_value = []

        result = converter_distance.create_collection_attributes(distance_table_mock)

        assert result is None or result == []

    def test_creates_attributes_for_measurements(self, converter_distance, distance_table_mock) -> None:
        result = converter_distance.create_collection_attributes(distance_table_mock)

        assert result is not None
        assert len(result) > 0


class TestCoordinatesTable:
    def test_creates_table_with_xyz_columns(self, converter_distance) -> None:
        table = converter_distance.coordinates_table()

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert set(table.column_names) == {"x", "y", "z"}
        assert table.schema.field("x").type == pa.float64()

    def test_contains_correct_coordinate_values(self, converter_distance) -> None:
        table = converter_distance.coordinates_table()

        x_values = table.column("x").to_pylist()
        y_values = table.column("y").to_pylist()
        z_values = table.column("z").to_pylist()

        assert x_values == [100.0, 200.0]
        assert y_values == [500.0, 600.0]
        assert z_values == [50.0, 55.0]


class TestDistancesTable:
    def test_creates_table_with_distance_columns(self, converter_distance) -> None:
        table = converter_distance.distances_table()

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert set(table.column_names) == {"final", "target", "current"}

    def test_all_columns_use_final_depth(self, converter_distance) -> None:
        table = converter_distance.distances_table()

        final = table.column("final").to_pylist()
        target = table.column("target").to_pylist()
        current = table.column("current").to_pylist()

        assert final == target == current == [100.0, 150.0]


class TestHolesTable:
    def test_creates_table_with_correct_schema(self, converter_distance, distance_table_mock) -> None:
        table = converter_distance.holes_table(distance_table_mock)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert set(table.column_names) == {"hole_index", "offset", "count"}
        assert table.schema.field("hole_index").type == pa.int32()
        assert table.schema.field("offset").type == pa.uint64()
        assert table.schema.field("count").type == pa.uint64()

    def test_calculates_correct_offsets_and_counts(self, converter_distance, distance_table_mock) -> None:
        table = converter_distance.holes_table(distance_table_mock)

        hole_indices = table.column("hole_index").to_pylist()
        counts = table.column("count").to_pylist()
        offsets = table.column("offset").to_pylist()

        assert hole_indices == [1, 2]
        assert counts == [3, 2]
        assert offsets == [0, 3]

    def test_handles_unequal_measurements_per_hole(self, converter_distance, distance_measurements_df) -> None:
        # Add more measurements for hole 2
        extended_df = pd.concat(
            [
                distance_measurements_df,
                pd.DataFrame(
                    {
                        "hole_index": [2, 2],
                        "penetrationLength": [35.0, 45.0],
                        "density": [2.7, 2.8],
                        "porosity": [0.18, 0.19],
                    }
                ),
            ],
            ignore_index=True,
        )

        mock_table = Mock(spec=DistanceMeasurementTable)
        mock_table.df = extended_df

        table = converter_distance.holes_table(mock_table)
        counts = table.column("count").to_pylist()
        offsets = table.column("offset").to_pylist()

        assert counts == [3, 4]
        assert offsets == [0, 3]


class TestHoleIdTables:
    def test_creates_lookup_and_index_tables(self, converter_distance) -> None:
        lookup_table, integer_array_table = converter_distance.hole_id_tables()

        assert isinstance(lookup_table, pa.Table)
        assert isinstance(integer_array_table, pa.Table)

    def test_lookup_table_has_correct_schema(self, converter_distance) -> None:
        lookup_table, _ = converter_distance.hole_id_tables()

        assert set(lookup_table.column_names) == {"key", "value"}
        assert lookup_table.schema.field("key").type == pa.int32()
        assert lookup_table.schema.field("value").type == pa.string()

    def test_lookup_table_maps_correctly(self, converter_distance) -> None:
        lookup_table, _ = converter_distance.hole_id_tables()

        keys = lookup_table.column("key").to_pylist()
        values = lookup_table.column("value").to_pylist()

        assert keys == [1, 2]
        assert values == ["DH-001", "DH-002"]


class TestPathTable:
    def test_creates_table_with_correct_schema(self, converter_distance) -> None:
        table = converter_distance.path_table()

        assert isinstance(table, pa.Table)
        assert table.num_rows == 5
        assert set(table.column_names) == {"distance", "azimuth", "dip"}

    def test_assumes_vertical_holes(self, converter_distance) -> None:
        table = converter_distance.path_table()

        azimuth_values = table.column("azimuth").to_pylist()
        dip_values = table.column("dip").to_pylist()

        assert all(az == 0.0 for az in azimuth_values)
        assert all(dip == 90.0 for dip in dip_values)

    def test_uses_depth_values_for_distance(self, converter_distance) -> None:
        table = converter_distance.path_table()

        distances = table.column("distance").to_pylist()

        assert distances == [10.0, 20.0, 30.0, 15.0, 25.0]


class TestCollectionDistancesTable:
    def test_creates_table_with_values_column(self, converter_distance, distance_table_mock) -> None:
        table = converter_distance.collection_distances_table(distance_table_mock)

        assert isinstance(table, pa.Table)
        assert "values" in table.column_names

    def test_contains_correct_distance_values(self, converter_distance, distance_table_mock) -> None:
        table = converter_distance.collection_distances_table(distance_table_mock)

        values = table.column("values").to_pylist()

        assert values == [10.0, 20.0, 30.0, 15.0, 25.0]


class TestCollectionStartEndTable:
    def test_creates_table_with_from_to_columns(self, converter_interval, interval_table_mock) -> None:
        table = converter_interval.collection_start_end_table(interval_table_mock)

        assert isinstance(table, pa.Table)
        assert set(table.column_names) == {"from", "to"}
        assert table.num_rows == 5

    def test_contains_correct_interval_values(self, converter_interval, interval_table_mock) -> None:
        table = converter_interval.collection_start_end_table(interval_table_mock)

        from_values = table.column("from").to_pylist()
        to_values = table.column("to").to_pylist()

        assert from_values == [0.0, 10.0, 20.0, 0.0, 15.0]
        assert to_values == [10.0, 20.0, 30.0, 15.0, 25.0]


class TestGetFirstDistanceMeasurementTable:
    def test_returns_first_distance_table(self, converter_distance, distance_table_mock) -> None:
        result = converter_distance.get_first_distance_measurement_table()

        assert result == distance_table_mock

    def test_raises_error_when_no_distance_table(self, dhc_interval, mock_data_client) -> None:
        # Mock to never return distance tables
        dhc_interval.get_measurement_tables = Mock()
        dhc_interval.get_measurement_tables.return_value = []
        converter = DownholeCollectionToGeoscienceObject(dhc_interval, mock_data_client)

        with pytest.raises(ValueError, match="No distance measurement tables found"):
            converter.get_first_distance_measurement_table()


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_single_hole_single_measurement(self, mock_data_client) -> None:
        collars_df = pd.DataFrame(
            {
                "hole_index": [1],
                "hole_id": ["DH-001"],
                "x": [100.0],
                "y": [500.0],
                "z": [50.0],
                "final_depth": [100.0],
            }
        )

        distance_df = pd.DataFrame(
            {
                "hole_index": [1],
                "penetrationLength": [10.0],
                "density": [2.5],
            }
        )

        collars_mock = Mock()
        collars_mock.df = collars_df
        collars_mock.get_attribute_column_names.return_value = []

        distance_mock = Mock(spec=DistanceMeasurementTable)
        distance_mock.df = distance_df
        distance_mock.get_depth_values.return_value = [10.0]
        distance_mock.get_primary_column.return_value = "penetrationLength"
        distance_mock.get_attribute_columns.return_value = ["density"]
        distance_mock.get_nan_values.return_value = []

        dhc_mock = Mock(spec=DownholeCollection)
        dhc_mock.name = "Minimal"
        dhc_mock.coordinate_reference_system = 4326
        dhc_mock.collars = collars_mock
        dhc_mock.get_bounding_box.return_value = [100.0, 100.0, 500.0, 500.0, 50.0, 50.0]
        dhc_mock.get_measurement_tables.return_value = [distance_mock]

        converter = DownholeCollectionToGeoscienceObject(dhc_mock, mock_data_client)
        result = converter.convert()

        assert result is not None
        assert result.name == "Minimal"

    def test_multiple_holes_varying_measurement_counts(self, mock_data_client) -> None:
        collars_df = pd.DataFrame(
            {
                "hole_index": [1, 2, 3],
                "hole_id": ["DH-001", "DH-002", "DH-003"],
                "x": [100.0, 200.0, 300.0],
                "y": [500.0, 600.0, 700.0],
                "z": [50.0, 55.0, 60.0],
                "final_depth": [100.0, 150.0, 120.0],
            }
        )

        distance_df = pd.DataFrame(
            {
                "hole_index": [1, 2, 2, 2, 3],
                "penetrationLength": [10.0, 15.0, 25.0, 35.0, 20.0],
                "density": [2.5, 2.4, 2.5, 2.6, 2.3],
            }
        )

        collars_mock = Mock()
        collars_mock.df = collars_df
        collars_mock.get_attribute_column_names.return_value = []

        distance_mock = Mock(spec=DistanceMeasurementTable)
        distance_mock.df = distance_df
        distance_mock.get_depth_values.return_value = distance_df["penetrationLength"].tolist()
        distance_mock.get_primary_column.return_value = "penetrationLength"
        distance_mock.get_attribute_columns.return_value = ["density"]

        dhc_mock = Mock(spec=DownholeCollection)
        dhc_mock.name = "Unequal"
        dhc_mock.coordinate_reference_system = 4326
        dhc_mock.collars = collars_mock
        dhc_mock.get_bounding_box.return_value = [100.0, 300.0, 500.0, 700.0, 50.0, 60.0]
        dhc_mock.get_measurement_tables.return_value = [distance_mock]

        converter = DownholeCollectionToGeoscienceObject(dhc_mock, mock_data_client)
        holes_table = converter.holes_table(distance_mock)

        counts = holes_table.column("count").to_pylist()
        offsets = holes_table.column("offset").to_pylist()

        assert counts == [1, 3, 1]
        assert offsets == [0, 1, 4]
