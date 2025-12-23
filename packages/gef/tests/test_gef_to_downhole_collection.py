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

from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pint_pandas
import polars as pl
import pytest

from evo.data_converters.common.objects import DownholeCollection
from evo.data_converters.gef import gef_unit_registry
from evo.data_converters.gef.converter.gef_to_downhole_collection import (
    DownholeCollectionBuilder,
    create_from_parsed_gef_cpts,
)


@pytest.fixture
def shared_gef_unit_registry():
    return gef_unit_registry


@pytest.fixture
def builder() -> DownholeCollectionBuilder:
    """Provide a fresh DownholeCollectionBuilder instance for each test."""
    return DownholeCollectionBuilder()


@pytest.fixture
def mock_cpt_data() -> Mock:
    """Create a mock CPTData object with some extra attributes."""
    mock = Mock(
        spec=[
            "delivered_location",
            "delivered_vertical_position_offset",
            "final_depth",
            "data",
            "column_void_mapping",
            "engineer",
            "wind_speed",
            "raw_headers",
            "groundwater_level_offset",
            "predrilled_depth_offset",
            "final_depth_offset",
        ]
    )

    mock.delivered_location = Mock()
    mock.delivered_location.srs_name = "EPSG:28992"
    mock.delivered_location.x = 100000.0
    mock.delivered_location.y = 500000.0

    mock.delivered_vertical_position_offset = 0.5
    mock.final_depth = 10.0

    mock.data = pl.DataFrame(
        {
            "penetrationLength": [0.0, 1.0, 2.0, 3.0],
            "coneResistance": [0.5, 1.5, 2.5, 3.5],
            "localFriction": [0.02, 0.03, 0.04, 0.03],
        }
    )

    mock.column_void_mapping = {
        "penetrationLength": 9999.0,
        "coneResistance": 9999.0,
        "localFriction": 9999.0,
    }

    mock.raw_headers = {
        "MEASUREMENTTEXT": [
            ["4", "S10-CFIIP.1721", "conus type en serienummer"],
            ["5", "Sondeerrups 1; 12400 kg; geen ankers", "sondeerequipment"],
        ],
        "MEASUREMENTVAR": [
            ["1", "1000", "mm2", "nom. oppervlak conuspunt"],
            ["2", "15000", "mm2", "oppervlakte kleefmantel"],
        ],
    }

    mock.engineer = "Bob"
    mock.wind_speed = 12.2
    mock.predrilled_depth_offset = 1500
    mock.final_depth_offset = 4596

    return mock


@pytest.fixture
def mock_cpt_data_2() -> Mock:
    """Create a second mock CPTData object with different values."""
    mock = Mock(
        spec=[
            "delivered_location",
            "delivered_vertical_position_offset",
            "final_depth",
            "data",
            "column_void_mapping",
            "engineer",
            "wind_speed",
            "raw_headers",
            "groundwater_level_offset",
            "predrilled_depth_offset",
            "final_depth_offset",
        ]
    )

    mock.delivered_location = Mock()
    mock.delivered_location.srs_name = "EPSG:28992"
    mock.delivered_location.x = 100000.0
    mock.delivered_location.y = 500100.0

    mock.delivered_vertical_position_offset = 0.5
    mock.final_depth = 10.0

    mock.data = pl.DataFrame(
        {
            "penetrationLength": [0.0, 1.0, 2.0, 3.0],
            "coneResistance": [1.0, 2.0, 3.0, 4.0],
            "localFriction": [0.01, 0.02, 0.03, 0.04],
        }
    )

    mock.column_void_mapping = {
        "penetrationLength": 9999.0,
        "coneResistance": 9999.0,
        "localFriction": 9999.0,
    }

    mock.raw_headers = {
        "MEASUREMENTTEXT": [
            ["99999", "Unmapped header should come back with measurementtext_99999"],
        ],
        "MEASUREMENTVAR": [
            ["99999", "Unmapped header", "should come back with", "measurementvar_99999"],
        ],
    }

    mock.engineer = "Bob"
    mock.wind_speed = 17.0
    mock.predrilled_depth_offset = 1700
    mock.final_depth_offset = 7596

    return mock


