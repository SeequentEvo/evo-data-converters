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
from evo.data_converters.common.objects.downhole_collection import (
    ColumnMapping,
    DownholeCollection,
    DistanceTable,
    IntervalTable,
)
from evo.data_converters.common.objects.downhole_collection.hole_collars import HoleCollars
from evo.data_converters.common.objects.downhole_collection.tables import (
    MeasurementTableAdapter,
    MeasurementTableFactory,
)


@pytest.fixture
def valid_collars_df():
    """Create a valid collars DataFrame."""
    return pd.DataFrame(
        {
            "hole_index": [1, 2, 3],
            "hole_id": ["DH-001", "DH-002", "DH-003"],
            "x": [100.0, 200.0, 300.0],
            "y": [500.0, 600.0, 700.0],
            "z": [50.0, 55.0, 60.0],
            "final_depth": [150.0, 200.0, 180.0],
        }
    )


@pytest.fixture
def valid_collars(valid_collars_df):
    """Create a valid HoleCollars object."""
    return HoleCollars(valid_collars_df)


@pytest.fixture
def distance_measurements_df():
    """Create distance-based measurements DataFrame."""
    return pd.DataFrame(
        {
            "hole_index": [1, 1, 2],
            "penetrationLength": [10.0, 20.0, 15.0],
            "value": [1.5, 2.3, 1.8],
        }
    )


@pytest.fixture
def interval_measurements_df():
    """Create interval-based measurements DataFrame."""
    return pd.DataFrame(
        {
            "hole_index": [1, 1, 2],
            "SCPP_TOP": [0.0, 10.0, 0.0],
            "SCPP_BASE": [10.0, 20.0, 15.0],
            "value": [1.5, 2.3, 1.8],
        }
    )


