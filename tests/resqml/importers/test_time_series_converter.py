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

import tempfile
from os import path
from typing import Any, cast
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import resqpy.grid as rqg
import resqpy.model as rqm
import resqpy.property as rqp
from evo_schemas.components import ContinuousTimeSeries_V1_0_1 as ContinuousTimeSeries
from resqpy.property import AttributePropertySet
from resqpy.time_series import GeologicTimeSeries, TimeSeries

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.resqml.importer._attribute_converters import create_category_lookup_and_data
from evo.data_converters.resqml.importer._time_series_converter import (
    _build_category_time_series,
    _build_continuous_time_series,
    _build_date_time_array,
    _build_time_step,
    _get_properties_and_date_times,
    _load_time_series,
    convert_time_series,
)


class TestTimeSeriesConverter(TestCase):
    """
    Tests for time_series_converter
    """

    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        meta_data = EvoWorkspaceMetadata(
            org_id="8ac3f041-b186-41f9-84ba-43d60f8683be",
            workspace_id="2cf1697f-2771-485e-848d-e6674d2ac63f",
            cache_root=self.cache_root_dir.name,
        )
        _, data_client = create_evo_object_service_and_data_client(meta_data)
        self.data_dir = tempfile.TemporaryDirectory()
        model_file = path.join(self.data_dir.name, "new_file.epc")
        model = rqm.new_model(model_file)

        self.data_client = data_client
        self.model = model
        self.model_file = model_file

        # Add a grid
        self.grid = rqg.RegularGrid(
            self.model,
            title="test_grid",
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        self.grid.write_hdf5()
        self.grid.create_xml(
            add_relationships=False, write_active=False, write_geometry=False, add_cell_length_properties=False
        )

    # --------------------------------------------------------------------------
    # Tests for convert_time_series
    #
    # -------------------------------------------------------------------------

    @patch("resqpy.model.Model.uuids")
    def test_convert_time_series(self, mock_model_uuids: MagicMock) -> None:
        # Given a PropertySet with 2 continuous properties
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)

        # Need to mock the calls to model.uuids,
        ps_uuid = uuid4()
        ps.create_property_set_xml("A title of some form", ps_uuid=ps_uuid)
        mock_model_uuids.return_value = [ps_uuid]

        # We would expect the property array to contain an entry for each cell
        expected_length = self.grid.nk * self.grid.nj * self.grid.ni

        # Then
        objs = convert_time_series(self.model, self.grid, None, self.data_client)

        # We would expect a continuous time series
        self.assertIsNotNone(objs)
        self.assertEqual(1, len(objs))
        ts = cast(ContinuousTimeSeries, objs[0])
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("continuous_time_series", ts.attribute_type)

        # With two time steps
        self.assertEqual(2, ts.num_time_steps)

        # and a value array with a column for each time step
        #                    and a row for each cell.
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(2, ts.values.width)
        self.assertEqual("float64", ts.values.data_type)

        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))
        d2 = self.read_column_from_parquet_file(ts.values.data, "t1")
        self.assertEqual(expected_length, len(d2))

    @patch("evo.data_converters.resqml.importer._time_series_converter._build_time_step")
    @patch("resqpy.model.Model.uuids")
    def test_convert_time_series_build_time_set_returns_none(
        self, mock_model_uuids: MagicMock, mock_build_time_step: MagicMock
    ) -> None:
        # Given a PropertySet with 2 continuous properties
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)

        # Need to mock the calls to uuids
        ps_uuid = uuid4()
        ps.create_property_set_xml("A title of some form", ps_uuid=ps_uuid)
        mock_model_uuids.return_value = [ps_uuid]

        # Build time step will return None, simulating an error
        mock_build_time_step.return_value = None

        # THEN
        objs = convert_time_series(self.model, self.grid, None, self.data_client)
        # We would expect an empty list
        self.assertIsNotNone(objs)
        self.assertEqual(0, len(objs))

    @patch("evo.data_converters.resqml.importer._time_series_converter._get_properties_and_date_times")
    @patch("resqpy.model.Model.uuids")
    def test_convert_time_series_get_properties_date_and_time_returns_none(
        self, mock_model_uuids: MagicMock, mock_get_properties_and_date_times: MagicMock
    ) -> None:
        # Given a PropertySet with 2 continuous properties
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)

        # Need to mock the calls to uuids
        ps_uuid = uuid4()
        ps.create_property_set_xml("A title of some form", ps_uuid=ps_uuid)
        mock_model_uuids.return_value = [ps_uuid]

        # Build get properties dat and times will return None, simulating an error
        mock_get_properties_and_date_times.return_value = None

        # THEN
        objs = convert_time_series(self.model, self.grid, None, self.data_client)
        # We would expect an empty list
        self.assertIsNotNone(objs)
        self.assertEqual(0, len(objs))

    @patch("resqpy.model.Model.uuids")
    def test_convert_time_series_multiple_time_series(self, mock_model_uuids: MagicMock) -> None:
        # Given a PropertySet with 2 continuous properties,
        # each with a different time series
        #
        series1 = self.time_series(daily=1)
        self.continuous_time_series_property(0, series1, "property_one")
        series2 = self.time_series(daily=1)
        self.continuous_time_series_property(1, series2, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)

        # Need to mock the calls to uuids, TODO pad this out
        ps_uuid = uuid4()
        ps.create_property_set_xml("A title of some form", ps_uuid=ps_uuid)
        mock_model_uuids.return_value = [ps_uuid]

        # THEN
        objs = convert_time_series(self.model, self.grid, None, self.data_client)

        # We would expect a continuous time series
        self.assertIsNotNone(objs)
        self.assertEqual(1, len(objs))
        ts = cast(ContinuousTimeSeries, objs[0])
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("continuous_time_series", ts.attribute_type)

        # With two time steps
        self.assertEqual(2, ts.num_time_steps)

        # and a value array with a column for each time step
        #                    and a row for each cell.
        expected_length = self.grid.nk * self.grid.nj * self.grid.ni
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(2, ts.values.width)
        self.assertEqual("float64", ts.values.data_type)

        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))
        d2 = self.read_column_from_parquet_file(ts.values.data, "t1")
        self.assertEqual(expected_length, len(d2))

    # --------------------------------------------------------------------------
    # Tests for _build_continuous_series
    #
    # -------------------------------------------------------------------------

    def test_build_continuous_time_series(self) -> None:
        # Given a PropertySet with 2 continuous properties
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # We would expect the property array to contain an entry for each cell
        expected_length = self.grid.nk * self.grid.nj * self.grid.ni

        # And to be able build a time step.
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # Then
        ts = _build_continuous_time_series(properties, "fred fred", step, None, self.data_client)
        # We would expect a time series to have been correctly constructed
        assert ts is not None
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("continuous_time_series", ts.attribute_type)

        # Containing the correct number of time steps
        self.assertEqual(step, ts.time_step)
        self.assertEqual(2, ts.num_time_steps)

        # And with a value array with the expected width
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(2, ts.values.width)
        self.assertEqual("float64", ts.values.data_type)

        # And with a value array with two columns of the expected length
        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))
        d2 = self.read_column_from_parquet_file(ts.values.data, "t1")
        self.assertEqual(expected_length, len(d2))

    def test_build_continuous_time_series_size_1(self) -> None:
        # Given a PropertySet with 1 continuous property
        series = self.time_series(daily=0)
        self.continuous_time_series_property(0, series, "property_one")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # We would expect the property array to contain an entry for each cell
        expected_length = self.grid.nk * self.grid.nj * self.grid.ni

        # And to be able build a time step.
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # THEN
        ts = _build_continuous_time_series(properties, "fred fred", step, None, self.data_client)
        # We would expect a time series to have been correctly constructed
        assert ts is not None
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("continuous_time_series", ts.attribute_type)

        # Containing the correct number of time steps
        self.assertEqual(step, ts.time_step)
        self.assertEqual(1, ts.num_time_steps)

        # And with a value array with the expected width
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(1, ts.values.width)
        self.assertEqual("float64", ts.values.data_type)

        # And with a value array with one column of the expected length
        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))

    def test_build_continuous_time_series_with_points_properties(self) -> None:
        # Given a PropertySet containing a points_property
        # Which are not currently supported for TimeSeries
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.points_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # We should still be able to build a time step
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # THEN
        ts = _build_continuous_time_series(properties, "fred fred", step, None, self.data_client)
        # We would NOT expect a TimeSeries to be built.
        self.assertIsNone(ts)

    def test_build_continuous_time_series_discrete_properties(self) -> None:
        # Given a PropertySet containing two discrete properties
        series = self.time_series(daily=1)
        self.discrete_time_series_property(0, series, "property_one")
        self.discrete_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # We would expect the property array to contain an entry for each cell
        expected_length = self.grid.nk * self.grid.nj * self.grid.ni

        # And to be able to build the time step
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # THEN
        ts = _build_continuous_time_series(properties, "fred fred", step, None, self.data_client)
        # We should have created a Continuous time series, from the discrete properties
        assert ts is not None

        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("continuous_time_series", ts.attribute_type)

        self.assertEqual(step, ts.time_step)
        self.assertEqual(2, ts.num_time_steps)

        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(2, ts.values.width)
        #  And the discrete values (integers) to have been mapped to float64
        self.assertEqual("float64", ts.values.data_type)

        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))
        d2 = self.read_column_from_parquet_file(ts.values.data, "t1")
        self.assertEqual(expected_length, len(d2))

    def test_build_continuous_time_series_number_values_ne_time_steps(self) -> None:
        # Given a PropertySet where the number of time steps differs from the
        # number of properties
        series = self.time_series(daily=2)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # Should be able to build the time step
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # THEN
        ts = _build_continuous_time_series(properties, "fred fred", step, None, self.data_client)
        # Should not have built a time series
        self.assertIsNone(ts)

    def test_build_continuous_time_series_include_set(self) -> None:
        # Given a PropertySet with two properties
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # Should be able to build the time step
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # Include is set to one cell [1,1,1]
        ts = _build_continuous_time_series(properties, "fred fred", step, ([1], [1], [1]), self.data_client)  # pyright: ignore
        # Then a continuous time series was created
        assert ts is not None
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("continuous_time_series", ts.attribute_type)

        # The number of time steps is 2
        self.assertEqual(step, ts.time_step)
        self.assertEqual(2, ts.num_time_steps)

        # There will be two property columns, and one row. As we've only included one cell.
        expected_length = 1
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(2, ts.values.width)
        self.assertEqual("float64", ts.values.data_type)

        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))
        d2 = self.read_column_from_parquet_file(ts.values.data, "t1")
        self.assertEqual(expected_length, len(d2))

    # --------------------------------------------------------------------------
    # Tests for _build_time_step
    #
    # -------------------------------------------------------------------------

    def test_build_time_step(self) -> None:
        # Given a property set with 2 time steps, and two continuous properties
        series = self.time_series(daily=1)

        ts = _build_time_step(series.timestamps, "test", self.data_client)
        # THEN should build a time step
        assert ts is not None

        # With the expected name, and data type
        self.assertIsNotNone(ts)
        self.assertEqual("test-TimeStep", ts.name)
        self.assertEqual("date_time", ts.attribute_type)

        # And it should have written the values to a parquet file.
        data = self.read_column_from_parquet_file(ts.values.data, "data")
        self.assertEqual(2, len(data))

    def test_build_time_step_invalid_timestamps(self) -> None:
        ts = _build_time_step(["Not a date"], "test", self.data_client)
        # THEN should not build a time step
        assert ts is None

    # --------------------------------------------------------------------------
    # Tests for _build_date_time_array
    #
    # -------------------------------------------------------------------------

    def test_build_date_time_array_from_empty_list(self) -> None:
        # Given an empty date list
        dates: list[str] = list()

        # Then the date time array should be empty
        dta = _build_date_time_array(dates, self.data_client)
        assert dta is not None
        self.assertEqual(0, dta.length)
        self.assertEqual("timestamp", dta.data_type)

    def test_build_date_time_array_one_date(self) -> None:
        # Given a list with a single date
        dates = ["2000-02-01T04:05:06Z"]

        # Then the date array should have one entry
        dta = _build_date_time_array(dates, self.data_client)
        assert dta is not None
        self.assertEqual(1, dta.length)
        self.assertEqual("timestamp", dta.data_type)

        # and it should be 2000-02-01T04:05:06 UTC
        data = self.read_column_from_parquet_file(dta.data, "data")
        self.assertEqual(1, len(data))
        date = data[0]
        self.assertEqual(2000, date.year)
        self.assertEqual(2, date.month)
        self.assertEqual(1, date.day)
        self.assertEqual(4, date.hour)
        self.assertEqual(5, date.minute)
        self.assertEqual(6, date.second)
        self.assertEqual("UTC", date.tzname())

    def test_build_date_time_array_one_date_non_utc_time_zone(self) -> None:
        # Given a list with a single date and a +12:00 time zone
        dates = ["2000-02-03T04:05:06+12:00"]

        # Then there should be one date
        dta = _build_date_time_array(dates, self.data_client)
        assert dta is not None
        self.assertEqual(1, dta.length)
        self.assertEqual("timestamp", dta.data_type)

        # And it should be 2000-02-02t:16:05:06 UTC,
        #
        data = self.read_column_from_parquet_file(dta.data, "data")
        self.assertEqual(1, len(data))
        date = data[0]
        self.assertEqual(2000, date.year)
        self.assertEqual(2, date.month)
        self.assertEqual(2, date.day)
        self.assertEqual(16, date.hour)
        self.assertEqual(5, date.minute)
        self.assertEqual(6, date.second)
        self.assertEqual("UTC", date.tzname())

    def test_build_date_time_array_one_date_mixed_time_zone(self) -> None:
        # Given a list with 2 dates with differing time zones
        dates: list[str] = ["2000-02-03T04:05:06+12:00", "2001-03-01T06:01:01+02:00"]

        # Then there should be two date times
        dta = _build_date_time_array(dates, self.data_client)
        assert dta is not None
        self.assertEqual(2, dta.length)
        self.assertEqual("timestamp", dta.data_type)

        # And they should have been converted to UTC
        data = self.read_column_from_parquet_file(dta.data, "data")
        self.assertEqual(2, len(data))
        date = data[0]
        self.assertEqual(2000, date.year)
        self.assertEqual(2, date.month)
        self.assertEqual(2, date.day)
        self.assertEqual(16, date.hour)
        self.assertEqual(5, date.minute)
        self.assertEqual(6, date.second)
        self.assertEqual("UTC", date.tzname())

        date = data[1]
        self.assertEqual(2001, date.year)
        self.assertEqual(3, date.month)
        self.assertEqual(1, date.day)
        self.assertEqual(4, date.hour)
        self.assertEqual(1, date.minute)
        self.assertEqual(1, date.second)
        self.assertEqual("UTC", date.tzname())

    def test_build_date_time_array_invalid_date_time(self) -> None:
        # Given a list with a valid date and an invalid date
        dates = ["2000-02-03T04:05:06+12:00", "no actually a date"]

        # Then None should be returned
        dta = _build_date_time_array(dates, self.data_client)
        self.assertIsNone(dta)

    def test_build_date_time_array_date_time_white_space(self) -> None:
        # Given a list with a valid date and a date that's all white space
        dates = ["2000-02-03T04:05:06+12:00", "    "]

        # Then None should be returned
        dta = _build_date_time_array(dates, self.data_client)
        self.assertIsNone(dta)

    def test_build_date_time_array_date_time_empty_string(self) -> None:
        # Given a list with a valid date and a date that's an empty string
        dates = ["2000-02-03T04:05:06+12:00", ""]

        # Then None should be returned
        dta = _build_date_time_array(dates, self.data_client)
        self.assertIsNone(dta)

    def test_build_date_time_array_date_time_None(self) -> None:
        # Given a list with a valid date and a date that's None
        dates = ["2000-02-03T04:05:06+12:00", None]

        # Then None should be returned
        dta = _build_date_time_array(dates, self.data_client)
        self.assertIsNone(dta)

    def test_build_date_time_array_one_date_no_time_zone(self) -> None:
        # Given a list with a single date and no time zone
        dates = ["2000-02-03T04:05:06"]

        # Then there should be one date time
        dta = _build_date_time_array(dates, self.data_client)
        assert dta is not None
        self.assertEqual(1, dta.length)
        self.assertEqual("timestamp", dta.data_type)

        # And the time zone should have defaulted to UTC
        data = self.read_column_from_parquet_file(dta.data, "data")
        self.assertEqual(1, len(data))
        date = data[0]
        self.assertEqual(2000, date.year)
        self.assertEqual(2, date.month)
        self.assertEqual(3, date.day)
        self.assertEqual(4, date.hour)
        self.assertEqual(5, date.minute)
        self.assertEqual(6, date.second)

        self.assertEqual("UTC", date.tzname())

    # --------------------------------------------------------------------------
    # Tests for _load_time_series
    #
    # -------------------------------------------------------------------------
    def test_load_time_series_one_series(self) -> None:
        # Given a PropertySet with 2 continuous properties
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        ps.create_property_set_xml("test")

        ts = _load_time_series(self.model, ps)

        # THEN
        # ts should have one value
        self.assertIsNotNone(ts)
        self.assertEqual(1, len(ts))
        # ts should contain an entry for series
        self.assertTrue(str(series.uuid) in ts)

        # it should have two time stamps
        self.assertEqual(2, len(ts[str(series.uuid)]))

    def test_load_time_series_two_series(self) -> None:
        # Given a PropertySet with 2 continuous properties each with a different time series
        series1 = self.time_series(first_timestamp="2000-01-01T00:00:00", daily=2)
        series2 = self.time_series(first_timestamp="2001-01-01T00:00:00", daily=3)

        # NOTE: resqpy keys the properties in a property set by
        #       property kind and index. Duplicate keys are ignored
        #       so we need to have different indexes.
        self.continuous_time_series_property(0, series1, "property_one")
        self.continuous_time_series_property(1, series2, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        ps.create_property_set_xml("test")

        ts = _load_time_series(self.model, ps)

        # THEN
        # ts should have two values
        self.assertIsNotNone(ts)
        # ts should contain entries for series1 and series2
        self.assertTrue(str(series1.uuid) in ts)
        self.assertTrue(str(series2.uuid) in ts)

        # and each should contain a single time stamp
        self.assertEqual(3, len(ts[str(series1.uuid)]))
        self.assertEqual(4, len(ts[str(series2.uuid)]))

    @patch("evo.data_converters.resqml.importer._time_series_converter._load_timestamps")
    def test_load_time_series_load_timestamps_error(self, mock_load_timestamps: MagicMock) -> None:
        # Given a PropertySet with 2 continuous properties
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one")
        self.continuous_time_series_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        ps.create_property_set_xml("test")

        # And load_timestamps returns None
        mock_load_timestamps.return_value = None
        ts = _load_time_series(self.model, ps)

        # THEN
        # ts should be none
        self.assertEqual(0, len(ts))

    # --------------------------------------------------------------------------
    # Tests for _get_properties_and_date_times
    #
    # -------------------------------------------------------------------------
    def test_get_properties_and_date_times(self) -> None:
        # Given a PropertySet with 2 continuous properties of the same kind
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one", kind="saturation")
        self.continuous_time_series_property(1, series, "property_two", kind="saturation")
        ps = AttributePropertySet(self.model, support=self.grid)
        ps.create_property_set_xml("test")

        # Should be able to load the time series
        ts = _load_time_series(self.model, ps)

        ds = _get_properties_and_date_times(ps, "saturation", ts, "test")

        # Then
        # the list should be sorted in ascending date order
        self.assertTrue(all(ds[i][0] <= ds[i + 1][0] for i in range(len(ds) - 1)))
        # it should contain 2 entries
        self.assertEqual(2, len(ds))
        # And they should correspond to the properties in the Property Set
        self.assertEqual("property_one", ds[0][1].title)
        self.assertEqual("property_two", ds[1][1].title)

    def test_get_properties_and_date_times_multiple_kinds(self) -> None:
        # Given a PropertySet with 2 continuous properties with different kinds
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one", kind="porosity")
        self.continuous_time_series_property(1, series, "property_two", kind="saturation")
        ps = AttributePropertySet(self.model, support=self.grid)
        ps.create_property_set_xml("test")

        # Should be able to load the time series
        ts = _load_time_series(self.model, ps)

        ds = _get_properties_and_date_times(ps, "saturation", ts, "test")

        # Then
        # the list should be sorted in ascending date order
        self.assertTrue(all(ds[i][0] <= ds[i + 1][0] for i in range(len(ds) - 1)))
        # it should contain 1 entry
        self.assertEqual(1, len(ds))
        # And it should be the second property
        self.assertEqual("property_two", ds[0][1].title)

    def test_get_properties_and_date_times_kinds_not_matched(self) -> None:
        # Given a PropertySet with 2 continuous properties of the same kind "porosity"
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one", kind="saturation")
        self.continuous_time_series_property(1, series, "property_two", kind="saturation")
        ps = AttributePropertySet(self.model, support=self.grid)
        ps.create_property_set_xml("test")

        # Should be able to load the time series
        ts = _load_time_series(self.model, ps)

        # When we try to get the values for "porosity"
        ds = _get_properties_and_date_times(ps, "porosity", ts, "test")

        # Then
        # There should not be any matching entries
        self.assertEqual(0, len(ds))

    def test_get_properties_and_date_times_non_time_series_property(self) -> None:
        # Given a PropertySet with 2 continuous properties of the same kind, one without a time series
        series = self.time_series(daily=1)
        self.continuous_time_series_property(0, series, "property_one", kind="saturation")
        self.continuous_property("property_two", kind="saturation")
        ps = AttributePropertySet(self.model, support=self.grid)
        ps.create_property_set_xml("test")

        # Should be able to load the time series
        ts = _load_time_series(self.model, ps)

        ds = _get_properties_and_date_times(ps, "saturation", ts, "test")

        # Then
        # the list should be sorted in ascending date order
        self.assertTrue(all(ds[i][0] <= ds[i + 1][0] for i in range(len(ds) - 1)))
        # it should contain 1 entry
        self.assertEqual(1, len(ds))
        # And it should correspond to property one
        self.assertEqual("property_one", ds[0][1].title)

    # --------------------------------------------------------------------------
    # Tests for _build_category_series
    #
    # -------------------------------------------------------------------------

    def test_build_category_time_series(self) -> None:
        # Given a PropertySet with 2 category properties
        series = self.time_series(daily=1)
        lookup = self.lookup_table()
        self.category_property(0, series, lookup, "property_one")
        self.category_property(1, series, lookup, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # We would expect the property array to contain an entry for each cell
        expected_length = self.grid.nk * self.grid.nj * self.grid.ni

        # And to be able build a time step.
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # Then
        ts = _build_category_time_series(self.model, properties, "fred fred", step, None, self.data_client)
        # We would expect a time series to have been correctly constructed
        assert ts is not None
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("categoral_time_series", ts.attribute_type)

        # Containing the correct number of time steps
        self.assertEqual(step, ts.time_step)
        self.assertEqual(2, ts.num_time_steps)

        # And with a value array with the expected width
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(2, ts.values.width)
        self.assertEqual("int64", ts.values.data_type)

        # And with a value array with two columns of the expected length
        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))
        d2 = self.read_column_from_parquet_file(ts.values.data, "t1")
        self.assertEqual(expected_length, len(d2))

    def test_build_category_time_series_size_1(self) -> None:
        # Given a PropertySet with 1 categorical property
        series = self.time_series(daily=0)
        lookup = self.lookup_table()
        self.category_property(0, series, lookup, "property_one")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # We would expect the property array to contain an entry for each cell
        expected_length = self.grid.nk * self.grid.nj * self.grid.ni

        # And to be able build a time step.
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # THEN
        ts = _build_category_time_series(self.model, properties, "fred fred", step, None, self.data_client)
        # We would expect a time series to have been correctly constructed
        assert ts is not None
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("categoral_time_series", ts.attribute_type)

        # Containing the correct number of time steps
        self.assertEqual(step, ts.time_step)
        self.assertEqual(1, ts.num_time_steps)

        # And with a value array with the expected width
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(1, ts.values.width)
        self.assertEqual("int64", ts.values.data_type)

        # And with a value array with one column of the expected length
        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))

    def test_build_category_time_series_time_steps_ne_properties(self) -> None:
        # Given a PropertySet with 2 category properties, but 3 time steps
        series = self.time_series(daily=2)
        lookup = self.lookup_table()
        self.category_property(0, series, lookup, "property_one")
        self.category_property(1, series, lookup, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # And to be able build a time step.
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # Then
        ts = _build_category_time_series(self.model, properties, "fred fred", step, None, self.data_client)
        # We would NOT expect a time series to have been correctly constructed
        self.assertIsNone(ts)

    def test_build_category_time_series_time_steps_different_lookup_tables(self) -> None:
        # Given a PropertySet with 2 category properties, with different lookup tables
        series = self.time_series(daily=1)
        lookup1 = self.lookup_table()
        lookup2 = self.lookup_table()
        self.category_property(0, series, lookup1, "property_one")
        self.category_property(1, series, lookup2, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # And to be able build a time step.
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # Then
        ts = _build_category_time_series(self.model, properties, "fred fred", step, None, self.data_client)
        # We would NOT expect a time series to have been correctly constructed
        self.assertIsNone(ts)

    def test_build_category_time_series_with_points_properties(self) -> None:
        # Given a PropertySet containing a points_property
        # Which are not currently supported for TimeSeries
        series = self.time_series(daily=1)
        lookup = self.lookup_table()
        self.category_property(0, series, lookup, "property_one")
        self.points_property(1, series, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # We should still be able to build a time step
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # THEN
        ts = _build_category_time_series(self.model, properties, "fred fred", step, None, self.data_client)
        # We would NOT expect a TimeSeries to be built.
        self.assertIsNone(ts)

    def test_build_category_time_series_include_set(self) -> None:
        # Given a PropertySet with two properties
        series = self.time_series(daily=1)
        lookup = self.lookup_table()
        self.category_property(0, series, lookup, "property_one")
        self.category_property(1, series, lookup, "property_two")
        ps = AttributePropertySet(self.model, support=self.grid)
        properties = [*ps.properties()]

        # Should be able to build the time step
        step = _build_time_step(series.timestamps, "test", self.data_client)
        assert step is not None

        # Include is set to one cell [1,1,1]
        ts = _build_category_time_series(self.model, properties, "fred fred", step, ([1], [1], [1]), self.data_client)  # pyright: ignore
        # Then a categorical time series was created
        assert ts is not None
        self.assertIsNotNone(ts)
        self.assertIsNotNone(ts.key)
        self.assertEqual("categoral_time_series", ts.attribute_type)

        # The number of time steps is 2
        self.assertEqual(step, ts.time_step)
        self.assertEqual(2, ts.num_time_steps)

        # There will be two property columns, and one row. As we've only included one cell.
        expected_length = 1
        self.assertEqual(expected_length, ts.values.length)
        self.assertEqual(2, ts.values.width)
        self.assertEqual("int64", ts.values.data_type)

        d1 = self.read_column_from_parquet_file(ts.values.data, "t0")
        self.assertEqual(expected_length, len(d1))
        d2 = self.read_column_from_parquet_file(ts.values.data, "t1")
        self.assertEqual(expected_length, len(d2))

    # --------------------------------------------------------------------------
    # Test helper functions
    #
    # -------------------------------------------------------------------------

    def time_series(
        self, first_timestamp: str = "2000-01-01T00:00:00", daily: int = 30, title: str = str(uuid4())
    ) -> TimeSeries:
        """Build a time series"""
        ts = TimeSeries(self.model, first_timestamp=first_timestamp, daily=daily, title=title)
        ts.create_xml()
        self.assertIsNotNone(ts.uuid)
        return ts

    def geologic_time_series(self) -> GeologicTimeSeries:
        """Build a geologic time series"""
        ts = GeologicTimeSeries(self.model)
        ts.create_xml()
        self.assertIsNotNone(ts.uuid)
        return ts

    def continuous_time_series_property(
        self, index: int, ts: TimeSeries, name: str, kind: str = "porosity"
    ) -> rqp.Property:
        """build a continuous time series property"""

        self.assertIsNotNone(ts.uuid)
        property = rqp.Property.from_array(
            self.model,
            np.random.random(self.grid.extent_kji).astype(np.float64),
            source_info="test data",
            property_kind=kind,
            discrete=False,
            indexable_element="cells",
            keyword=name,
            support_uuid=self.grid.uuid,
            time_series_uuid=ts.uuid,
            time_index=index,
            uom="m",
        )
        property.create_xml()
        self.assertTrue(property.is_continuous())
        self.assertIsNotNone(property.time_series_uuid())
        self.assertEqual(property.time_series_uuid(), ts.uuid)
        return property

    def continuous_property(self, name: str, kind: str = "porosity") -> rqp.Property:
        """build a time series property"""

        property = rqp.Property.from_array(
            self.model,
            np.random.random(self.grid.extent_kji).astype(np.float64),
            source_info="test data",
            property_kind=kind,
            discrete=False,
            indexable_element="cells",
            keyword=name,
            support_uuid=self.grid.uuid,
            uom="m",
        )
        property.create_xml()
        self.assertTrue(property.is_continuous())
        return property

    def discrete_time_series_property(self, index: int, ts: TimeSeries, name: str) -> rqp.Property:
        """build a discrete time series property"""

        self.assertIsNotNone(ts.uuid)
        property = rqp.Property.from_array(
            self.model,
            np.random.random(self.grid.extent_kji).astype(np.int64),
            source_info="test data",
            property_kind="DiscreteProperty",
            discrete=False,
            indexable_element="cells",
            keyword=name,
            support_uuid=self.grid.uuid,
            time_series_uuid=ts.uuid,
            time_index=index,
            uom="m",
        )
        property.create_xml()
        self.assertTrue(property.is_continuous())
        self.assertIsNotNone(property.time_series_uuid())
        self.assertEqual(property.time_series_uuid(), ts.uuid)
        return property

    def points_property(self, index: int, ts: TimeSeries, name: str) -> rqp.Property:
        """create a points property"""
        property = rqp.Property.from_array(
            self.model,
            np.random.randn(self.grid.nk, self.grid.nj, self.grid.ni, 3),
            points=True,
            source_info="test data",
            property_kind="PointsProperty",
            indexable_element="cells",
            keyword=name,
            support_uuid=self.grid.uuid,
            time_series_uuid=ts.uuid,
            time_index=index,
            uom="m",
        )
        self.assertTrue(property.is_points())
        return property

    def read_column_from_parquet_file(self, pq_hash: str, column: str) -> Any:
        df = pq.read_table(path.join(self.data_client.cache_location, pq_hash))
        return df.column(column).to_pylist()

    def lookup_table(self) -> rqp.StringLookup:
        # create a set of category labels
        lookup = rqp.StringLookup(self.model)
        lookup.set_string("0", "sandstone")
        lookup.set_string("1", "shale")
        lookup.set_string("2", "limestone")
        lookup.create_xml()

        # save the RESQML lookup table for tests
        lookup_as_dict = lookup.as_dict()
        indices = list(lookup_as_dict.keys())
        names = lookup_as_dict.values()
        df = pd.DataFrame({"data": names, "index": indices})
        df.set_index("index", inplace=True)
        create_category_lookup_and_data(df)

        return lookup

    def category_property(self, index: int, ts: TimeSeries, lookup: rqp.StringLookup, name: str) -> rqp.Property:
        """Build a category property"""

        # randomly assign a category to each cell
        property = rqp.Property.from_array(
            self.model,
            np.random.randint(0, 3, size=self.grid.extent_kji),
            discrete=True,
            source_info="test data",
            property_kind="CategoricalProperty",
            indexable_element="cells",
            keyword=name,
            support_uuid=self.grid.uuid,
            string_lookup_uuid=lookup.uuid,
            time_series_uuid=ts.uuid,
            time_index=index,
        )
        self.assertTrue(property.is_categorical())
        return property
