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
import polars as pl
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch
from evo.data_converters.common.objects import DownholeCollection
from evo.data_converters.gef.converter.gef_to_downhole_collection import (
    DownholeCollectionBuilder,
    create_from_parsed_gef_cpts,
)


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
            "report_date",
            "engineer",
            "wind_speed",
            "signed_off",
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
            "friction": [0.02, 0.03, 0.04, 0.03],
        }
    )

    mock.column_void_mapping = {
        "penetrationLength": 9999.0,
        "coneResistance": 9999.0,
        "friction": 9999.0,
    }

    mock.report_date = datetime(year=2020, month=10, day=20)
    mock.engineer = "Bob"
    mock.wind_speed = 12.2
    mock.signed_off = False

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
            "report_date",
            "engineer",
            "wind_speed",
            "signed_off",
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
            "friction": [0.01, 0.02, 0.03, 0.04],
        }
    )

    mock.column_void_mapping = {
        "penetrationLength": 9999.0,
        "coneResistance": 9999.0,
        "friction": 9999.0,
    }

    mock.report_date = datetime(year=2020, month=10, day=20)
    mock.engineer = "Bob"
    mock.wind_speed = 17.0
    mock.signed_off = True

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
            "report_date",
            "engineer",
            "wind_speed",
            "cone_size",
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
            "friction": [0.01, 0.02, 0.03, 0.04],
        }
    )

    mock.column_void_mapping = {
        "penetrationLength": 9999.0,
        "coneResistance": 9999.0,
        "friction": 9999.0,
    }

    mock.report_date = datetime(year=2020, month=10, day=21)
    mock.engineer = "Sally"
    mock.wind_speed = 15.0
    mock.cone_size = 3.14

    return mock