class TestDownholeCollectionInitialization:
    def test_init_minimal(self, valid_collars):
        """Test initialization with minimal required parameters."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
        )
        assert dc.name == "Test Collection"
        assert dc.collars == valid_collars
        assert len(dc.measurements) == 0
        assert dc.nan_values_by_attribute == {}
        assert dc.coordinate_reference_system == "unspecified"

    def test_init_with_epsg_code(self, valid_collars):
        """Test initialization with EPSG code."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
            coordinate_reference_system=4326,
        )
        assert dc.coordinate_reference_system == 4326

    def test_init_with_wkt(self, valid_collars):
        """Test initialization with WKT coordinate reference system."""
        wkt = 'PROJCS["WGS 84 / UTM zone 33N"]'
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
            coordinate_reference_system=wkt,
        )
        assert dc.coordinate_reference_system == wkt

    def test_init_with_single_measurement_df(self, valid_collars, distance_measurements_df):
        """Test initialization with a single measurement DataFrame."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
            measurements=[distance_measurements_df],
            column_mapping=ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]),
        )
        assert len(dc.measurements) == 1
        assert isinstance(dc.measurements[0], MeasurementTableAdapter)

    def test_init_with_multiple_measurement_dfs(
        self, valid_collars, distance_measurements_df, interval_measurements_df
    ):
        """Test initialization with multiple measurement DataFrames."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
            measurements=[distance_measurements_df, interval_measurements_df],
            column_mapping=ColumnMapping(
                DEPTH_COLUMNS=["penetrationLength"], FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]
            ),
        )
        assert len(dc.measurements) == 2
        assert all(isinstance(m, MeasurementTableAdapter) for m in dc.measurements)

    def test_init_with_measurement_adapter(self, valid_collars, distance_measurements_df):
        """Test initialization with a MeasurementTableAdapter."""
        col_mapping = ColumnMapping(DEPTH_COLUMNS=["penetrationLength"])
        adapter = MeasurementTableFactory.create(distance_measurements_df, col_mapping)
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
            measurements=[adapter],
        )
        assert len(dc.measurements) == 1
        assert dc.measurements[0] == adapter

    def test_init_with_nan_values(self, valid_collars):
        """Test initialization with NaN values specification."""
        nan_values = {"density": [-999.0, -9999.0], "porosity": [-1.0]}
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
            nan_values_by_attribute=nan_values,
        )
        assert dc.nan_values_by_attribute == nan_values

    def test_init_with_all_optional_parameters(self, valid_collars, distance_measurements_df):
        """Test initialization with all optional parameters."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test Collection",
            measurements=[distance_measurements_df],
            column_mapping=ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]),
            nan_values_by_attribute={"value": [-999.0]},
            uuid="test-uuid-123",
            coordinate_reference_system=32633,
            description="Test description",
            extensions={"custom_field": "custom_value"},
            tags={"project": "test_project"},
        )
        assert dc.name == "Test Collection"
        assert dc.uuid == "test-uuid-123"
        assert dc.coordinate_reference_system == 32633
        assert dc.description == "Test description"
        assert dc.extensions == {"custom_field": "custom_value"}
        assert dc.tags == {"project": "test_project"}
        assert dc.nan_values_by_attribute == {"value": [-999.0]}


class TestAddMeasurementTable:
    def test_add_measurement_table_from_dataframe(self, valid_collars, distance_measurements_df):
        """Test adding a measurement table from a DataFrame."""
        dc = DownholeCollection(collars=valid_collars, name="Test")

        dc.add_measurement_table(distance_measurements_df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))

        assert len(dc.measurements) == 1
        assert isinstance(dc.measurements[0], MeasurementTableAdapter)

    def test_add_measurement_table_from_adapter(self, valid_collars, distance_measurements_df):
        """Test adding a measurement table from an adapter."""
        col_mapping = ColumnMapping(DEPTH_COLUMNS=["penetrationLength"])
        dc = DownholeCollection(collars=valid_collars, name="Test")
        adapter = MeasurementTableFactory.create(distance_measurements_df, col_mapping)

        dc.add_measurement_table(adapter)

        assert len(dc.measurements) == 1
        assert dc.measurements[0] == adapter

    def test_add_multiple_measurement_tables(self, valid_collars, distance_measurements_df, interval_measurements_df):
        """Test adding multiple measurement tables."""
        dc = DownholeCollection(collars=valid_collars, name="Test")

        dc.add_measurement_table(distance_measurements_df, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        dc.add_measurement_table(
            interval_measurements_df, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"])
        )

        assert len(dc.measurements) == 2

    def test_add_measurement_table_preserves_order(self, valid_collars):
        """Test that measurement tables are added in order."""
        dc = DownholeCollection(collars=valid_collars, name="Test")

        df1 = pd.DataFrame({"hole_index": [1], "penetrationLength": [10.0], "attr1": [1.0]})
        df2 = pd.DataFrame({"hole_index": [1], "SCPP_TOP": [0.0], "SCPP_BASE": [10.0], "attr2": [2.0]})
        df3 = pd.DataFrame({"hole_index": [1], "penetrationLength": [20.0], "attr3": [3.0]})

        dc.add_measurement_table(df1, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))
        dc.add_measurement_table(df2, ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]))
        dc.add_measurement_table(df3, ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]))

        assert len(dc.measurements) == 3
        # Verify order by checking attribute columns
        assert "attr1" in dc.measurements[0].get_attribute_columns()
        assert "attr2" in dc.measurements[1].get_attribute_columns()
        assert "attr3" in dc.measurements[2].get_attribute_columns()


class TestGetMeasurementTables:
    def test_get_all_measurement_tables(self, valid_collars, distance_measurements_df):
        """Test getting all measurement tables without filter."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=[distance_measurements_df],
            column_mapping=ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]),
        )

        tables = dc.get_measurement_tables()

        assert len(tables) == 1
        assert isinstance(tables[0], MeasurementTableAdapter)

    def test_get_measurement_tables_returns_copy(self, valid_collars, distance_measurements_df):
        """Test that get_measurement_tables returns a copy, not the original list."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=[distance_measurements_df],
            column_mapping=ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]),
        )

        tables1 = dc.get_measurement_tables()
        tables2 = dc.get_measurement_tables()

        assert tables1 is not tables2  # Different list objects
        assert tables1 == tables2  # Same contents

    def test_get_measurement_tables_with_distance_filter(
        self, valid_collars, distance_measurements_df, interval_measurements_df
    ):
        """Test filtering for only distance measurement tables."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=[distance_measurements_df, interval_measurements_df],
            column_mapping=ColumnMapping(
                DEPTH_COLUMNS=["penetrationLength"], FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]
            ),
        )

        distance_tables = dc.get_measurement_tables(filter=[DistanceTable])

        assert len(distance_tables) == 1
        assert isinstance(distance_tables[0], DistanceTable)

    def test_get_measurement_tables_with_interval_filter(
        self, valid_collars, distance_measurements_df, interval_measurements_df
    ):
        """Test filtering for only interval measurement tables."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=[distance_measurements_df, interval_measurements_df],
            column_mapping=ColumnMapping(
                DEPTH_COLUMNS=["penetrationLength"], FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]
            ),
        )

        interval_tables = dc.get_measurement_tables(filter=[IntervalTable])

        assert len(interval_tables) == 1
        assert isinstance(interval_tables[0], IntervalTable)

    def test_get_measurement_tables_with_multiple_type_filter(
        self, valid_collars, distance_measurements_df, interval_measurements_df
    ):
        """Test filtering with multiple types."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=[distance_measurements_df, interval_measurements_df],
            column_mapping=ColumnMapping(
                DEPTH_COLUMNS=["penetrationLength"], FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"]
            ),
        )

        tables = dc.get_measurement_tables(filter=[DistanceTable, IntervalTable])

        assert len(tables) == 2

    def test_get_measurement_tables_empty_when_no_match(self, valid_collars, distance_measurements_df):
        """Test that filtering returns empty list when no tables match."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=[distance_measurements_df],  # Only distance table
            column_mapping=ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]),
        )

        interval_tables = dc.get_measurement_tables(filter=[IntervalTable])

        assert len(interval_tables) == 0

    def test_get_measurement_tables_with_no_measurements(self, valid_collars):
        """Test getting measurement tables when none exist."""
        dc = DownholeCollection(collars=valid_collars, name="Test")

        tables = dc.get_measurement_tables()

        assert len(tables) == 0
        assert isinstance(tables, list)


class TestGetBoundingBox:
    def test_get_bounding_box(self, valid_collars):
        """Test getting bounding box from collars."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
        )

        bbox = dc.get_bounding_box()

        assert isinstance(bbox, list)
        assert len(bbox) == 6
        assert bbox[0] == 100.0  # min_x
        assert bbox[1] == 300.0  # max_x
        assert bbox[2] == 500.0  # min_y
        assert bbox[3] == 700.0  # max_y
        assert bbox[4] == 50.0  # min_z
        assert bbox[5] == 60.0  # max_z

    def test_get_bounding_box_single_point(self, valid_collars_df):
        """Test bounding box with a single collar point."""
        single_collar_df = pd.DataFrame(
            {
                "hole_index": [1],
                "hole_id": ["DH-001"],
                "x": [100.0],
                "y": [500.0],
                "z": [50.0],
                "final_depth": [150.0],
            }
        )
        collars = HoleCollars(single_collar_df)
        dc = DownholeCollection(collars=collars, name="Test")

        bbox = dc.get_bounding_box()

        assert bbox[0] == bbox[1] == 100.0  # min_x == max_x
        assert bbox[2] == bbox[3] == 500.0  # min_y == max_y
        assert bbox[4] == bbox[5] == 50.0  # min_z == max_z

    def test_get_bounding_box_negative_coordinates(self, valid_collars_df):
        """Test bounding box with negative coordinates."""
        negative_coords_df = pd.DataFrame(
            {
                "hole_index": [1, 2],
                "hole_id": ["DH-001", "DH-002"],
                "x": [-100.0, -50.0],
                "y": [-200.0, -150.0],
                "z": [-10.0, -5.0],
                "final_depth": [100.0, 150.0],
            }
        )
        collars = HoleCollars(negative_coords_df)
        dc = DownholeCollection(collars=collars, name="Test")

        bbox = dc.get_bounding_box()

        assert bbox[0] == -100.0  # min_x
        assert bbox[1] == -50.0  # max_x
        assert bbox[2] == -200.0  # min_y
        assert bbox[3] == -150.0  # max_y
        assert bbox[4] == -10.0  # min_z
        assert bbox[5] == -5.0  # max_z


