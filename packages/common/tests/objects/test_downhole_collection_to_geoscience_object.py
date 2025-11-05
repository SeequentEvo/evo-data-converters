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
from unittest.mock import Mock, MagicMock
from evo.data_converters.common.objects.downhole_collection import (
    DownholeCollection,
    IntervalTable as IntervalMeasurementTable,
    DistanceTable as DistanceMeasurementTable,
)
from evo.data_converters.common.objects.downhole_collection_to_geoscience_object import (
    DownholeCollectionToGeoscienceObject,
)


@pytest.fixture
def mock_data_client():
    """Create a mock ObjectDataClient that returns valid schemas for different table types."""
    client = Mock()

    def save_table_side_effect(table):
        """Return appropriate schema based on table structure."""
        num_rows = table.num_rows
        column_names = set(table.column_names)

        # LookupTable: has 'key' and 'value' columns
        if column_names == {"key", "value"}:
            return {
                "data": None,
                "length": num_rows,
                "keys_data_type": "int32",
                "values_data_type": "string",
            }

        # FloatArray2: has 'from' and 'to' columns (for intervals)
        if column_names == {"from", "to"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # FloatArray3: has 'x', 'y', 'z' columns OR 'final', 'target', 'current'
        if column_names == {"x", "y", "z"} or column_names == {"final", "target", "current"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # DownholeDirectionVector: has 'distance', 'azimuth', 'dip' columns
        if column_names == {"distance", "azimuth", "dip"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # HoleChunks: has 'hole_index', 'offset', 'count' columns
        if column_names == {"hole_index", "offset", "count"}:
            return {
                "data": None,
                "length": num_rows,
            }

        # IntegerArray1: single 'data' column with int type
        if column_names == {"data"} and table.schema.field("data").type in (pa.int32(), pa.int64()):
            dtype_str = "int32" if table.schema.field("data").type == pa.int32() else "int64"
            return {
                "data": None,
                "length": num_rows,
                "data_type": dtype_str,
            }

        # FloatArray1: single column ('values' or 'data')
        if column_names == {"values"} or (column_names == {"data"} and table.schema.field("data").type == pa.float64()):
            return {
                "data": None,
                "length": num_rows,
            }

        # Default for any other array types
        return {
            "data": None,
            "length": num_rows,
        }

    client.save_table = MagicMock(side_effect=save_table_side_effect)
    return client


@pytest.fixture
def sample_dhc_distance():
    """Create a sample DownholeCollection with distance-based measurements for testing."""
    collars_df = pd.DataFrame(
        {
            "hole_index": [1, 2],
            "hole_id": ["DH-001", "DH-002"],
            "x": [100.0, 200.0],
            "y": [500.0, 600.0],
            "z": [50.0, 55.0],
            "final_depth": [100.0, 150.0],
        }
    )

    distance_measurements_df = pd.DataFrame(
        {
            "hole_index": [1, 1, 1, 2, 2],
            "penetrationLength": [10.0, 20.0, 30.0, 15.0, 25.0],
            "density": [2.5, 2.6, 2.7, 2.4, 2.5],
            "porosity": [0.15, 0.18, 0.20, 0.12, 0.16],
        }
    )

    # Create mock collars and distance table objects
    collars_mock = Mock()
    collars_mock.df = collars_df

    distance_table_mock = Mock(spec=DistanceMeasurementTable)
    distance_table_mock.df = distance_measurements_df
    distance_table_mock.get_depth_values.return_value = distance_measurements_df["penetrationLength"].tolist()
    distance_table_mock.get_primary_column.return_value = "penetrationLength"
    distance_table_mock.get_attribute_columns.return_value = ["density", "porosity"]

    dhc_mock = Mock(spec=DownholeCollection)
    dhc_mock.name = "Test Distance Collection"
    dhc_mock.coordinate_reference_system = 32633
    dhc_mock.collars = collars_mock
    dhc_mock.get_bounding_box.return_value = [100.0, 200.0, 500.0, 600.0, 50.0, 55.0]
    dhc_mock.get_measurement_tables.return_value = [distance_table_mock]
    dhc_mock.nan_values_by_attribute = {}

    return dhc_mock


@pytest.fixture
def sample_dhc_interval():
    """Create a sample DownholeCollection with interval-based measurements for testing."""
    collars_df = pd.DataFrame(
        {
            "hole_index": [1, 2],
            "hole_id": ["DH-001", "DH-002"],
            "x": [100.0, 200.0],
            "y": [500.0, 600.0],
            "z": [50.0, 55.0],
            "final_depth": [100.0, 150.0],
        }
    )

    interval_measurements_df = pd.DataFrame(
        {
            "hole_index": [1, 1, 1, 2, 2],
            "SCPP_TOP": [0.0, 10.0, 20.0, 0.0, 15.0],
            "SCPP_BASE": [10.0, 20.0, 30.0, 15.0, 25.0],
            "lithology_code": [1, 2, 1, 3, 2],
            "grade": [0.5, 1.2, 0.8, 0.3, 1.5],
        }
    )

    # Create mock collars and interval table objects
    collars_mock = Mock()
    collars_mock.df = collars_df

    interval_table_mock = Mock(spec=IntervalMeasurementTable)
    interval_table_mock.df = interval_measurements_df
    interval_table_mock.get_from_column.return_value = "SCPP_TOP"
    interval_table_mock.get_to_column.return_value = "SCPP_BASE"
    interval_table_mock.get_attribute_columns.return_value = ["lithology_code", "grade"]

    dhc_mock = Mock(spec=DownholeCollection)
    dhc_mock.name = "Test Interval Collection"
    dhc_mock.coordinate_reference_system = 32633
    dhc_mock.collars = collars_mock
    dhc_mock.get_bounding_box.return_value = [100.0, 200.0, 500.0, 600.0, 50.0, 55.0]
    dhc_mock.get_measurement_tables.return_value = [interval_table_mock]
    dhc_mock.nan_values_by_attribute = {}

    return dhc_mock


@pytest.fixture
def sample_dhc_mixed():
    """Create a sample DownholeCollection with both distance and interval measurements."""
    collars_df = pd.DataFrame(
        {
            "hole_index": [1, 2],
            "hole_id": ["DH-001", "DH-002"],
            "x": [100.0, 200.0],
            "y": [500.0, 600.0],
            "z": [50.0, 55.0],
            "final_depth": [100.0, 150.0],
        }
    )

    distance_measurements_df = pd.DataFrame(
        {
            "hole_index": [1, 1, 1, 2, 2],
            "penetrationLength": [10.0, 20.0, 30.0, 15.0, 25.0],
            "density": [2.5, 2.6, 2.7, 2.4, 2.5],
        }
    )

    interval_measurements_df = pd.DataFrame(
        {
            "hole_index": [1, 1, 2],
            "SCPP_TOP": [0.0, 20.0, 0.0],
            "SCPP_BASE": [20.0, 30.0, 15.0],
            "lithology": [1, 2, 1],
        }
    )

    # Create mock collars and table objects
    collars_mock = Mock()
    collars_mock.df = collars_df

    distance_table_mock = Mock(spec=DistanceMeasurementTable)
    distance_table_mock.df = distance_measurements_df
    distance_table_mock.get_depth_values.return_value = distance_measurements_df["penetrationLength"].tolist()
    distance_table_mock.get_primary_column.return_value = "penetrationLength"
    distance_table_mock.get_attribute_columns.return_value = ["density"]

    interval_table_mock = Mock(spec=IntervalMeasurementTable)
    interval_table_mock.df = interval_measurements_df
    interval_table_mock.get_from_column.return_value = "SCPP_TOP"
    interval_table_mock.get_to_column.return_value = "SCPP_BASE"
    interval_table_mock.get_attribute_columns.return_value = ["lithology"]

    dhc_mock = Mock(spec=DownholeCollection)
    dhc_mock.name = "Test Mixed Collection"
    dhc_mock.coordinate_reference_system = 32633
    dhc_mock.collars = collars_mock
    dhc_mock.get_bounding_box.return_value = [100.0, 200.0, 500.0, 600.0, 50.0, 55.0]
    dhc_mock.get_measurement_tables.return_value = [distance_table_mock, interval_table_mock]
    dhc_mock.nan_values_by_attribute = {}

    return dhc_mock


@pytest.fixture
def converter_distance(sample_dhc_distance, mock_data_client):
    """Create a converter instance with distance measurements."""
    return DownholeCollectionToGeoscienceObject(
        dhc=sample_dhc_distance,
        data_client=mock_data_client,
    )


@pytest.fixture
def converter_interval(sample_dhc_interval, mock_data_client):
    """Create a converter instance with interval measurements."""
    return DownholeCollectionToGeoscienceObject(
        dhc=sample_dhc_interval,
        data_client=mock_data_client,
    )


@pytest.fixture
def converter_mixed(sample_dhc_mixed, mock_data_client):
    """Create a converter instance with mixed measurements."""
    return DownholeCollectionToGeoscienceObject(
        dhc=sample_dhc_mixed,
        data_client=mock_data_client,
    )


class TestConvert:
    def test_convert_creates_geoscience_object_distance(self, converter_distance):
        """Test that convert() creates a DownholeCollectionGo object with distance data."""
        result = converter_distance.convert()

        assert result is not None
        assert result.name == "Test Distance Collection"
        assert result.coordinate_reference_system.epsg_code == 32633
        assert result.bounding_box is not None

    def test_convert_creates_geoscience_object_mixed(self, converter_mixed):
        """Test that convert() creates a DownholeCollectionGo object with mixed data."""
        result = converter_mixed.convert()

        assert result is not None
        assert result.name == "Test Mixed Collection"
        assert len(result.collections) == 2  # One distance, one interval

    def test_convert_calls_data_client(self, converter_distance, mock_data_client):
        """Test that convert() saves data via the data client."""
        converter_distance.convert()

        # Should save multiple tables (coordinates, distances, holes, etc.)
        assert mock_data_client.save_table.call_count >= 5

    def test_convert_with_wkt_crs(self, sample_dhc_distance, mock_data_client):
        """Test conversion with WKT coordinate reference system."""
        sample_dhc_distance.coordinate_reference_system = 'PROJCS["WGS 84 / UTM zone 33N"]'
        converter = DownholeCollectionToGeoscienceObject(sample_dhc_distance, mock_data_client)

        result = converter.convert()

        assert result is not None
        assert result.coordinate_reference_system.ogc_wkt == 'PROJCS["WGS 84 / UTM zone 33N"]'


class TestBoundingBox:
    def test_create_bounding_box(self, converter_distance):
        """Test bounding box creation from collar data."""
        bbox = converter_distance.create_bounding_box()

        assert bbox.min_x == 100.0
        assert bbox.max_x == 200.0
        assert bbox.min_y == 500.0
        assert bbox.max_y == 600.0
        assert bbox.min_z == 50.0
        assert bbox.max_z == 55.0


class TestCoordinatesTables:
    def test_coordinates_table_structure(self, converter_distance):
        """Test coordinates table has correct schema and data."""
        table = converter_distance.coordinates_table()

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert table.num_columns == 3
        assert set(table.column_names) == {"x", "y", "z"}

        # Check data types
        assert table.schema.field("x").type == pa.float64()
        assert table.schema.field("y").type == pa.float64()
        assert table.schema.field("z").type == pa.float64()

    def test_coordinates_table_values(self, converter_distance):
        """Test coordinates table contains correct values."""
        table = converter_distance.coordinates_table()

        x_values = table.column("x").to_pylist()
        y_values = table.column("y").to_pylist()
        z_values = table.column("z").to_pylist()

        assert x_values == [100.0, 200.0]
        assert y_values == [500.0, 600.0]
        assert z_values == [50.0, 55.0]


class TestDistancesTables:
    def test_distances_table_structure(self, converter_distance):
        """Test distances table has correct schema."""
        table = converter_distance.distances_table()

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert set(table.column_names) == {"final", "target", "current"}

    def test_distances_table_uses_final_depth(self, converter_distance):
        """Test that all distance columns use final_depth values."""
        table = converter_distance.distances_table()

        final_values = table.column("final").to_pylist()
        target_values = table.column("target").to_pylist()
        current_values = table.column("current").to_pylist()

        assert final_values == [100.0, 150.0]
        assert target_values == [100.0, 150.0]
        assert current_values == [100.0, 150.0]


class TestHolesTables:
    def test_holes_table_structure_distance(self, converter_distance, sample_dhc_distance):
        """Test holes table has correct schema and indexing for distance measurements."""
        measurement_table = sample_dhc_distance.get_measurement_tables()[0]
        table = converter_distance.holes_table(measurement_table)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert set(table.column_names) == {"hole_index", "offset", "count"}

        # Check data types
        assert table.schema.field("hole_index").type == pa.int32()
        assert table.schema.field("offset").type == pa.uint64()
        assert table.schema.field("count").type == pa.uint64()

    def test_holes_table_counts_measurements_distance(self, converter_distance, sample_dhc_distance):
        """Test that holes table correctly counts measurements per hole."""
        measurement_table = sample_dhc_distance.get_measurement_tables()[0]
        table = converter_distance.holes_table(measurement_table)

        hole_indices = table.column("hole_index").to_pylist()
        counts = table.column("count").to_pylist()
        offsets = table.column("offset").to_pylist()

        assert hole_indices == [1, 2]
        assert counts == [3, 2]  # 3 measurements for hole 1, 2 for hole 2
        assert offsets == [0, 3]  # hole 1 starts at 0, hole 2 starts at 3

    def test_holes_table_counts_measurements_interval(self, converter_interval, sample_dhc_interval):
        """Test that holes table correctly counts interval measurements per hole."""
        measurement_table = sample_dhc_interval.get_measurement_tables()[0]
        table = converter_interval.holes_table(measurement_table)

        hole_indices = table.column("hole_index").to_pylist()
        counts = table.column("count").to_pylist()
        offsets = table.column("offset").to_pylist()

        assert hole_indices == [1, 2]
        assert counts == [3, 2]  # 3 intervals for hole 1, 2 for hole 2
        assert offsets == [0, 3]  # hole 1 starts at 0, hole 2 starts at 3


class TestHoleIdTables:
    def test_hole_id_tables_structure(self, converter_distance):
        """Test hole id lookup and index tables."""
        lookup_table, integer_array_table = converter_distance.hole_id_tables()

        # Check lookup table
        assert isinstance(lookup_table, pa.Table)
        assert set(lookup_table.column_names) == {"key", "value"}
        assert lookup_table.schema.field("key").type == pa.int32()
        assert lookup_table.schema.field("value").type == pa.string()

        # Check integer array table
        assert isinstance(integer_array_table, pa.Table)
        assert set(integer_array_table.column_names) == {"data"}

    def test_hole_id_mapping(self, converter_distance):
        """Test that hole IDs are correctly mapped to indices."""
        lookup_table, _ = converter_distance.hole_id_tables()

        keys = lookup_table.column("key").to_pylist()
        values = lookup_table.column("value").to_pylist()

        assert keys == [1, 2]
        assert values == ["DH-001", "DH-002"]


class TestPathTable:
    def test_path_table_structure(self, converter_distance):
        """Test path table has correct schema."""
        table = converter_distance.path_table()

        assert isinstance(table, pa.Table)
        assert table.num_rows == 5  # Total measurements
        assert set(table.column_names) == {"distance", "azimuth", "dip"}

    def test_path_table_assumes_vertical(self, converter_distance):
        """Test that path table assumes vertical holes."""
        table = converter_distance.path_table()

        azimuth_values = table.column("azimuth").to_pylist()
        dip_values = table.column("dip").to_pylist()

        # All holes assumed vertical
        assert all(az == 0.0 for az in azimuth_values)
        assert all(dip == 90.0 for dip in dip_values)

    def test_path_table_uses_depth_values(self, converter_distance):
        """Test that distance values come from depth column."""
        table = converter_distance.path_table()

        distances = table.column("distance").to_pylist()
        expected = [10.0, 20.0, 30.0, 15.0, 25.0]

        assert distances == expected


class TestCollectionDistanceAttributes:
    def test_collection_distances_table(self, converter_distance, sample_dhc_distance):
        """Test collection distances table creation."""
        measurement_table = sample_dhc_distance.get_measurement_tables()[0]
        table = converter_distance.collection_distances_table(measurement_table)

        assert isinstance(table, pa.Table)
        assert "values" in table.column_names

        values = table.column("values").to_pylist()
        expected = [10.0, 20.0, 30.0, 15.0, 25.0]
        assert values == expected

    def test_collection_attribute_tables_distance(self, converter_distance, sample_dhc_distance):
        """Test attribute tables are created for each measurement column."""
        measurement_table = sample_dhc_distance.get_measurement_tables()[0]
        attribute_tables = converter_distance.collection_attribute_tables(measurement_table)

        # Should have tables for density and porosity
        assert "density" in attribute_tables
        assert "porosity" in attribute_tables
        assert len(attribute_tables) == 2

        # Check density values
        density_table = attribute_tables["density"]
        density_values = density_table.column("data").to_pylist()
        assert density_values == [2.5, 2.6, 2.7, 2.4, 2.5]

        # Check porosity values
        porosity_table = attribute_tables["porosity"]
        porosity_values = porosity_table.column("data").to_pylist()
        assert porosity_values == [0.15, 0.18, 0.20, 0.12, 0.16]


class TestCollectionIntervalAttributes:
    def test_collection_start_end_table(self, converter_interval, sample_dhc_interval):
        """Test collection start/end interval table creation."""
        measurement_table = sample_dhc_interval.get_measurement_tables()[0]
        table = converter_interval.collection_start_end_table(measurement_table)

        assert isinstance(table, pa.Table)
        assert set(table.column_names) == {"from", "to"}
        assert table.num_rows == 5

        from_values = table.column("from").to_pylist()
        to_values = table.column("to").to_pylist()

        assert from_values == [0.0, 10.0, 20.0, 0.0, 15.0]
        assert to_values == [10.0, 20.0, 30.0, 15.0, 25.0]

    def test_collection_attribute_tables_interval(self, converter_interval, sample_dhc_interval):
        """Test attribute tables are created for interval measurements."""
        measurement_table = sample_dhc_interval.get_measurement_tables()[0]
        attribute_tables = converter_interval.collection_attribute_tables(measurement_table)

        # Should have tables for lithology_code and grade
        assert "lithology_code" in attribute_tables
        assert "grade" in attribute_tables
        assert len(attribute_tables) == 2

        # Check lithology_code values
        lithology_table = attribute_tables["lithology_code"]
        lithology_values = lithology_table.column("data").to_pylist()
        assert lithology_values == [1, 2, 1, 3, 2]

        # Check grade values
        grade_table = attribute_tables["grade"]
        grade_values = grade_table.column("data").to_pylist()
        assert grade_values == [0.5, 1.2, 0.8, 0.3, 1.5]


class TestLocationCreation:
    def test_create_dhc_location(self, converter_distance):
        """Test that DHC location is created with all required components."""
        location = converter_distance.create_dhc_location()

        assert location is not None
        assert location.coordinates is not None
        assert location.distances is not None
        assert location.holes is not None
        assert location.hole_id is not None
        assert location.path is not None


class TestCollectionsCreation:
    def test_create_dhc_collections_distance(self, converter_distance):
        """Test that DHC collections are created for distance measurements."""
        collections = converter_distance.create_dhc_collections()

        assert isinstance(collections, list)
        assert len(collections) == 1
        # Check it's a distance table type
        assert hasattr(collections[0], "distance")

    def test_create_dhc_collections_interval(self, converter_interval):
        """Test that DHC collections are created for interval measurements."""
        collections = converter_interval.create_dhc_collections()

        assert isinstance(collections, list)
        assert len(collections) == 1
        # Check it's an interval table type
        assert hasattr(collections[0], "from_to")

    def test_create_dhc_collections_mixed(self, converter_mixed):
        """Test that DHC collections are created for mixed measurements."""
        collections = converter_mixed.create_dhc_collections()

        assert isinstance(collections, list)
        assert len(collections) == 2

        # First should be distance, second should be interval
        assert hasattr(collections[0], "distance")
        assert hasattr(collections[1], "from_to")

    def test_create_dhc_collection_distance(self, converter_distance, sample_dhc_distance):
        """Test distance collection creation includes attributes."""
        measurement_table = sample_dhc_distance.get_measurement_tables()[0]
        distance = converter_distance.create_dhc_collection_distance(measurement_table)

        assert distance is not None
        assert distance.name == "distances"
        assert distance.distance is not None
        assert distance.distance.values is not None
        assert len(distance.distance.attributes) == 2  # density and porosity

    def test_create_dhc_collection_interval(self, converter_interval, sample_dhc_interval):
        """Test interval collection creation includes attributes."""
        measurement_table = sample_dhc_interval.get_measurement_tables()[0]
        interval = converter_interval.create_dhc_collection_interval(measurement_table)

        assert interval is not None
        assert interval.name == "intervals"
        assert interval.from_to is not None
        assert interval.from_to.intervals is not None
        assert interval.from_to.intervals.start_and_end is not None
        assert len(interval.from_to.attributes) == 2  # lithology_code and grade


class TestEdgeCases:
    def test_single_hole_single_measurement_distance(self, mock_data_client):
        """Test conversion with minimal distance data."""
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

        distance_measurements_df = pd.DataFrame(
            {
                "hole_index": [1],
                "penetrationLength": [10.0],
                "density": [2.5],
            }
        )

        collars_mock = Mock()
        collars_mock.df = collars_df

        distance_table_mock = Mock(spec=DistanceMeasurementTable)
        distance_table_mock.df = distance_measurements_df
        distance_table_mock.get_depth_values.return_value = [10.0]
        distance_table_mock.get_primary_column.return_value = "penetrationLength"
        distance_table_mock.get_attribute_columns.return_value = ["density"]

        dhc_mock = Mock(spec=DownholeCollection)
        dhc_mock.name = "Minimal Distance"
        dhc_mock.coordinate_reference_system = 4326
        dhc_mock.collars = collars_mock
        dhc_mock.get_bounding_box.return_value = [100.0, 100.0, 500.0, 500.0, 50.0, 50.0]
        dhc_mock.get_measurement_tables.return_value = [distance_table_mock]
        dhc_mock.nan_values_by_attribute = {}

        converter = DownholeCollectionToGeoscienceObject(dhc_mock, mock_data_client)
        result = converter.convert()

        assert result is not None
        assert result.name == "Minimal Distance"

    def test_single_hole_single_interval(self, mock_data_client):
        """Test conversion with minimal interval data."""
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

        interval_measurements_df = pd.DataFrame(
            {
                "hole_index": [1],
                "SCPP_TOP": [0.0],
                "SCPP_BASE": [10.0],
                "lithology": [1],
            }
        )

        collars_mock = Mock()
        collars_mock.df = collars_df

        interval_table_mock = Mock(spec=IntervalMeasurementTable)
        interval_table_mock.df = interval_measurements_df
        interval_table_mock.get_from_column.return_value = "SCPP_TOP"
        interval_table_mock.get_to_column.return_value = "SCPP_BASE"
        interval_table_mock.get_attribute_columns.return_value = ["lithology"]

        dhc_mock = Mock(spec=DownholeCollection)
        dhc_mock.name = "Minimal Interval"
        dhc_mock.coordinate_reference_system = 4326
        dhc_mock.collars = collars_mock
        dhc_mock.get_bounding_box.return_value = [100.0, 100.0, 500.0, 500.0, 50.0, 50.0]
        dhc_mock.get_measurement_tables.return_value = [interval_table_mock]
        dhc_mock.nan_values_by_attribute = {}

        # Need to add a distance table for path calculation
        distance_measurements_df = pd.DataFrame(
            {
                "hole_index": [1],
                "penetrationLength": [10.0],
            }
        )
        distance_table_mock = Mock(spec=DistanceMeasurementTable)
        distance_table_mock.df = distance_measurements_df
        distance_table_mock.get_depth_values.return_value = [10.0]

        # Mock the get_measurement_tables to return interval for main loop but distance for path
        def get_tables_side_effect(filter=None):
            if filter and DistanceMeasurementTable in filter:
                return [distance_table_mock]
            return [interval_table_mock]

        dhc_mock.get_measurement_tables.side_effect = get_tables_side_effect

        converter = DownholeCollectionToGeoscienceObject(dhc_mock, mock_data_client)
        result = converter.convert()

        assert result is not None
        assert result.name == "Minimal Interval"

    def test_multiple_holes_unequal_measurements(self, mock_data_client):
        """Test conversion with varying measurement counts per hole."""
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

        distance_measurements_df = pd.DataFrame(
            {
                "hole_index": [1, 2, 2, 2, 3],
                "penetrationLength": [10.0, 15.0, 25.0, 35.0, 20.0],
                "density": [2.5, 2.4, 2.5, 2.6, 2.3],
            }
        )

        collars_mock = Mock()
        collars_mock.df = collars_df

        distance_table_mock = Mock(spec=DistanceMeasurementTable)
        distance_table_mock.df = distance_measurements_df
        distance_table_mock.get_depth_values.return_value = distance_measurements_df["penetrationLength"].tolist()
        distance_table_mock.get_primary_column.return_value = "penetrationLength"
        distance_table_mock.get_attribute_columns.return_value = ["density"]

        dhc_mock = Mock(spec=DownholeCollection)
        dhc_mock.name = "Unequal"
        dhc_mock.coordinate_reference_system = 4326
        dhc_mock.collars = collars_mock
        dhc_mock.get_bounding_box.return_value = [100.0, 300.0, 500.0, 700.0, 50.0, 60.0]
        dhc_mock.get_measurement_tables.return_value = [distance_table_mock]
        dhc_mock.nan_values_by_attribute = {}

        converter = DownholeCollectionToGeoscienceObject(dhc_mock, mock_data_client)
        holes_table = converter.holes_table(distance_table_mock)

        counts = holes_table.column("count").to_pylist()
        offsets = holes_table.column("offset").to_pylist()

        assert counts == [1, 3, 1]
        assert offsets == [0, 1, 4]

    def test_nan_values_handling(self, mock_data_client):
        """Test that NaN values are properly handled in attributes."""
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

        distance_measurements_df = pd.DataFrame(
            {
                "hole_index": [1],
                "penetrationLength": [10.0],
                "density": [-999.0],  # Sentinel value
            }
        )

        collars_mock = Mock()
        collars_mock.df = collars_df

        distance_table_mock = Mock(spec=DistanceMeasurementTable)
        distance_table_mock.df = distance_measurements_df
        distance_table_mock.get_depth_values.return_value = [10.0]
        distance_table_mock.get_primary_column.return_value = "penetrationLength"
        distance_table_mock.get_attribute_columns.return_value = ["density"]

        dhc_mock = Mock(spec=DownholeCollection)
        dhc_mock.name = "NaN Test"
        dhc_mock.coordinate_reference_system = 4326
        dhc_mock.collars = collars_mock
        dhc_mock.get_bounding_box.return_value = [100.0, 100.0, 500.0, 500.0, 50.0, 50.0]
        dhc_mock.get_measurement_tables.return_value = [distance_table_mock]
        dhc_mock.nan_values_by_attribute = {"density": [-999.0]}

        converter = DownholeCollectionToGeoscienceObject(dhc_mock, mock_data_client)
        measurement_table = dhc_mock.get_measurement_tables()[0]
        distance_collection = converter.create_dhc_collection_distance(measurement_table)

        # Find the density attribute
        density_attr = next(attr for attr in distance_collection.distance.attributes if attr.key == "density")

        assert density_attr.nan_description is not None
        assert density_attr.nan_description.values == [-999.0]
