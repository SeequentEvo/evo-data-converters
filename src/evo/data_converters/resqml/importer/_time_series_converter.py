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

import datetime
from typing import Optional, cast
from uuid import uuid4

import numpy as np
import numpy.typing as npt
import pandas as pd
import pyarrow as pa
import resqpy.olio.xml_et as rqet
from dateutil.parser import ParserError, isoparse
from evo_schemas.components import CategoryTimeSeries_V1_0_1 as CategoryTimeSeries
from evo_schemas.components import ContinuousTimeSeries_V1_0_1 as ContinuousTimeSeries
from evo_schemas.components import NanCategorical_V1_0_1 as NanCategorical
from evo_schemas.components import NanContinuous_V1_0_1 as NanContinuous
from evo_schemas.components import OneOfAttribute_V1_1_0 as OneOfAttribute
from evo_schemas.components import TimeStepDateTimeAttribute_V1_0_1 as TimeStepDateTimeAttribute
from evo_schemas.elements import DateTimeArray_V1_0_1 as DateTimeArray
from evo_schemas.elements import FloatArrayMd_V1_0_1 as FloatArrayMd
from evo_schemas.elements import IntegerArrayMd_V1_0_1 as IntegerArrayMd
from evo_schemas.elements import LookupTable_V1_0_1 as LookupTable
from lxml.etree import Element
from resqpy.grid import Grid
from resqpy.model import Model
from resqpy.property import ApsProperty, AttributePropertySet, StringLookup

import evo.logging
from evo.data_converters.resqml.importer._attribute_converters import create_category_lookup_and_data
from evo.objects.utils.data import ObjectDataClient

logger = evo.logging.getLogger("data_converters.resqml")


def convert_time_series(
    model: Model,
    parent: Grid,
    include: Optional[tuple[npt.NDArray[np.int_], npt.NDArray[np.int_], npt.NDArray[np.int_]]],
    data_client: ObjectDataClient,
) -> OneOfAttribute:
    """Convert the parents time series properties to the corresponding Evo Geoscience objects

    :param model: The resqpy model, representing the file being converted
    :param parent: The resqpy object containing the time series
    :param include: tuple of three arrays, one for each dimension k, j, i
                    containing the indices of the elements included in each dimension.
                    [k[n], j[n], i[n]] forms the index for cell[n]
    :param data_client: ObjectDataClient used to create the properties

    :returns: list of Evo time series objects for the parent.

    Notes/Assumptions:
        - A PropertySet can contain multiple time series
        - All properties with the same property kind belong to the same
          time series
          This is build into resqpy as the keys built, are property_kind + time_index
          Note: this means that two properties that have different time series but the same time index
                will be treated as the same property (first one processed wins)

    """

    assert parent is not None
    time_series: OneOfAttribute = []
    property_set_uuids = model.uuids(related_uuid=parent.uuid, obj_type="PropertySet")
    for uuid in property_set_uuids:
        try:
            property_set = AttributePropertySet(model, property_set_uuid=uuid, support=parent)
            ts = _load_time_series(model, property_set)
            kinds = property_set.property_kind_list()
            for kind in kinds:
                name = _build_name(model, kind, uuid)

                properties_and_date_times = _get_properties_and_date_times(property_set, kind, ts, name)
                if not properties_and_date_times:
                    # No properties for kind found, it's been logged, so we'll ignore it and continue
                    continue
                # mypy gets confused with the usage of zip to unpack the list of tuples into a tupple
                # of lists so use an explicit cast
                (date_times, properties) = cast(tuple[list[str], list[ApsProperty]], zip(*properties_and_date_times))

                time_step = _build_time_step(date_times, name, data_client)
                if time_step is None:
                    continue

                # The properties for a kind are assumed to be the same type
                # so inspect the first member of the set to determine the type.
                # The converters will fail if a property is not of the correct type.
                property = properties[0]
                if property.is_categorical:
                    series = _build_category_time_series(model, properties, name, time_step, include, data_client)
                elif property.is_discrete:
                    # As there is no Evo integer time series we map Discrete time series to floating point
                    # log a warning about potential loss of precision
                    logger.warning(
                        f"The Property Set {name} is discrete, i.e. it has integer values."
                        "These will be converted to floating point and there may be some loss of precision for large values"
                    )
                    series = _build_continuous_time_series(properties, name, time_step, include, data_client)
                elif property.is_continuous:
                    series = _build_continuous_time_series(properties, name, time_step, include, data_client)
                else:
                    logger.warning(
                        f"Ignoring Property set {name} for {parent.citation_title}, as it is not a supported type"
                    )
                    continue
                if series is not None:
                    time_series.append(series)
        except AssertionError as err:
            logger.error(f"Unable to convert property set {uuid}: {err}")
    return time_series


