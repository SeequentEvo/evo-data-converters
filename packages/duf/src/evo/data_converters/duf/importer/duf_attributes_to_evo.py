from datetime import datetime
from typing import Any, Optional

import pyarrow as pa
from dateutil.parser import isoparse
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_1_0,
    IntegerAttribute_V1_1_0,
    NanCategorical_V1_0_1,
    NanContinuous_V1_0_1,
    OneOfAttribute_V1_2_0,
    OneOfAttribute_V1_2_0_Item,
    StringAttribute_V1_1_0,
)
from evo_schemas.elements import (
    DateTimeArray_V1_0_1,
    FloatArray1_V1_0_1,
    IntegerArray1_V1_0_1,
    StringArray_V1_0_1,
)

import evo.logging
from evo.objects.utils.data import ObjectDataClient

logger = evo.logging.getLogger("data_converters")


def convert_duf_attributes(
    attributes: list[tuple[str, Any]],
    data_client: ObjectDataClient,
) -> OneOfAttribute_V1_2_0:
    attributes_go = []

    for attribute in attributes:
        attribute_go = convert_duf_single_value_attribute(attribute, data_client)
        if attribute_go:
            attributes_go.append(attribute_go)

    return attributes_go


def convert_duf_single_value_attribute(
    attribute: tuple[str, Any], data_client: ObjectDataClient
) -> Optional[OneOfAttribute_V1_2_0_Item]:
    key, value = attribute

    if isinstance(value, str):
        try:
            value = isoparse(value)
        except ValueError:
            pass

    match value:
        case str():
            table = pa.table(
                [[value]],
                schema=pa.schema(
                    [
                        pa.field("n0", pa.string()),
                    ]
                ),
            )
            table = data_client.save_table(table)
            return StringAttribute_V1_1_0(
                name=key,
                key=key,
                values=StringArray_V1_0_1(
                    data=table["data"],
                    length=1,
                ),
            )
        case int():
            table = pa.table(
                [[value]],
                schema=pa.schema(
                    [
                        pa.field("n0", pa.int64()),
                    ]
                ),
            )
            table = data_client.save_table(table)
            return IntegerAttribute_V1_1_0(
                name=key,
                key=key,
                values=IntegerArray1_V1_0_1(
                    data=table["data"],
                    length=1,
                    data_type=table["data_type"],
                ),
                nan_description=NanCategorical_V1_0_1(values=[]),
            )
        case float():
            table = pa.table(
                [[value]],
                schema=pa.schema(
                    [
                        pa.field("n0", pa.float64()),
                    ]
                ),
            )
            table = data_client.save_table(table)
            return ContinuousAttribute_V1_1_0(
                name=key,
                key=key,
                values=FloatArray1_V1_0_1(
                    data=table["data"],
                    length=1,
                    data_type=table["data_type"],
                ),
                nan_description=NanContinuous_V1_0_1(values=[]),
            )
        case datetime():
            table = pa.table(
                [[value]],
                schema=pa.schema(
                    [
                        pa.field("n0", pa.timestamp("us", tz="UTC")),
                    ]
                ),
            )
            table = data_client.save_table(table)
            return DateTimeAttribute_V1_1_0(
                name=key,
                key=key,
                values=DateTimeArray_V1_0_1(
                    data=table["data"],
                    length=1,
                    data_type=table["data_type"],
                ),
                nan_description=NanCategorical_V1_0_1(values=[]),
            )
        case _:
            logger.warning(f"Skipping unsupported DUF attribute data type '{value.__class__.__name__}'")
            return None