class TestProcessCptFile:
    @patch("evo.data_converters.gef.converter.gef_to_downhole_collection.logger")
    def test_successful_processing(self, mock_logger, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder.process_cpt_file(1, "CPT-001", mock_cpt_data)

        assert len(builder.collar_rows) == 1
        assert len(builder.measurement_dfs) == 1
        assert builder.epsg_code == 28992
        assert builder.collar_rows[0]["hole_id"] == "CPT-001"
        assert builder.collar_rows[0]["hole_index"] == 1
        assert mock_logger.debug.called

    def test_inconsistent_epsg_raises_error(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2
    ) -> None:
        builder.process_cpt_file(1, "CPT-001", mock_cpt_data)
        mock_cpt_data_2.delivered_location.srs_name = "EPSG:4326"

        with pytest.raises(ValueError, match="Inconsistent EPSG codes"):
            builder.process_cpt_file(2, "CPT-002", mock_cpt_data_2)


class TestBuild:
    def test_successful_build(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder.process_cpt_file(1, "CPT-001", mock_cpt_data)
        result = builder.build()

        assert isinstance(result, DownholeCollection)
        assert result.name == "CPT-001"
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

    def test_epsg_404000_returns_unspecified(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location.srs_name = "urn:ogc:def:crs:EPSG::404000"

        result = builder._extract_epsg_code(mock_cpt, "TEST-001")

        assert result == "unspecified"

    def test_missing_srs_name_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location = Mock(spec=[])

        with pytest.raises(ValueError, match="missing delivered_location.srs_name"):
            builder._extract_epsg_code(mock_cpt, "TEST-001")

    def test_malformed_srs_name_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location.srs_name = "INVALID_FORMAT"

        with pytest.raises(ValueError, match="malformed SRS name"):
            builder._extract_epsg_code(mock_cpt, "TEST-001")


class TestValidateAndSetEpsg:
    @patch("evo.data_converters.gef.converter.gef_to_downhole_collection.logger")
    def test_sets_epsg_on_first_file(self, mock_logger, builder, mock_cpt_data) -> None:
        builder._validate_and_set_epsg(mock_cpt_data, "CPT-001")

        assert builder.epsg_code == 28992
        assert mock_logger.info.called

    def test_consistent_epsg_passes(self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2) -> None:
        builder._validate_and_set_epsg(mock_cpt_data, "CPT-001")
        builder._validate_and_set_epsg(mock_cpt_data_2, "CPT-002")

        assert builder.epsg_code == 28992

    def test_inconsistent_epsg_raises_error(
        self, builder: DownholeCollectionBuilder, mock_cpt_data, mock_cpt_data_2
    ) -> None:
        builder._validate_and_set_epsg(mock_cpt_data, "CPT-001")
        mock_cpt_data_2.delivered_location.srs_name = "EPSG:4326"

        with pytest.raises(ValueError, match="Inconsistent EPSG codes"):
            builder._validate_and_set_epsg(mock_cpt_data_2, "CPT-002")


class TestValidateEpsgCode:
    def test_valid_epsg_passes(self, builder: DownholeCollectionBuilder) -> None:
        builder.epsg_code = 28992
        builder._validate_epsg_code()  # Should not raise

    def test_none_epsg_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        with pytest.raises(ValueError, match="Could not find valid epsg code"):
            builder._validate_epsg_code()


class TestValidateLocationAttributes:
    def test_valid_location_passes(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location.x = 100000.0
        mock_cpt.delivered_location.y = 500000.0

        builder._validate_location_attributes(mock_cpt, "TEST-001")

    def test_missing_x_raises_error(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location = Mock(spec=["y"])
        mock_cpt.delivered_location.y = 500000.0

        with pytest.raises(ValueError, match="missing required location attribute"):
            builder._validate_location_attributes(mock_cpt, "TEST-001")


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

    def test_returns_valid_attributes(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        attributes = builder._get_collar_attributes(mock_cpt_data)

        assert attributes["engineer"] == "Bob"
        assert attributes["wind_speed"] == 12.2
        assert attributes["signed_off"] is False
        assert attributes["report_date"] == datetime(2020, 10, 20)

    def test_filters_none_and_empty_values(self, builder: DownholeCollectionBuilder) -> None:
        mock_cpt = Mock()
        mock_cpt.delivered_location = Mock()
        mock_cpt.data = []
        mock_cpt.empty_list = []
        mock_cpt.empty_dict = {}
        mock_cpt.none_value = None
        mock_cpt.valid_value = "test"

        attributes = builder._get_collar_attributes(mock_cpt)

        assert "empty_list" not in attributes
        assert "empty_dict" not in attributes
        assert "none_value" not in attributes
        assert attributes["valid_value"] == "test"


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

        assert collar_row["engineer"] == "Bob"
        assert collar_row["wind_speed"] == 12.2


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
        assert "friction" in measurements.columns


class TestTrackNanValues:
    def test_tracks_nan_values_by_attribute(self, builder: DownholeCollectionBuilder, mock_cpt_data) -> None:
        builder._track_nan_values(mock_cpt_data)

        assert builder.nan_values_by_attribute["penetrationLength"] == [9999.0]
        assert builder.nan_values_by_attribute["coneResistance"] == [9999.0]
        assert builder.nan_values_by_attribute["friction"] == [9999.0]

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

        # cone_size only exists in the 3rd cpt file
        assert pd.isna(collars_df.iloc[0]["cone_size"])
        assert pd.isna(collars_df.iloc[1]["cone_size"])
        assert collars_df.iloc[2]["cone_size"] == 3.14

        # signed_off appears in the first two cpt files
        assert not collars_df.iloc[0]["signed_off"]
        assert collars_df.iloc[1]["signed_off"]
        assert pd.isna(collars_df.iloc[2]["signed_off"])


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
        assert builder._generate_collection_name() == "CPT-001"

    def test_multiple_collars_returns_range_format(self, builder: DownholeCollectionBuilder) -> None:
        builder.collar_rows = [
            {"hole_id": "CPT-001"},
            {"hole_id": "CPT-002"},
            {"hole_id": "CPT-003"},
        ]
        assert builder._generate_collection_name() == "CPT-001...CPT-003"


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
        assert result.name == "CPT-001"
        assert result.coordinate_reference_system == 28992
        assert len(result.measurements) == 1
        assert result.measurements[0].nan_values_by_column["penetrationLength"] == [9999.00]


class TestCreateFromParsedGefCpts:
    def test_empty_dict_raises_error(self) -> None:
        with pytest.raises(ValueError, match="No CPT files provided"):
            create_from_parsed_gef_cpts({})

    def test_single_cpt_creates_valid_collection(self, mock_cpt_data) -> None:
        parsed_files = {"CPT-001": mock_cpt_data}

        result = create_from_parsed_gef_cpts(parsed_files)

        assert isinstance(result, DownholeCollection)
        assert result.name == "CPT-001"
        assert result.coordinate_reference_system == 28992
        assert len(result.collars.df) == 1
        assert result.collars.df.iloc[0]["hole_id"] == "CPT-001"

    def test_multiple_cpts_creates_combined_collection(self, mock_cpt_data, mock_cpt_data_2) -> None:
        parsed_files = {"CPT-001": mock_cpt_data, "CPT-002": mock_cpt_data_2}

        result = create_from_parsed_gef_cpts(parsed_files)

        assert result.name == "CPT-001...CPT-002"
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
                    "friction": [j * 0.01 for j in range(20)],
                }
            )
            mock.column_void_mapping = {
                "penetrationLength": 9999.0,
                "coneResistance": 9999.0,
                "friction": 9999.0,
            }

            cpts[f"CPT-{i:03d}"] = mock

        result = create_from_parsed_gef_cpts(cpts)

        assert result.name == "CPT-001...CPT-005"
        assert len(result.collars.df) == 5
        assert len(result.measurements[0].df) == 100  # 5 CPTs * 20 measurements
        assert set(result.measurements[0].df["hole_index"].unique()) == {1, 2, 3, 4, 5}

    def test_multiple_cpts_custom_name(self, mock_cpt_data, mock_cpt_data_2) -> None:
        """Test with multiple CPT, use custom name."""
        parsed_files = {"CPT-001": mock_cpt_data, "CPT-002": mock_cpt_data_2}

        result = create_from_parsed_gef_cpts(parsed_files, name="Custom name")

        assert result.name == "Custom name"
        assert len(result.collars.df) == 2
        assert len(result.measurements[0].df) == 8  # 4 measurements each
        assert result.measurements[0].df["hole_index"].nunique() == 2
