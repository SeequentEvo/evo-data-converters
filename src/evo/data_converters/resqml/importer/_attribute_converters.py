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

from typing import Optional

import numpy as np
import numpy.typing as npt
import pandas as pd
import pyarrow as pa
import resqpy.property as rqp
from evo_schemas.components import AttributeDescription_V1_0_1 as AttributeDescription
from evo_schemas.components import CategoryAttribute_V1_0_1 as CategoryAttribute
from evo_schemas.components import CategoryAttributeDescription_V1_0_1 as CategoryAttributeDescription
from evo_schemas.components import ContinuousAttribute_V1_0_1 as ContinuousAttribute
from evo_schemas.components import IntegerAttribute_V1_0_1 as IntegerAttribute
from evo_schemas.components import NanCategorical_V1_0_1 as NanCategorical
from evo_schemas.components import NanContinuous_V1_0_1 as NanContinuous
from evo_schemas.components import OneOfAttribute_V1_1_0 as OneOfAttribute
from evo_schemas.components import VectorAttribute_V1_0_0 as VectorAttribute
from evo_schemas.elements import FloatArray1_V1_0_1 as FloatArray1
from evo_schemas.elements import FloatArrayMd_V1_0_1 as FloatArrayMd
from evo_schemas.elements import IntegerArray1_V1_0_1 as IntegerArray1
from evo_schemas.elements import LookupTable_V1_0_1 as LookupTable
from resqpy.model import Model
from resqpy.property import Property

import evo.logging
from evo.data_converters.resqml.utils import property_is_discrete
from evo.objects.utils.data import ObjectDataClient

logger = evo.logging.getLogger("data_converters.resqml")


