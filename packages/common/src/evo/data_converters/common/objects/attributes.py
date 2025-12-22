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

import typing
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import pyarrow as pa
from evo_schemas.components import (
    AttributeDescription_V1_0_1 as AttributeDescription,
)
from evo_schemas.components import (
    BoolAttribute_V1_1_0 as BoolAttribute,
)
from evo_schemas.components import (
    CategoryAttribute_V1_1_0 as CategoryAttribute,
)
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0 as ContinuousAttribute,
)
from evo_schemas.components import (
    DateTimeAttribute_V1_1_0 as DateTimeAttribute,
)
from evo_schemas.components import (
    IntegerAttribute_V1_1_0 as IntegerAttribute,
)
from evo_schemas.components import (
    NanCategorical_V1_0_1 as NanCategorical,
)
from evo_schemas.components import (
    NanContinuous_V1_0_1 as NanContinuous,
)
from evo_schemas.components import (
    OneOfAttribute_V1_2_0_Item as OneOfAttribute_Item,
)
from evo_schemas.components import (
    StringAttribute_V1_1_0 as StringAttribute,
)
from evo_schemas.elements import (
    BoolArray1_V1_0_1 as BoolArray1,
)
from evo_schemas.elements import (
    DateTimeArray_V1_0_1 as DateTimeArray,
)
from evo_schemas.elements import (
    FloatArray1_V1_0_1 as FloatArray1,
)
from evo_schemas.elements import (
    IntegerArray1_V1_0_1 as IntegerArray1,
)
from evo_schemas.elements import (
    LookupTable_V1_0_1 as LookupTable,
)
from evo_schemas.elements import (
    StringArray_V1_0_1 as StringArray,
)
from pint_pandas import PintType

import evo.logging
from evo.data_converters.common.objects.units import UnitMapper
from evo.objects.utils.data import ObjectDataClient

logger = evo.logging.getLogger("data_converters")


class AttributeType(Enum):
    """
    Enumeration mapping inferred attribute types to PyArrow data types.

    This provides a standardised way to map between pandas dtype inference
    and the corresponding PyArrow data types used for storage.
    """

    CONTINUOUS = 1
    STRING = 2
    INTEGER = 3
    DATETIME = 4
    BOOL = 5


@dataclass
class AttributeConfig:
    """
    Configuration for constructing an attribute from a pandas Series.

    :param data_type: The PyArrow data type to use for storage
    :param array_class: The Evo array class for wrapping the stored data
    :param attribute_class: The Evo attribute class to instantiate
    :param nan_class: Optional class for describing NaN values (None if not supported)
    """

    data_type: AttributeType
    array_class: FloatArray1 | StringArray | IntegerArray1 | DateTimeArray | BoolArray1
    attribute_class: OneOfAttribute_Item
    nan_class: NanContinuous | NanCategorical | None = None


CONTINUOUS_CONFIG: AttributeConfig = AttributeConfig(
    data_type=AttributeType.CONTINUOUS,
    array_class=FloatArray1,
    attribute_class=ContinuousAttribute,
    nan_class=NanContinuous,
)

STRING_CONFIG: AttributeConfig = AttributeConfig(
    data_type=AttributeType.STRING,
    array_class=StringArray,
    attribute_class=StringAttribute,
    nan_class=None,
)

INTEGER_CONFIG: AttributeConfig = AttributeConfig(
    data_type=AttributeType.INTEGER,
    array_class=IntegerArray1,
    attribute_class=IntegerAttribute,
    nan_class=NanCategorical,
)

DATETIME_CONFIG: AttributeConfig = AttributeConfig(
    data_type=AttributeType.DATETIME,
    array_class=DateTimeArray,
    attribute_class=DateTimeAttribute,
    nan_class=NanCategorical,
)

BOOL_CONFIG: AttributeConfig = AttributeConfig(
    data_type=AttributeType.BOOL,
    array_class=BoolArray1,
    attribute_class=BoolAttribute,
    nan_class=None,
)

# Mapping from inferred pandas dtype to attribute configuration
INFERRED_TYPE_MAP: dict[str, AttributeConfig] = {
    # Continuous/Float types
    "floating": CONTINUOUS_CONFIG,
    "mixed-integer-float": CONTINUOUS_CONFIG,
    "decimal": CONTINUOUS_CONFIG,
    # String types
    "string": STRING_CONFIG,
    "unicode": STRING_CONFIG,
    "bytes": STRING_CONFIG,
    # Integer types
    "integer": INTEGER_CONFIG,
    # DateTime types
    "datetime64": DATETIME_CONFIG,
    "datetime": DATETIME_CONFIG,
    "date": DATETIME_CONFIG,
    # Boolean types
    "boolean": BOOL_CONFIG,
}