@pytest.fixture
def mock_cpt_data_3() -> Mock:
    """Create a third mock CPTData object with different attributes."""
    mock = Mock(
        spec=[
            "delivered_location",
            "delivered_vertical_position_offset",
            "final_depth",
            "data",
            "column_void_mapping",
            "wind_speed",
            "raw_headers",
            "groundwater_level_offset",
            "predrilled_depth_offset",
        ]
    )

    mock.delivered_location = Mock()
    mock.delivered_location.srs_name = "EPSG:28992"
    mock.delivered_location.x = 100000.0
    mock.delivered_location.y = 500200.0

    mock.delivered_vertical_position_offset = 0.5
    mock.final_depth = 10.0

    mock.data = pl.DataFrame(
        {
            "penetrationLength": [0.0, 1.0, 2.0, 3.0],
            "coneResistance": [1.0, 2.0, 3.0, 4.0],
            "localFriction": [0.01, 0.02, 0.03, 0.04],
        }
    )

    mock.column_void_mapping = {
        "penetrationLength": 9999.0,
        "coneResistance": 9999.0,
        "localFriction": 9999.0,
    }

    mock.raw_headers = {}

    mock.engineer = "Sally"
    mock.wind_speed = 15.0
    mock.predrilled_depth_offset = 1245
    mock.groundwater_level_offset = 400

    return mock


@pytest.fixture
def mock_cpt_data_4() -> Mock:
    """Create a mock CPTData object with some extra attributes."""
    mock = Mock(
        spec=[
            "delivered_location",
            "delivered_vertical_position_offset",
            "final_depth",
            "data",
            "column_void_mapping",
            "engineer",
            "wind_speed",
            "raw_headers",
            "predrilled_depth_offset",
        ]
    )

    mock.delivered_location = Mock()
    mock.delivered_location.srs_name = "EPSG:28992"
    mock.delivered_location.x = 100000.0
    mock.delivered_location.y = 500000.0

    mock.delivered_vertical_position_offset = 0.5
    mock.final_depth = 10.0

    mock.data = pl.DataFrame(
        {
            "penetrationLength": [0.0, 1.0, 2.0, 3.0],
            "coneResistance": [0.5, 1.5, 2.5, 3.5],
            "localFriction": [0.02, 0.03, 0.04, 0.03],
            "frictionRatio": [0.01, 0.02, 0.03, 0.04],
            "soilDensity": [1.2, 2.4, 3.3, 4.1],
        }
    )

    mock.column_void_mapping = {
        "penetrationLength": 9999.0,
        "coneResistance": 9999.0,
        "localFriction": 9999.0,
        "frictionRatio": 9999.0,
        "soilDensity": 9999.0,
    }

    mock.raw_headers = {
        "MEASUREMENTTEXT": [
            ["4", "S10-CFIIP.1721", "conus type en serienummer"],
            ["5", "Sondeerrups 1; 12400 kg; geen ankers", "sondeerequipment"],
        ],
        "MEASUREMENTVAR": [
            ["1", "1000", "mm2", "nom. oppervlak conuspunt"],
            ["2", "15000", "mm2", "oppervlakte kleefmantel"],
        ],
    }

    mock.report_date = datetime(year=2020, month=10, day=20)
    mock.engineer = "Bob"
    mock.wind_speed = 12.2
    mock.predrilled_depth_offset = 2452

    return mock