def _build_name(model: Model, kind: str, uuid: str) -> str:
    """Build a name for the Evo TimeSeries

    :param model: The resqpy model, representing the file being converted
    :param kind: The RESQML property kind, i.e. 'saturation'
    :param uuid: The uuid of the RESQML AttributePropertySet, containing the property

    :return: the name for the TimeSeries

    """
    title = model.title_for_part(model.part_for_uuid(uuid))
    name: str
    if title is not None:
        name = title + "-" + kind
    else:
        name = "TimeSeries-" + uuid + "-" + kind
    return name


def _get_properties_and_date_times(
    ps: AttributePropertySet, kind: str, ts: dict[str, list[str]], name: str
) -> list[tuple[str, ApsProperty]]:
    """Extract all the properties and associated timestamps for the supplied kind from the property set

    :param ps: The AttributePropertySet containing the properties
    :param kind: The target kind
    :param name: The Time series name, if we need to log a diagnostic

    :return: list of (date_time, property) tuples, sorted in ascending date_time order
             Where: date_time is an ISO8601 date string

    """
    pl = list()
    for property in ps.properties():
        if property.property_kind != kind:
            continue
        if property.time_series_uuid is None:
            # Ignore any properties without a time series, they'll be handled
            # by the non time series property conversion for their parent
            continue
        pl.append((ts[str(property.time_series_uuid)][property.time_index], property))
    if len(pl) == 0:
        logger.warning(f"No properties of kind {kind} in Property Set {name}")
        return pl
    pl.sort()  # sort into ascending date time order
    return pl


def _load_time_series(model: Model, ps: AttributePropertySet) -> dict[str, list[str]]:
    """Load all the time series associated with a PropertySet

    :param model: The resqpy model, representing the file being converted
    :param ps: The AttributePropertySet containing the properties

    :return: A dictionary keyed by the time series uuid of the date time strings in that time series

    """

    time_series = dict()
    for property in ps.properties():
        uuid = property.time_series_uuid
        if uuid and uuid not in time_series:
            root = model.root_for_uuid(uuid)
            ts = _load_timestamps(root)
            if ts is not None:
                time_series[str(uuid)] = ts
    return time_series


def _build_time_step(
    date_times: list[str], name: str, data_client: ObjectDataClient
) -> Optional[TimeStepDateTimeAttribute]:
    """Build an Evo TimeStepDateTimeAttribute

    :param date_times: A list of ISO8601 date strings
    :param name: The time series name
    :param data_client: ObjectDataClient used to create the properties

    :return: The constructed TimeStep attribute, or None if there was an
             error.

    """
    dta = _build_date_time_array(date_times, data_client)
    if dta is None:
        return None
    return TimeStepDateTimeAttribute(name=name + "-TimeStep", values=dta)