def create_attribute(name: str, series: pd.Series, client: ObjectDataClient) -> OneOfAttribute_Item | None:
    """
    Create an Evo attribute from a pandas Series based on inferred type.

    Automatically infers the data type from the Series and creates the appropriate
    Evo attribute object. Handles categorical types specially, and supports NaN
    value descriptions where applicable.

    :param name: The name/key for the attribute
    :param series: Pandas Series containing the attribute data
    :param client: Object data client for saving PyArrow tables

    :return: The created attribute object, or None if the series is empty or type is unsupported
    """
    if series.empty:
        logger.debug(f"Got passed an empty series for attribute {name}, skipping Attribute creation.")
        return None

    attribute_description = None
    nan_values_list = list(series.attrs.get("nan_values", []))

    # If series has a Pint Data Type, then we will need to create an AttributeDescription
    # to pass the type info to EVO.
    # If there is not Evo Unit corresponding to the Pint Type, the attribute will be passed
    # to EVO without an attribute_description
    if isinstance(series.dtype, PintType):
        unit = UnitMapper.lookup(series.dtype)
        if unit is not None:
            attribute_description = AttributeDescription(discipline="None", type=unit)
        else:
            logger.warning(f"Unable to map {series.dtype} to an EVO unit")

        series = pd.Series(series.pint.magnitude, index=series.index, name=series.name)
        # Note that Pint magnitudes are floats, so need to Map the nan_values to float
        # otherwise the ContinuousAttribute constructor will fail, as it requires the nan_values be a float.
        nan_values_list = [float(i) for i in nan_values_list]

    inferred_type: str = pd.api.types.infer_dtype(series, skipna=True)

    if inferred_type == "categorical":
        return create_categorical_attribute(name, series, client)

    # Get attribute configuration for inferred type
    config: AttributeConfig | None = INFERRED_TYPE_MAP.get(inferred_type)
    if config is None:
        logger.warning(
            f"Encountered unsupported attribute type, inferred {inferred_type} with no matching AttributeConfig."
        )
        return None

    # PyArrow expects datetime columns to be of a specific dtype, not just inferred
    if config.data_type == AttributeType.DATETIME:
        series = pd.to_datetime(series)

    # Create and save the pyarrow table
    table: pa.Table = create_table(series, config.data_type)
    table_info = client.save_table(table)

    # Create the evo array element from saved table information
    array_element = config.array_class.from_dict(table_info)

    # Keywords args to pass to attribute constructor
    attribute_kwargs: dict[str, typing.Any] = {
        "key": name,
        "name": name,
        "values": array_element,
        "attribute_description": attribute_description,
    }

    # Add nan_description if the attribute supports it
    if config.nan_class is not None:
        nan_values = (
            [int(v) for v in nan_values_list]
            if config.data_type in {AttributeType.INTEGER, AttributeType.DATETIME}
            else nan_values_list
        )
        attribute_kwargs["nan_description"] = config.nan_class(values=nan_values)

    # Create and return the evo attribute
    return config.attribute_class(**attribute_kwargs)


def create_categorical_attribute(name: str, series: pd.Series, client: ObjectDataClient) -> CategoryAttribute:
    """
    Create a CategoryAttribute from a categorical pandas Series.

    Converts pandas categorical data into an Evo CategoryAttribute with a lookup
    table mapping integer codes to string category values. Handles NaN values
    using pandas' -1 code convention.

    :param name: The name/key for the attribute
    :param series: Pandas Series with categorical dtype
    :param client: Object data client for saving PyArrow tables

    :return: The created CategoryAttribute object
    """
    categories = series.cat.categories.astype(str)
    keys = list(range(len(categories)))

    lookup_table = pa.Table.from_arrays(
        arrays=[pa.array(keys, type=pa.int32()), pa.array(categories, type=pa.string())],
        schema=pa.schema(
            [
                pa.field("key", pa.int32()),
                pa.field("value", pa.string()),
            ]
        ),
    )

    lookup_table_args = client.save_table(lookup_table)
    lookup_table_go = LookupTable.from_dict(lookup_table_args)

    integer_array_table = pa.Table.from_arrays(
        arrays=[pa.array(series.cat.codes, type=pa.int32())], schema=pa.schema([pa.field("data", pa.int32())])
    )

    integer_array_args = client.save_table(integer_array_table)
    integer_array_go = IntegerArray1.from_dict(integer_array_args)

    # Pandas uses -1 for NaN in categorical codes
    nan_codes = [-1]

    return CategoryAttribute(
        name=name,
        key=name,
        table=lookup_table_go,
        values=integer_array_go,
        nan_description=NanCategorical(values=nan_codes),
    )


def create_table(series: pd.Series, attribute_type: AttributeType) -> pa.Table:
    """
    Create a PyArrow table from a pandas Series with the specified data type.

    :param series: Pandas Series containing the data to convert
    :param data_type: DataType enum specifying the PyArrow type to use

    :return: PyArrow table with a single 'data' column of the specified type
    """
    data_type = get_data_type(attribute_type)

    try:
        # Trial conversion: fails if values can't be represented in data_type
        pa.array(series.to_numpy(), type=data_type, from_pandas=True)
    except (pa.ArrowInvalid, pa.ArrowTypeError, OverflowError, ValueError) as e:
        raise TypeError(f"Series cannot be converted to Arrow type {data_type} for Series dtype={series.dtype}") from e

    schema = pa.schema([("data", data_type)])
    return pa.Table.from_pandas(series.rename("data").to_frame(), schema=schema)


def get_data_type(type: AttributeType) -> pa.DataType:
    return _type_map[type]


_type_map: dict[int, pa.DataType] = {
    AttributeType.CONTINUOUS: pa.float64(),
    AttributeType.STRING: pa.string(),
    AttributeType.INTEGER: pa.int64(),
    AttributeType.DATETIME: pa.timestamp("us", tz="UTC"),
    AttributeType.BOOL: pa.bool_(),
}