def create_category_lookup_and_data(column: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create a category lookup table and a data column with mapped values.

    Args:
        column (pd.Series): The column to create the lookup table and data column from.

    Returns:
        lookup_df (pd.DataFrame): The category lookup table.
        values_df (pd.DataFrame): The data column with mapped values.
    """
    set_obj = set(column["data"])
    list_obj = list(set_obj)
    list_obj.sort()
    num_unique_elements = len(list_obj)

    # Create lookup table
    lookup_df = pd.DataFrame(list())
    lookup_df["key"] = [i for i in range(1, num_unique_elements + 1)]
    lookup_df["value"] = list_obj

    # Create data column
    values_df = pd.DataFrame(list())
    values_df["data"] = column["data"].map(lookup_df.set_index("value")["key"])
    return lookup_df, values_df


def convert_categorical_property(
    m: Model, p: Property, data_client: ObjectDataClient, idx_valid: Optional[list[bool]] = None
) -> CategoryAttribute:
    """Converts a RESQML Categorical Property object to a CategoryAttribute object.
    Args:
        m (Model): The RESQML model object.
        p (Property): The RESQML Property object.
        data_client (ObjectDataClient): The ObjectDataClient object.
        idx_valid (np.ndarray): Optional. The indices of the valid values in the property array.
    """
    lookup_as_dict = rqp.StringLookup(m, p.string_lookup_uuid()).as_dict()

    # lookup table
    indices = list(lookup_as_dict.keys())
    names = lookup_as_dict.values()
    df = pd.DataFrame({"data": names, "index": indices})
    df.set_index("index", inplace=True)
    table_df, _ = create_category_lookup_and_data(df)

    schema = pa.schema([("key", pa.int64()), ("value", pa.string())])
    table = pa.Table.from_pandas(table_df, schema=schema)
    lookup_table_args = data_client.save_table(table)
    lookup_table_go = LookupTable.from_dict(lookup_table_args)

    # data
    array_values = p.array_ref(masked=True, exclude_null=True)[idx_valid] if idx_valid is not None else p.array_ref()
    flattened_values = np.array(array_values).astype(np.int64).flatten(order="C")
    values_df = pd.DataFrame(flattened_values, columns=["data"])
    schema = pa.schema([("data", pa.int64())])
    table = pa.Table.from_pandas(values_df, schema=schema)
    int_array_args = data_client.save_table(table)
    int_array_go = IntegerArray1.from_dict(int_array_args)

    if p.null_value() is not None:
        values = [p.null_value()]
        nan = NanCategorical(values=values)
    else:
        nan = None

    return CategoryAttribute(
        name=p.title,
        attribute_description=CategoryAttributeDescription(discipline="None", type=p.property_kind()),
        nan_description=nan,
        table=lookup_table_go,
        values=int_array_go,
    )


def convert_continuous_property(
    p: Property, data_client: ObjectDataClient, idx_valid: Optional[list[bool]] = None
) -> ContinuousAttribute:
    """Converts a RESQML Continuous Property object to a ContinuousAttribute object.
    Args:
        p (Property): The RESQML Property object.
        data_client (ObjectDataClient): The ObjectDataClient object.
        idx_valid (np.ndarray): Optional. The indices of the valid values in the property array.
    """
    array_values = p.array_ref(masked=True)[idx_valid] if idx_valid is not None else p.array_ref()
    flattened_values = np.array(array_values).astype(np.float64).flatten(order="C")
    values_df = pd.DataFrame(flattened_values, columns=["data"])
    schema = pa.schema([("data", pa.float64())])
    table = pa.Table.from_pandas(values_df, schema=schema)
    float_array_args = data_client.save_table(table)
    float_array_go = FloatArray1.from_dict(float_array_args)

    return ContinuousAttribute(
        name=p.title or "",
        attribute_description=AttributeDescription(discipline="None", type=p.property_kind()),
        nan_description=NanContinuous(values=[]),
        values=float_array_go,
    )


def convert_discrete_property(
    p: Property, data_client: ObjectDataClient, idx_valid: Optional[list[bool]] = None
) -> IntegerAttribute:
    """Converts a RESQML Discrete Property object to an IntegerAttribute object.
    Args:
       p (Property): The RESQML Property object.
       data_client (ObjectDataClient): The ObjectDataClient object.
       idx_valid (np.ndarray): Optional. The indices of the valid values in the property array.
    """
    array_values = p.array_ref(masked=True)[idx_valid] if idx_valid is not None else p.array_ref()
    flattened_values = np.array(array_values).astype(np.int64).flatten(order="C")
    values_df = pd.DataFrame(flattened_values, columns=["data"])
    schema = pa.schema([("data", pa.int64())])
    table = pa.Table.from_pandas(values_df, schema=schema)
    int_array_args = data_client.save_table(table)
    int_array_go = IntegerArray1.from_dict(int_array_args)
    if p.null_value() is not None:
        values = [p.null_value()]
        nan = NanCategorical(values=values)
    else:
        nan = None

    return IntegerAttribute(
        name=p.title,
        attribute_description=AttributeDescription(discipline="None", type=p.property_kind()),
        nan_description=nan,
        values=int_array_go,
    )


def convert_points_property(
    p: Property, data_client: ObjectDataClient, idx_valid: Optional[list[bool]] = None
) -> VectorAttribute:
    """Converts a RESQML Points Property object to a VectorAttribute object.
    Args:
        p (Property): The RESQML Property object.
        data_client (ObjectDataClient): The ObjectDataClient object.
        idx_valid (np.ndarray): Optional. The indices of the valid values in the property array.
    """
    go = None

    if p.is_points():
        array_values = p.array_ref(masked=True)[idx_valid] if idx_valid is not None else p.array_ref()
        go = _convert_points_to_vector_attribute(p.title, str(p.uuid), array_values, data_client)

    return go


def _convert_points_to_vector_attribute(
    name: str, key: str, array_values: npt.NDArray[np.float64], data_client: ObjectDataClient
) -> VectorAttribute:
    """
    Converts a list of x, y, z coordinates to a VectorAttribute object. The list of coordinates
    is reshaped to a 2D array with 3 columns (x, y, z). The name and key are used to create
    the VectorAttribute object.
    Args:
        name (str): The name of the VectorAttribute object.
        key (str): The unique key of the VectorAttribute object.
        array_values (list): The list of x, y, z coordinates.
        data_client (ObjectDataClient): The ObjectDataClient object.
    """
    xyz_array = array_values.reshape(-1, 3)
    df = pd.DataFrame(xyz_array, columns=["x", "y", "z"])
    schema = pa.schema([("x", pa.float64()), ("y", pa.float64()), ("z", pa.float64())])
    table = pa.Table.from_pandas(df, schema=schema)
    float_array_args = data_client.save_table(table)
    float_array_go = FloatArrayMd.from_dict(float_array_args)

    return VectorAttribute(
        name=name,
        key=key,
        attribute_description=AttributeDescription(discipline="None", type="ContinuousProperty"),
        nan_description=NanContinuous(values=[]),
        values=float_array_go,
    )


def convert_resqml_properties_to_evo_attributes(
    model: Model, properties: npt.NDArray[rqp.Property], data_client: ObjectDataClient
) -> OneOfAttribute:
    """
    :param model: The resqpy model, representing the file being converted
    :param properties: The list of resqpy Property objects to be converted
    :param data_client: ObjectDataClient used to create the properties
    :returns: list of Evo attributes
    """
    attributes = []

    if properties is not None:
        for property in properties:
            if isinstance(property, rqp.Property):
                if property.is_categorical():
                    go = convert_categorical_property(model, property, data_client)
                    attributes.append(go)
                elif property.is_continuous():
                    go = convert_continuous_property(property, data_client)
                    attributes.append(go)
                elif property_is_discrete(property):
                    go = convert_discrete_property(property, data_client)
                    attributes.append(go)
                elif property.is_points():
                    go = convert_points_property(property, data_client)
                    attributes.append(go)
                else:
                    # Unexpected property type, log a warning and continue
                    logger.warning(
                        "Ignoring property %s %s , As this is not a valid type"
                        % (property.citation_title, str(property.uuid))
                    )
    return attributes
