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

from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components import (
    BoolAttribute_V1_1_0 as BoolAttribute,
    CategoryAttribute_V1_1_0 as CategoryAttribute,
    ContinuousAttribute_V1_1_0 as ContinuousAttribute,
    DateTimeAttribute_V1_1_0 as DateTimeAttribute,
    IntegerAttribute_V1_1_0 as IntegerAttribute,
    NanCategorical_V1_0_1 as NanCategorical,
    NanContinuous_V1_0_1 as NanContinuous,
    OneOfAttribute_V1_2_0_Item as OneOfAttribute_Item,
    StringAttribute_V1_1_0 as StringAttribute,
)
from evo_schemas.elements import (
    BoolArray1_V1_0_1 as BoolArray1,
    DateTimeArray_V1_0_1 as DateTimeArray,
    FloatArray1_V1_0_1 as FloatArray1,
    IntegerArray1_V1_0_1 as IntegerArray1,
    LookupTable_V1_0_1 as LookupTable,
    StringArray_V1_0_1 as StringArray,
)

import evo.logging
import pandas as pd
import pyarrow as pa
import typing
from enum import Enum
from dataclasses import dataclass

logger = evo.logging.getLogger("data_converters")


class DataType(Enum):
    """This provides a way to map the inferred attribute type to the pyarrow data type to be stored."""

    CONTINUOUS = pa.float64()
    STRING = pa.string()
    INTEGER = pa.int64()
    DATETIME = pa.timestamp("us", tz="UTC")
    BOOL = pa.bool_()


class PyArrowTableFactory:
    @staticmethod
    def create_table(series: pd.Series, data_type: DataType) -> pa.Table:
        """Create a PyArrow table with the specified data type."""
        schema = pa.schema([("data", data_type.value)])
        return pa.Table.from_pandas(series.rename("data").to_frame(), schema=schema)


@dataclass
class AttributeConfig:
    """Values required to construct an attribute."""

    data_type: DataType
    array_class: type
    attribute_class: type
    nan_class: type | None = None


class AttributeFactory:
    """Provide mapping from pandas Series -> Evo Attribute."""

    CONTINUOUS_CONFIG: AttributeConfig = AttributeConfig(
        data_type=DataType.CONTINUOUS,
        array_class=FloatArray1,
        attribute_class=ContinuousAttribute,
        nan_class=NanContinuous,
    )

    STRING_CONFIG: AttributeConfig = AttributeConfig(
        data_type=DataType.STRING,
        array_class=StringArray,
        attribute_class=StringAttribute,
        nan_class=None,
    )

    INTEGER_CONFIG: AttributeConfig = AttributeConfig(
        data_type=DataType.INTEGER,
        array_class=IntegerArray1,
        attribute_class=IntegerAttribute,
        nan_class=NanCategorical,
    )

    DATETIME_CONFIG: AttributeConfig = AttributeConfig(
        data_type=DataType.DATETIME,
        array_class=DateTimeArray,
        attribute_class=DateTimeAttribute,
        nan_class=NanCategorical,
    )

    BOOL_CONFIG: AttributeConfig = AttributeConfig(
        data_type=DataType.BOOL,
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

    @staticmethod
    def create(name: str, series: pd.Series, client: ObjectDataClient) -> OneOfAttribute_Item | None:
        """Create an attribute from a pandas Series based on inferred type."""
        if series.empty:
            logger.debug(f"Got passed an empty series for attribute {name}, skipping Attribute creation.")
            return None

        inferred_type: str = pd.api.types.infer_dtype(series, skipna=True)

        if inferred_type == "categorical":
            return AttributeFactory.create_categorical_attribute(name, series, client)

        # Get attribute configuration for inferred type
        config: AttributeConfig | None = AttributeFactory.INFERRED_TYPE_MAP.get(inferred_type)
        if config is None:
            logger.warning(
                f"Encountered unsupported attribute type, inferred {inferred_type} with no matching AttributeConfig."
            )
            return None

        # PyArrow expects datetime columns to be of a specific dtype, not just inferred
        if config.data_type == DataType.DATETIME:
            series = pd.to_datetime(series)

        # Create and save the pyarrow table
        table: pa.Table = PyArrowTableFactory.create_table(series, config.data_type)
        table_info = client.save_table(table)

        # Create the evo array element from saved table information
        array_element = config.array_class.from_dict(table_info)

        # Keywords args to pass to attribute constructor
        attribute_kwargs: dict[str, typing.Any] = {
            "key": name,
            "name": name,
            "values": array_element,
        }

        # Add nan_description if the attribute supports it
        if config.nan_class is not None:
            nan_values_list = list(series.attrs.get("nan_values", []))
            attribute_kwargs["nan_description"] = config.nan_class(values=nan_values_list)

        # Create and return the evo attribute
        return config.attribute_class(**attribute_kwargs)

    @staticmethod
    def create_categorical_attribute(name: str, series: pd.Series, client: ObjectDataClient) -> CategoryAttribute:
        """Create a CategoryAttribute from a categorical pandas Series."""
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