class TestProcessCptFile:
    @patch("evo.data_converters.gef.converter.gef_to_downhole_collection.logger")
    def test_successful_processing(self, mock_logger, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder.process_cpt_file(1, "CPT-001", mock_cpt_data, "file_name")

        assert len(builder.collar_rows) == 1
        assert len(builder.measurement_dfs) == 1
        assert builder.epsg_code == 28992
        assert builder.collar_rows[0]["hole_id"] == "CPT-001"
        assert builder.collar_rows[0]["hole_index"] == 1
        assert mock_logger.debug.called

    def test_inconsistent_epsg_raises_error(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2
    ) -> None:
        builder.process_cpt_file(1, "CPT-001", mock_cpt_data, "file_name")
        mock_cpt_data_2.delivered_location.srs_name = "EPSG:4326"

        with pytest.raises(ValueError, match="Inconsistent EPSG codes"):
            builder.process_cpt_file(2, "CPT-002", mock_cpt_data_2, "file_name_2")


class TestBuild:
    def test_successful_build(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder.process_cpt_file(1, "CPT-001", mock_cpt_data, "path/to/the/data.file")
        result = builder.build()

        assert isinstance(result, DownholeCollection)
        assert result.name == "GEF CPT CPT-001"
        assert result.coordinate_reference_system == 28992

    def test_build_without_epsg_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        with pytest.raises(ValueError, match="Could not find valid epsg code"):
            builder.build()


class TestExtractEpsgCode:
    def test_valid_epsg_short_format(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location.srs_name = "EPSG:28992"

        result = builder._extract_epsg_code(mock_cpt, "TEST-001")

        assert result == 28992

    def test_valid_epsg_urn_format(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location.srs_name = "urn:ogc:def:crs:EPSG::4326"

        result = builder._extract_epsg_code(mock_cpt, "TEST-001")

        assert result == 4326

    def test_epsg_404000_returns_none(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location.srs_name = "urn:ogc:def:crs:EPSG::404000"

        result = builder._extract_epsg_code(mock_cpt, "TEST-001")

        assert result is None

    def test_malformed_srs_name_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location.srs_name = "INVALID_FORMAT"

        with pytest.raises(ValueError, match="malformed SRS name"):
            builder._extract_epsg_code(mock_cpt, "TEST-001")


class TestValidateAndSetEpsg:
    @patch("evo.data_converters.gef.converter.gef_to_downhole_collection.logger")
    def test_sets_epsg_on_first_file(self, mock_logger, builder, mock_cpt_data) -> None:
        builder._validate_and_set_epsg(mock_cpt_data, "CPT-001", "a_file_name")

        assert builder.epsg_code == 28992
        assert mock_logger.info.called

    def test_consistent_epsg_passes(self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2) -> None:
        builder._validate_and_set_epsg(mock_cpt_data, "CPT-001", "file_cpt001")
        builder._validate_and_set_epsg(mock_cpt_data_2, "CPT-002", "file_cpt002")

        assert builder.epsg_code == 28992

    def test_inconsistent_epsg_raises_error(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2
    ) -> None:
        builder._validate_and_set_epsg(mock_cpt_data, "CPT-001", "the_data_file_name")
        mock_cpt_data_2.delivered_location.srs_name = "EPSG:4326"

        with pytest.raises(ValueError, match="Inconsistent EPSG codes"):
            builder._validate_and_set_epsg(mock_cpt_data_2, "CPT-002", "directory/file.extension")


class TestValidateEpsgCode:
    def test_valid_epsg_passes(self, builder: DownholeCollectionBuilder) -> None:
        builder.epsg_code = 28992
        builder._validate_epsg_code()  # Should not raise

    def test_none_epsg_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        with pytest.raises(ValueError, match="Could not find valid epsg code"):
            builder._validate_epsg_code()


class TestCalculateFinalDepth:
    def test_uses_final_depth_when_available(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.final_depth = 15.5
        mock_cpt.data = pl.DataFrame({"penetrationLength": [0, 1, 2]})

        result = builder._calculate_final_depth(mock_cpt, "TEST-001")

        assert result == 15.5

    def test_calculates_from_penetration_length(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.final_depth = 0.0
        mock_cpt.data = pl.DataFrame({"penetrationLength": [0.0, 2.5, 5.0, 7.8]})

        result = builder._calculate_final_depth(mock_cpt, "TEST-001")

        assert result == 7.8

    def test_missing_penetration_length_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.final_depth = 0.0
        mock_cpt.data = pl.DataFrame({"coneResistance": [1, 2, 3]})

        with pytest.raises(ValueError, match="missing 'penetrationLength' column"):
            builder._calculate_final_depth(mock_cpt, "TEST-001")


class TestGetCollarAttributes:
    def test_filters_excluded_keys(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        attributes = builder._get_collar_attributes(mock_cpt_data)

        assert "data" not in attributes
        assert "final_depth" not in attributes
        assert "column_void_mapping" not in attributes
        assert "raw_headers" not in attributes

    def test_filters_unknown_attributes(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        attributes = builder._get_collar_attributes(mock_cpt_data)

        assert "engineer" not in attributes
        assert "wind_speed" not in attributes

    def test_returns_valid_attributes(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        attributes = builder._get_collar_attributes(mock_cpt_data)

        assert "engineer" not in attributes
        assert "wind_speed" not in attributes
        assert attributes["predrilled_depth_offset"] == 1500
        assert attributes["final_depth_offset"] == 4596

    def test_filters_none_and_empty_values(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location = Mock()
        mock_cpt.data = []
        mock_cpt.empty_list = []
        mock_cpt.empty_dict = {}
        mock_cpt.none_value = None
        mock_cpt.cpt_standard = []
        mock_cpt.standardized_location = {}
        mock_cpt.dissipationtest_performed = None
        mock_cpt.predrilled_depth = 23254

        attributes = builder._get_collar_attributes(mock_cpt)

        assert "cpt_standard" not in attributes
        assert "standardizied_location" not in attributes
        assert "dissapationtest_performed" not in attributes
        assert attributes["predrilled_depth"] == 23254


class TestCreateCollarRow:
    """Tests for _create_collar_row method."""

    def test_creates_correct_collar_row(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        collar_row = builder._create_collar_row(1, "CPT-001", mock_cpt_data)

        assert collar_row["hole_index"] == 1
        assert collar_row["hole_id"] == "CPT-001"
        assert collar_row["x"] == 100000.0
        assert collar_row["y"] == 500000.0
        assert collar_row["z"] == 0.5
        assert collar_row["final_depth"] == 10.0

    def test_includes_collar_attributes(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        collar_row = builder._create_collar_row(1, "CPT-001", mock_cpt_data)

        assert collar_row["predrilled_depth_offset"] == 1500
        assert collar_row["final_depth_offset"] == 4596

    def test_includes_raw_headers(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        collar_row = builder._create_collar_row(1, "CPT-001", mock_cpt_data)

        assert collar_row["cone_type_serial"] == "S10-CFIIP.1721, conus type en serienummer"
        assert collar_row["friction_sleeve_area"] == "15000, mm2, oppervlakte kleefmantel"

    def test_unmapped_raw_headers(self, builder: DownholeCollectionBuilder, mock_cpt_data_2) -> None:
        collar_row = builder._create_collar_row(1, "CPT-001", mock_cpt_data_2)

        assert collar_row["measurementtext_99999"] == "Unmapped header should come back with measurementtext_99999"
        assert collar_row["measurementvar_99999"] == "Unmapped header, should come back with, measurementvar_99999"


class TestPrepareMeasurements:
    def test_adds_hole_index_column(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data)

        assert "hole_index" in measurements.columns
        assert all(measurements["hole_index"] == 1)

    def test_hole_index_is_first_column(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data)

        assert measurements.columns[0] == "hole_index"

    def test_preserves_other_columns(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data)

        assert "penetrationLength" in measurements.columns
        assert "coneResistance" in measurements.columns
        assert "localFriction" in measurements.columns

    def test_adds_dip_when_inclination_resultant_present(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.data = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0, 2.0],
                "inclinationResultant": [0.0, 10.0, 20.0],
            }
        )

        measurements = builder._prepare_measurements(1, mock_cpt)

        assert "dip" in measurements.columns
        assert measurements["dip"][0] == 90.0
        assert measurements["dip"][1] == 80.0
        assert measurements["dip"][2] == 70.0

    def test_adds_azimuth_when_inclination_components_present(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.data = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0],
                "inclinationNS": [1.0, 0.0],
                "inclinationEW": [0.0, 1.0],
            }
        )

        measurements = builder._prepare_measurements(1, mock_cpt)

        assert "azimuth" in measurements.columns
        assert measurements["azimuth"][0] == pytest.approx(0.0)  # North
        assert measurements["azimuth"][1] == pytest.approx(90.0)  # East


class TestApplyMeasurementUnits:
    def test_penetration_length_has_m_unit(self, builder: DownholeCollectionBuilder, mock_cpt_data_4) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data_4)
        measurements = builder._apply_measurement_units(measurements, mock_cpt_data_4)
        dtype = measurements["penetrationLength"].dtype
        assert isinstance(dtype, pint_pandas.PintType)
        assert dtype.units == "meter", f"Expected unit 'meter', got {dtype.units}"

    def test_cone_resistance_has_kpa_unit(self, builder: DownholeCollectionBuilder, mock_cpt_data_4) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data_4)
        measurements = builder._apply_measurement_units(measurements, mock_cpt_data_4)
        dtype = measurements["coneResistance"].dtype
        assert isinstance(dtype, pint_pandas.PintType)
        assert dtype.units == "megapascal", f"Expected unit 'megapascal', got {dtype.units}"

    def test_local_friction_has_kpa_unit(self, builder: DownholeCollectionBuilder, mock_cpt_data_4) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data_4)
        measurements = builder._apply_measurement_units(measurements, mock_cpt_data_4)
        dtype = measurements["localFriction"].dtype
        assert isinstance(dtype, pint_pandas.PintType)
        assert dtype.units == "megapascal", f"Expected unit 'megapascal', got {dtype.units}"

    def test_friction_ratio_has_float64_unit(self, builder: DownholeCollectionBuilder, mock_cpt_data_4) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data_4)
        measurements = builder._apply_measurement_units(measurements, mock_cpt_data_4)
        dtype = measurements["frictionRatio"].dtype
        assert not isinstance(dtype, pint_pandas.PintType)
        assert dtype == np.float64, f"Expected unit 'np.float64', got {dtype}"

    def test_soil_density_is_converted_to_n_per_m3_unit(
        self, builder: DownholeCollectionBuilder, mock_cpt_data_4
    ) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data_4)
        measurements = builder._apply_measurement_units(measurements, mock_cpt_data_4)
        dtype = measurements["soilDensity"].dtype
        assert isinstance(dtype, pint_pandas.PintType)
        assert dtype.units == "newton / meter ** 3", f"Expected unit 'newton / meter ** 3', got {dtype.units}"
        assert measurements["soilDensity"].iloc[0].magnitude == 1200.0
        assert measurements["soilDensity"].iloc[1].magnitude == 2400.0
        assert measurements["soilDensity"].iloc[2].magnitude == 3300.0
        assert measurements["soilDensity"].iloc[3].magnitude == 4100.0


class TestCalculateDip:
    def test_calculates_dip_from_inclination_resultant(self, builder: DownholeCollectionBuilder) -> None:
        df = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0, 2.0],
                "inclinationResultant": [0.0, 15.0, 30.0],
            }
        )

        result = builder.calculate_dip(df)

        assert "dip" in result.columns
        assert result["dip"][0] == 90.0  # 90 - 0
        assert result["dip"][1] == 75.0  # 90 - 15
        assert result["dip"][2] == 60.0  # 90 - 30

    def test_no_inclination_resultant_returns_original(self, builder: DownholeCollectionBuilder) -> None:
        df = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0, 2.0],
                "coneResistance": [1.0, 2.0, 3.0],
            }
        )

        result = builder.calculate_dip(df)

        assert "dip" not in result.columns
        assert result.equals(df)


