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
    ContinuousAttribute_V1_1_0 as ContinuousAttribute,
    NanContinuous_V1_0_1 as NanContinuous,
    OneOfAttribute_V1_2_0_Item as OneOfAttribute_Item,
    StringAttribute_V1_1_0 as StringAttribute,
)
from evo_schemas.elements import (
    FloatArray1_V1_0_1 as FloatArray1,
    StringArray_V1_0_1 as StringArray,
)

import pandas as pd
import pyarrow as pa
import typing


class PyArrowTableFactory:
    @staticmethod
    def create_continuous_table(series: pd.Series) -> pa.Table:
        schema = pa.schema([("data", pa.float64())])
        return pa.Table.from_pandas(series.rename("data").to_frame(), schema=schema)

    @staticmethod
    def create_string_table(series: pd.Series) -> pa.Table:
        schema = pa.schema([("data", pa.string())])
        return pa.Table.from_pandas(series.rename("data").to_frame(), schema=schema)


class AttributeFactory:
    @staticmethod
    def create(name: str, series: pd.Series, client: ObjectDataClient) -> OneOfAttribute_Item | None:
        nan_values_list: list[typing.Any] = list(series.attrs["nan_values"]) if "nan_values" in series.attrs else []
        inferred_type: str = pd.api.types.infer_dtype(series, skipna=True)

        if inferred_type in ["floating", "mixed-integer-float"]:
            table = PyArrowTableFactory.create_continuous_table(series)
            table_info = client.save_table(table)
            float_array = FloatArray1.from_dict(table_info)
            return ContinuousAttribute(
                key=name,
                name=name,
                nan_description=NanContinuous(values=nan_values_list),
                values=float_array,
            )

        elif inferred_type == "string":
            table = PyArrowTableFactory.create_string_table(series)
            table_info = client.save_table(table)
            string_array = StringArray.from_dict(table_info)
            return StringAttribute(
                key=name,
                name=name,
                values=string_array,
            )

        else:
            return None