class TestIntegration:
    def test_complete_distance_workflow(self, valid_collars, distance_measurements_df):
        """Test a complete workflow with distance measurements."""
        # Create collection
        dc = DownholeCollection(
            collars=valid_collars,
            name="Distance Test",
            coordinate_reference_system=32633,
        )

        # Add measurement table
        dc.add_measurement_table(
            distance_measurements_df, column_mapping=ColumnMapping(DEPTH_COLUMNS=["penetrationLength"])
        )

        # Verify measurements
        tables = dc.get_measurement_tables(filter=[DistanceTable])
        assert len(tables) == 1

        # Verify bounding box
        bbox = dc.get_bounding_box()
        assert len(bbox) == 6

    def test_complete_interval_workflow(self, valid_collars, interval_measurements_df):
        """Test a complete workflow with interval measurements."""
        # Create collection
        dc = DownholeCollection(
            collars=valid_collars,
            name="Interval Test",
            coordinate_reference_system=4326,
        )

        # Add measurement table
        dc.add_measurement_table(
            interval_measurements_df, column_mapping=ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"])
        )

        # Verify measurements
        tables = dc.get_measurement_tables(filter=[IntervalTable])
        assert len(tables) == 1

        # Verify bounding box
        bbox = dc.get_bounding_box()
        assert len(bbox) == 6

    def test_complete_mixed_workflow(self, valid_collars, distance_measurements_df, interval_measurements_df):
        """Test a complete workflow with both distance and interval measurements."""
        # Create collection with one measurement
        dc = DownholeCollection(
            collars=valid_collars,
            name="Mixed Test",
            measurements=[distance_measurements_df],
            coordinate_reference_system=32633,
            nan_values_by_attribute={"value": [-999.0]},
            column_mapping=ColumnMapping(DEPTH_COLUMNS=["penetrationLength"]),
        )

        # Add another measurement
        dc.add_measurement_table(
            interval_measurements_df, column_mapping=ColumnMapping(FROM_COLUMNS=["SCPP_TOP"], TO_COLUMNS=["SCPP_BASE"])
        )

        # Verify all measurements
        all_tables = dc.get_measurement_tables()
        assert len(all_tables) == 2

        # Verify filtered measurements
        distance_tables = dc.get_measurement_tables(filter=[DistanceTable])
        interval_tables = dc.get_measurement_tables(filter=[IntervalTable])
        assert len(distance_tables) == 1
        assert len(interval_tables) == 1

        # Verify bounding box
        bbox = dc.get_bounding_box()
        assert bbox[0] == 100.0  # min_x
        assert bbox[1] == 300.0  # max_x