class TestCalculateAzimuth:
    def test_calculates_azimuth_from_ns_ew_components(self, builder: DownholeCollectionBuilder) -> None:
        df = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0, 2.0, 3.0],
                "inclinationNS": [2.0, 0.0, -1.0, 1.0],
                "inclinationEW": [0.0, 2.0, 0.0, 1.0],
            }
        )

        result = builder.calculate_azimuth(df)

        assert "azimuth" in result.columns
        assert result["azimuth"][0] == pytest.approx(0.0)  # North
        assert result["azimuth"][1] == pytest.approx(90.0)  # East
        assert result["azimuth"][2] == pytest.approx(180.0)  # South
        assert result["azimuth"][3] == pytest.approx(45.0)  # Northeast

    def test_nan_values_produce_nan_azimuth(self, builder: DownholeCollectionBuilder) -> None:
        df = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0, 2.0],
                "inclinationNS": [None, 1.0, 1.0],
                "inclinationEW": [1.0, None, 1.0],
            }
        )

        result = builder.calculate_azimuth(df)

        assert "azimuth" in result.columns
        assert result["azimuth"].is_null()[0]
        assert result["azimuth"].is_null()[1]
        assert result["azimuth"][2] == pytest.approx(45.0)

    def test_missing_ns_column_returns_original(self, builder: DownholeCollectionBuilder) -> None:
        df = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0],
                "inclinationEW": [1.0, 2.0],
            }
        )

        result = builder.calculate_azimuth(df)

        assert "azimuth" not in result.columns
        assert result.equals(df)

    def test_missing_ew_column_returns_original(self, builder: DownholeCollectionBuilder) -> None:
        df = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0],
                "inclinationNS": [1.0, 2.0],
            }
        )

        result = builder.calculate_azimuth(df)

        assert "azimuth" not in result.columns
        assert result.equals(df)

    def test_missing_both_columns_returns_original(self, builder: DownholeCollectionBuilder) -> None:
        df = pl.DataFrame(
            {
                "penetrationLength": [0.0, 1.0],
                "coneResistance": [1.0, 2.0],
            }
        )

        result = builder.calculate_azimuth(df)

        assert "azimuth" not in result.columns
        assert result.equals(df)