def _build_date_time_array(values: list[str], data_client: ObjectDataClient) -> Optional[DateTimeArray]:
    """Build an Evo DateTimeArray from a list of date time strings

    :param values: The attribute date time strings, in ISO8601 format
    :param data_client: ObjectDataClient used to create the attribute

    :return: A DateTimeArray
             Or None if any of the date time strings are invalid
    """

    try:
        # Parse the input date strings
        timestamps = [isoparse(s) for s in values]
        # Default any missing time zones to UTC, to prevent the
        # local time zone being used.
        with_default_time_zones = [t.replace(tzinfo=t.tzinfo or datetime.timezone.utc) for t in timestamps]
        # convert the times to UTC
        utc = [t.astimezone(datetime.timezone.utc) for t in with_default_time_zones]
    except (ParserError, OverflowError, ValueError, TypeError) as err:
        logger.error(f"Invalid date in time series: {err}")
        return None

    # Write the date times to parquet
    schema = pa.schema([("data", pa.timestamp("us", "UTC"))])
    table = pa.Table.from_arrays([utc], schema=schema)
    va = data_client.save_table(table)

    # Build an return a DateTimeArray
    return DateTimeArray.from_dict(va)


def _load_timestamps(root: Element) -> Optional[list[str]]:
    """Load the timestamps for a time series directly from the XML
    :param root: the resqpy XML root for the timestamps
    :return: a list of ISO8601 formatted date time strings
             or None if an error was encountered
    """
    timestamps: list[str] = []
    children = rqet.list_of_tag(root, "Time")
    if children is None:
        return timestamps
    for child in children:
        dt_text = rqet.find_tag_text(child, "DateTime")
        if not dt_text:
            logger.error("Missing DateTime field in xml for time series")
            return None
        timestamps.append(dt_text.strip())

        year_offset = rqet.find_tag_int(child, "YearOffset")
        if year_offset:
            logger.warning("Geologic time series are not currently supported")
            return None
    return timestamps


def _build_continuous_time_series(
    properties: list[ApsProperty],
    name: str,
    time_step: TimeStepDateTimeAttribute,
    include: Optional[tuple[npt.NDArray[np.int_], npt.NDArray[np.int_], npt.NDArray[np.int_]]],
    data_client: ObjectDataClient,
) -> Optional[ContinuousTimeSeries]:
    """Build a continuous time series.

    :param properties: A list of resqpy ApsProperties containing the properties for the series
    :param name: The name of the property set, displayed in diagnostics
    :param time_step: an Evo Time Step object, there should be one date time for each property
    :param include: tuple of three arrays, one for each dimension k, j, i
                    containing the indices of the elements included in each dimension.
                    [k[n], j[n], i[n]] forms the index for cell[n]
    :param data_client: ObjectDataClient used to create the properties

    :return: ContinuousTimeSeries or None if there was an error
    """
    arrays = []
    nan_values = set()
    steps = time_step.values.length
    # Iterate through the properties in the property set, extracting their value arrays
    for p in properties:
        if p.is_categorical or p.is_points:
            logger.error(
                f"Unexpected type for Property {p.citation_title} in Property Set {name}, the Time series will be ignored"
            )
            return None
        array_values = p.array_ref[include] if include else p.array_ref
        flattened_values = np.array(array_values).astype(np.float64).flatten(order="C")
        arrays.append(flattened_values)
        # Only discrete properties will have an null_value
        # for continuous values the null value is always nan.
        if p.is_discrete and p.null_value is not None:
            nan_values.add(p.null_value)

    if steps != len(arrays):
        logger.error(
            f"Number of time steps {steps} does not equal number of properties {len(arrays)}, in Property Set {name}, the Time series will be ignored"
        )
        return None

    # Build a Float array to contain the values
    schema = pa.schema([pa.field("t" + str(n), pa.float64()) for n in range(steps)])
    table = pa.Table.from_arrays(arrays, schema=schema)
    va = data_client.save_table(table)
    values = FloatArrayMd.from_dict(va)

    series = ContinuousTimeSeries(
        values=values,
        time_step=time_step,
        num_time_steps=steps,
        key=str(uuid4()),
        nan_description=NanContinuous(values=list(nan_values)),
    )
    return series