class TestEdgeCases:
    def test_empty_measurements_list(self, valid_collars):
        """Test initialization with empty measurements list."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=[],
        )
        assert len(dc.measurements) == 0

    def test_none_measurements(self, valid_collars):
        """Test initialization with None measurements."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            measurements=None,
        )
        assert len(dc.measurements) == 0

    def test_empty_nan_values_dict(self, valid_collars):
        """Test initialization with empty nan_values_by_attribute dict."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            nan_values_by_attribute={},
        )
        assert dc.nan_values_by_attribute == {}

    def test_none_nan_values(self, valid_collars):
        """Test initialization with None nan_values_by_attribute."""
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            nan_values_by_attribute=None,
        )
        assert dc.nan_values_by_attribute == {}

    def test_multiple_attributes_nan_values(self, valid_collars):
        """Test with multiple attributes having NaN values."""
        nan_values = {
            "density": [-999.0, -9999.0],
            "porosity": [-1.0],
            "grade": [-999.0, -99.0, -9.0],
        }
        dc = DownholeCollection(
            collars=valid_collars,
            name="Test",
            nan_values_by_attribute=nan_values,
        )
        assert dc.nan_values_by_attribute == nan_values
        assert "density" in dc.nan_values_by_attribute
        assert "porosity" in dc.nan_values_by_attribute
        assert "grade" in dc.nan_values_by_attribute