class TestTrackNanValues:
    def test_tracks_nan_values_by_attribute(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder._track_nan_values(mock_cpt_data)

        assert builder.nan_values_by_attribute["penetrationLength"] == [9999.0]
        assert builder.nan_values_by_attribute["coneResistance"] == [9999.0]
        assert builder.nan_values_by_attribute["localFriction"] == [9999.0]

    def test_accumulates_nan_values_across_files(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2
    ) -> None:
        mock_cpt_data_2.column_void_mapping["penetrationLength"] = 1234.56
        builder._track_nan_values(mock_cpt_data)
        builder._track_nan_values(mock_cpt_data_2)

        assert len(builder.nan_values_by_attribute["penetrationLength"]) == 2
        assert builder.nan_values_by_attribute["penetrationLength"] == [9999.0, 1234.56]

    def test_skips_duplicate_nan_values_across_files(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2
    ) -> None:
        builder._track_nan_values(mock_cpt_data)
        builder._track_nan_values(mock_cpt_data_2)

        assert len(builder.nan_values_by_attribute["penetrationLength"]) == 1
        assert builder.nan_values_by_attribute["penetrationLength"] == [9999.0]


class TestApplyNanValuesToMeasurements:
    def test_sentinel_value_replacements(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder._track_nan_values(mock_cpt_data)
        measurements = pd.DataFrame(
            {
                "coneResistance": [9999.0, 1.0, 2.0, 9999.00],
            }
        )

        result = builder._apply_nan_values_to_measurements(measurements)

        assert pd.isna(result.iloc[0]["coneResistance"])
        assert result.iloc[1]["coneResistance"] == 1.0
        assert result.iloc[2]["coneResistance"] == 2.0
        assert pd.isna(result.iloc[3]["coneResistance"])


class TestCreateCollarsDataframe:
    def test_creates_dataframe_with_correct_dtypes(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder.collar_rows.append(builder._create_collar_row(1, "CPT-001", mock_cpt_data))
        collars_df = builder._create_collars_dataframe()

        assert isinstance(collars_df, pd.DataFrame)
        assert collars_df["hole_index"].dtype == "int32"
        assert collars_df["hole_id"].dtype == "string"
        assert collars_df["x"].dtype == "float64"
        assert collars_df["y"].dtype == "float64"
        assert collars_df["z"].dtype == "float64"
        assert collars_df["final_depth"].dtype == "float64"

    def test_creates_dataframe_with_multiple_rows(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2
    ) -> None:
        builder.collar_rows.append(builder._create_collar_row(1, "CPT-001", mock_cpt_data))
        builder.collar_rows.append(builder._create_collar_row(2, "CPT-002", mock_cpt_data_2))
        collars_df = builder._create_collars_dataframe()

        assert len(collars_df) == 2

    def test_creates_dataframe_with_differing_attributes(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2, mock_cpt_data_3
    ) -> None:
        builder.collar_rows.append(builder._create_collar_row(1, "CPT-001", mock_cpt_data))
        builder.collar_rows.append(builder._create_collar_row(2, "CPT-002", mock_cpt_data_2))
        builder.collar_rows.append(builder._create_collar_row(3, "CPT-003", mock_cpt_data_3))

        collars_df = builder._create_collars_dataframe()

        # groundwater_level_offset only exists in the 3rd cpt file
        assert pd.isna(collars_df.iloc[0]["groundwater_level_offset"])
        assert pd.isna(collars_df.iloc[1]["groundwater_level_offset"])
        assert collars_df.iloc[2]["groundwater_level_offset"] == 400

        # final_depth_offset appears in the first two cpt files
        assert collars_df.iloc[0]["final_depth_offset"]
        assert collars_df.iloc[1]["final_depth_offset"]
        assert pd.isna(collars_df.iloc[2]["final_depth_offset"])


class TestCreateMeasurementsDataframe:
    @patch("evo.data_converters.gef.converter.gef_to_downhole_collection.logger")
    def test_creates_dataframe_from_measurements(self, mock_logger, builder, mock_cpt_data) -> None:
        measurements = builder._prepare_measurements(1, mock_cpt_data)
        builder.measurement_dfs.append(measurements)

        measurements_df = builder._create_measurements_dataframe()

        assert isinstance(measurements_df, pd.DataFrame)
        assert len(measurements_df) == 4
        assert mock_logger.info.called

    @patch("evo.data_converters.gef.converter.gef_to_downhole_collection.logger")
    def test_empty_measurements_returns_empty_dataframe(self, mock_logger, builder) -> None:
        measurements_df = builder._create_measurements_dataframe()

        assert isinstance(measurements_df, pd.DataFrame)
        assert "hole_index" in measurements_df.columns
        assert len(measurements_df) == 0
        assert mock_logger.warning.called


class TestGenerateCollectionName:
    def test_empty_list_returns_empty_string(self, builder: DownholeCollectionBuilder) -> None:
        builder.collar_rows = []
        assert builder._generate_collection_name() == ""

    def test_single_collar_returns_hole_id(self, builder: DownholeCollectionBuilder) -> None:
        builder.collar_rows = [{"hole_id": "CPT-001"}]
        assert builder._generate_collection_name() == "GEF CPT CPT-001"

    def test_multiple_collars_returns_range_format(self, builder: DownholeCollectionBuilder) -> None:
        builder.collar_rows = [
            {"hole_id": "CPT-001"},
            {"hole_id": "CPT-002"},
            {"hole_id": "CPT-003"},
        ]
        assert builder._generate_collection_name() == "GEF CPT 3 holes CPT-001...CPT-003"


class TestCreateCollection:
    def test_creates_valid_collection(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder.epsg_code = 28992
        builder.collar_rows.append(builder._create_collar_row(1, "CPT-001", mock_cpt_data))
        builder.measurement_dfs.append(builder._prepare_measurements(1, mock_cpt_data))
        builder._track_nan_values(mock_cpt_data)

        collars_df = builder._create_collars_dataframe()
        measurements_df = builder._create_measurements_dataframe()
        collection_name = builder._generate_collection_name()

        result = builder._create_collection(collection_name, collars_df, measurements_df)

        assert isinstance(result, DownholeCollection)
        assert result.name == "GEF CPT CPT-001"
        assert result.coordinate_reference_system == 28992
        assert len(result.measurements) == 1
        assert result.measurements[0].nan_values_by_column["penetrationLength"] == [9999.00]


class TestCreateFromParsedGefCpts:
    def test_empty_dict_raises_error(self) -> None:
        with pytest.raises(ValueError, match="No CPT files provided"):
            create_from_parsed_gef_cpts({})

    def test_single_cpt_creates_valid_collection(self, mock_cpt_data) -> None:
        parsed_files = {"CPT-001": ("file_name", mock_cpt_data)}

        result = create_from_parsed_gef_cpts(parsed_files)

        assert isinstance(result, DownholeCollection)
        assert result.name == "GEF CPT CPT-001"
        assert result.coordinate_reference_system == 28992
        assert len(result.collars.df) == 1
        assert result.collars.df.iloc[0]["hole_id"] == "CPT-001"

    def test_multiple_cpts_creates_combined_collection(self, mock_cpt_data, mock_cpt_data_2) -> None:
        parsed_files = {"CPT-001": ("file_one", mock_cpt_data), "CPT-002": ("file_two", mock_cpt_data_2)}

        result = create_from_parsed_gef_cpts(parsed_files)

        assert result.name == "GEF CPT 2 holes CPT-001...CPT-002"
        assert len(result.collars.df) == 2
        assert len(result.measurements[0].df) == 8  # 4 measurements each
        assert result.measurements[0].df["hole_index"].nunique() == 2

    def test_five_cpts(self) -> None:
        """Test with multiple CPT files using dummy data."""
        cpts = {}

        for i in range(1, 6):
            mock = Mock(
                spec=[
                    "delivered_location",
                    "delivered_vertical_position_offset",
                    "final_depth",
                    "data",
                    "column_void_mapping",
                    "raw_headers",
                ]
            )
            mock.delivered_location = Mock()
            mock.delivered_location.srs_name = "EPSG:28992"
            mock.delivered_location.x = 100000.0 + (i * 50)
            mock.delivered_location.y = 500000.0 + (i * 50)
            mock.delivered_vertical_position_offset = 0.5
            mock.final_depth = 10.0 + i
            mock.data = pl.DataFrame(
                {
                    "penetrationLength": [j * 0.5 for j in range(20)],
                    "coneResistance": [j * 0.1 + i for j in range(20)],
                    "localFriction": [j * 0.01 for j in range(20)],
                }
            )
            mock.column_void_mapping = {
                "penetrationLength": 9999.0,
                "coneResistance": 9999.0,
                "localFriction": 9999.0,
            }
            mock.raw_headers = {}

            cpts[f"CPT-{i:03d}"] = ("filename", mock)

        result = create_from_parsed_gef_cpts(cpts)

        assert result.name == "GEF CPT 5 holes CPT-001...CPT-005"
        assert len(result.collars.df) == 5
        assert len(result.measurements[0].df) == 100  # 5 CPTs * 20 measurements
        assert set(result.measurements[0].df["hole_index"].unique()) == {1, 2, 3, 4, 5}

    def test_multiple_cpts_custom_name(self, mock_cpt_data, mock_cpt_data_2) -> None:
        """Test with multiple CPT, use custom name."""
        parsed_files = {"CPT-001": ("file_0001", mock_cpt_data), "CPT-002": ("file_002", mock_cpt_data_2)}

        result = create_from_parsed_gef_cpts(parsed_files, name="Custom name")

        assert result.name == "Custom name"
        assert len(result.collars.df) == 2
        assert len(result.measurements[0].df) == 8  # 4 measurements each
        assert result.measurements[0].df["hole_index"].nunique() == 2