def _build_category_time_series(
    model: Model,
    properties: list[ApsProperty],
    name: str,
    time_step: TimeStepDateTimeAttribute,
    include: Optional[tuple[npt.NDArray[np.int_], npt.NDArray[np.int_], npt.NDArray[np.int_]]],
    data_client: ObjectDataClient,
) -> Optional[CategoryTimeSeries]:
    """Build a category time series.

    :param model: The resqpy model, representing the file being converted
    :param properties: A list of resqpy ApsProperties containing the properties for the series
    :param name: The name of the property set, displayed in diagnostics
    :param time_step: a resqpy Time Step object, there should be one date time for each property
    :param include: tuple of three arrays, one for each dimension k, j, i
                    containing the indices of the elements included in each dimension.
                    [k[n], j[n], i[n]] forms the index for cell[n]
    :param data_client: ObjectDataClient used to create the properties

    :return: CategoryTimeSeries or None if there was an error
    """
    arrays = []
    nan_values = set()
    lookup = None
    steps = time_step.values.length
    category_table_uuid = None
    # Iterate through the properties extracting their value arrays
    for p in properties:
        if not p.is_categorical:
            logger.error(
                f"Unexpected type for Property {p.citation_title} in Property Set {name}, the Time series will be ignored"
            )
            return None

        # build the look up table, if required
        # All properties in the set must share the same look up table
        if category_table_uuid is None:
            category_table_uuid = p.string_lookup_uuid
            lookup = _build_lookup_table(model, p, data_client)
        elif p.string_lookup_uuid != category_table_uuid:
            logger.error(f"Multiple lookup tables defined for Property {p.citation_title} in Property Set {name}")
            return None

        array_values = p.array_ref[include] if include else p.array_ref
        flattened_values = np.array(array_values).astype(np.int64).flatten(order="C")
        arrays.append(flattened_values)
        if p.null_value is not None:
            nan_values.add(p.null_value)

    if lookup is None:
        logger.error(f"No Category Lookup table in Property Set {name}, the Time series will be ignored")
        return None

    if steps != len(arrays):
        logger.error(
            f"Number of time steps {steps} does not equal number of properties {len(arrays)}, in Property Set {name} it will be ignored"
        )
        return None

    # Build an int array to contain the values
    schema = pa.schema([pa.field("t" + str(n), pa.int64()) for n in range(steps)])
    table = pa.Table.from_arrays(arrays, schema=schema)
    va = data_client.save_table(table)
    values = IntegerArrayMd.from_dict(va)

    series = CategoryTimeSeries(
        table=lookup,
        values=values,
        time_step=time_step,
        num_time_steps=steps,
        key=str(uuid4()),
        nan_description=NanCategorical(values=list(nan_values)),
    )
    return series


def _build_lookup_table(model: Model, p: ApsProperty, data_client: ObjectDataClient) -> LookupTable:
    """
    Build a LookupTable from a resqpy Categorical Property

    :param model: The resqpy model, representing the file being converted
    :param property: The resqpy property to build the LookupTable from
    :param data_client: ObjectDataClient used to create the LookupTable

    :Return: The lookup table
    """

    lookup_as_dict = StringLookup(model, p.string_lookup_uuid).as_dict()
    indices = list(lookup_as_dict.keys())
    names = lookup_as_dict.values()
    df = pd.DataFrame({"data": names, "index": indices})
    df.set_index("index", inplace=True)
    table_df, _ = create_category_lookup_and_data(df)

    schema = pa.schema([("key", pa.int64()), ("value", pa.string())])
    table = pa.Table.from_pandas(table_df, schema=schema)
    lookup_table_args = data_client.save_table(table)
    return LookupTable.from_dict(lookup_table_args)
