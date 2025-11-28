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

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import auto, Enum
from typing import Any

from dateutil.parser import ParserError, isoparse
import numpy
import numpy as np
from numpy.typing import NDArray
import pyarrow as pa
import evo.logging
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.elements import (
    BoolArray1_V1_0_1,
    DateTimeArray_V1_0_1,
    FloatArray1_V1_0_1,
    IndexArray2_V1_0_1,
    IntegerArray1_V1_0_1,
    LookupTable_V1_0_1,
    StringArray_V1_0_1,
)
from evo_schemas.components import (
    BoolAttribute_V1_1_0,
    CategoryAttribute_V1_1_0,
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_1_0,
    IntegerAttribute_V1_1_0,
    NanCategorical_V1_0_1,
    NanContinuous_V1_0_1,
    OneOfAttribute_V1_2_0_Item,
    StringAttribute_V1_1_0,
)

from evo.data_converters.common.utils import vertices_bounding_box
from evo.data_converters.duf.common import deswik_types as dw
from evo.data_converters.duf.common.consts import EvoSchema
from evo.data_converters.duf.xprops import get_xprops_value

logger = evo.logging.getLogger("data_converters")


class AttributeType(Enum):
    String = auto()
    Category = auto()
    Integer = auto()
    Double = auto()
    DateTime = auto()
    # Color = auto()  # TODO: unsure of the format DUF uses for these
    Boolean = auto()


@dataclass(frozen=True)
class AttributeSpec:
    name: str
    evo_name: str
    attr_type: AttributeType
    options: tuple[str] | None = None
    required: bool = False
    description: str | None = None

    @staticmethod
    def __attr_prop_name(attr_index: int, name: str):
        return f"_dw_Attribute[{attr_index}].{name}"

    @classmethod
    def layer_attribute_by_index(
        cls, layer: dw.Layer, attr_index: int, evo_schema: EvoSchema
    ) -> "AttributeSpec | None":
        assert 0 < attr_index + 1 <= value_from_xproperties(layer, "_dw_AttributeCount", AttributeType.Integer), (
            f"Attribute index {attr_index} exceeds the number of attributes in layer {layer.Name}."
        )

        options = None
        attr_type = value_from_xproperties(layer, cls.__attr_prop_name(attr_index, "Type"), AttributeType.String)
        if (
            attr_type == "String"
            and value_from_xproperties(layer, cls.__attr_prop_name(attr_index, "LimitToList"), AttributeType.Boolean)
            and (
                options := value_from_xproperties(
                    layer, cls.__attr_prop_name(attr_index, "ValuesList"), AttributeType.String
                )
            )
        ):
            attr_type = AttributeType.Category
            options = tuple(options.split("|"))
        elif attr_type is not None:
            attr_type = getattr(AttributeType, attr_type, None)

        if attr_type is None:
            logger.warning(f"Unsupported attribute type {attr_type} for layer {layer.Name}, returning None.")
            return None

        name = value_from_xproperties(layer, cls.__attr_prop_name(attr_index, "Name"), AttributeType.String)
        if evo_schema in (EvoSchema.triangle_mesh, EvoSchema.line_segments):
            if name.lower() == "id":
                # Leapfrog does not handle columns named "ID", so rename them on the fly. We'll just hope
                # that there isn't another column named "external_id".
                evo_name = "external_id"
                logger.warning(f"Column {name} is being converted to {evo_name}")
            else:
                evo_name = name
        else:
            raise NotImplementedError()
        return cls(
            name=name,
            evo_name=evo_name,
            attr_type=attr_type,
            options=options,
            required=value_from_xproperties(layer, cls.__attr_prop_name(attr_index, "Required"), AttributeType.Boolean),
            description=value_from_xproperties(
                layer, cls.__attr_prop_name(attr_index, "Description"), AttributeType.String
            ),
        )

    @classmethod
    def layer_attributes(cls, layer: dw.Layer, evo_schema: EvoSchema) -> list["AttributeSpec"]:
        attr_count = value_from_xproperties(layer, "_dw_AttributeCount", AttributeType.Integer)
        if not attr_count:
            return []

        return [
            attr for i in range(attr_count) if (attr := cls.layer_attribute_by_index(layer, i, evo_schema)) is not None
        ]

    def _double_to_go(self, data_client: ObjectDataClient, values: list[numpy.floating | None]):
        table = pa.table(
            [values],
            schema=pa.schema(
                [
                    pa.field("n0", pa.float64()),
                ]
            ),
        )
        table = data_client.save_table(table)
        return ContinuousAttribute_V1_1_0(
            name=self.evo_name,
            key=self.name,
            values=FloatArray1_V1_0_1(**table),
            nan_description=NanContinuous_V1_0_1(values=[]),
        )

    def to_go(self, data_client: ObjectDataClient, values: list[Any]) -> OneOfAttribute_V1_2_0_Item:
        category_set = None
        if self.attr_type is AttributeType.String:
            category_set = set(v for v in values if v)

        match self.attr_type:
            case AttributeType.String if len(category_set) > 3_000:
                table = pa.table(
                    [values],
                    schema=pa.schema(
                        [
                            pa.field("n0", pa.string()),
                        ]
                    ),
                )
                table = data_client.save_table(table)
                return StringAttribute_V1_1_0(
                    name=self.evo_name,
                    key=self.name,
                    values=StringArray_V1_0_1(**table),
                )
            case AttributeType.String | AttributeType.Category:
                options = category_set if self.options is None else self.options

                # Leapfrog does not handle cases where "" is a category if there are also NaN values in
                # the column. Work around by dropping "" as a category. The result is that "" values will be published
                # as NaN.
                options = [opt for opt in options if opt != ""]
                reverse_lookup = defaultdict(int)  # Default to zero
                reverse_lookup.update({value: idx for idx, value in enumerate(options, start=1)})

                lookup_keys_type = pa.int32() if numpy.can_cast(len(options), "int32", "safe") else pa.int64()
                lookup_table = pa.table(
                    [list(reverse_lookup.values()), list(reverse_lookup.keys())],
                    schema=pa.schema(
                        [
                            pa.field("key", lookup_keys_type),
                            pa.field("value", pa.string()),
                        ]
                    ),
                )
                lookup_table = data_client.save_table(lookup_table)

                values_table = pa.table(
                    [[reverse_lookup[value] for value in values]],
                    schema=pa.schema(
                        [
                            pa.field("n0", lookup_keys_type),
                        ]
                    ),
                )
                values_table = data_client.save_table(values_table)

                return CategoryAttribute_V1_1_0(
                    name=self.evo_name,
                    key=self.name,
                    table=LookupTable_V1_0_1(**lookup_table),
                    nan_description=NanCategorical_V1_0_1(values=[0]),
                    values=IntegerArray1_V1_0_1(**values_table),
                )
            case AttributeType.Integer:
                if any(v is None for v in values):
                    # Leapfrog does not handle cases where integer columns have NaN values. So, convert it to double.
                    doubles = [v if v is None else float(v) for v in values]
                    logger.warning(f"Integer column {self.name} has NaNs. Converting to double.")
                    return self._double_to_go(data_client, doubles)
                nan_values = [max((v for v in values if v is not None), default=-1) + 1]
                data_type = pa.int32() if numpy.can_cast(nan_values[0], "int32", "safe") else pa.int64()
                table = pa.table(
                    [values],
                    schema=pa.schema(
                        [
                            pa.field("n0", data_type),
                        ]
                    ),
                )
                column = table.column(0)
                if column.null_count:
                    table = table.set_column(0, "n0", column.fill_null(nan_values[0]))
                else:
                    nan_values = []
                table = data_client.save_table(table)
                return IntegerAttribute_V1_1_0(
                    name=self.evo_name,
                    key=self.name,
                    values=IntegerArray1_V1_0_1(**table),
                    nan_description=NanCategorical_V1_0_1(values=nan_values),
                )
            case AttributeType.Double:
                return self._double_to_go(data_client, values)
            case AttributeType.DateTime:
                # The conversion is a little painful here as pyarrow can't always find tzdata to handle the timezones
                min_value = float("inf")
                max_value = float("-inf")
                any_null = False
                timestamps = []
                for value in values:
                    if isinstance(value, datetime):
                        timestamp = int(value.timestamp() * 1_000_000)  # Convert to microseconds
                    else:
                        try:
                            timestamp = int(isoparse(value).replace(tzinfo=timezone.utc).timestamp() * 1_000_000)
                        except (ParserError, ValueError, TypeError):
                            timestamp = None
                            any_null = True
                    timestamps.append(timestamp)
                    if timestamp is not None:
                        if timestamp < min_value:
                            min_value = timestamp
                        if timestamp > max_value:
                            max_value = timestamp

                # Choose a null value if required
                nan_values = []
                if any_null:
                    if min_value > 0:
                        nan_values = [0]
                    elif max_value < np.iinfo("int64").max:
                        nan_values = [np.iinfo("int64").max]
                    else:
                        # Do it the very slow way
                        for i in range(1, np.iinfo("int64").max):
                            if i not in timestamps:
                                nan_values = [i]
                                break

                table = pa.table(
                    [timestamps],
                    schema=pa.schema(
                        [
                            pa.field("n0", pa.timestamp("us", tz="UTC")),
                        ]
                    ),
                )
                if any_null:
                    table = table.set_column(0, "n0", table.column(0).fill_null(nan_values[0]))

                table = data_client.save_table(table)
                return DateTimeAttribute_V1_1_0(
                    name=self.evo_name,
                    key=self.name,
                    values=DateTimeArray_V1_0_1(**table),
                    nan_description=NanCategorical_V1_0_1(values=nan_values),
                )
            case AttributeType.Boolean:
                table = pa.table(
                    [values],
                    schema=pa.schema(
                        [
                            pa.field("n0", pa.bool_()),
                        ]
                    ),
                )
                table = data_client.save_table(table)
                return BoolAttribute_V1_1_0(
                    name=self.evo_name,
                    key=self.name,
                    values=BoolArray1_V1_0_1(**table),
                )
            case _:
                logger.warning(
                    f"Skipping unsupported DUF attribute data type '{self.attr_type.name}' for attribute '{self.name}'."
                )
                return None


def _try_cast(cast_func, value) -> Any | None:
    if value in (None, ""):
        return None
    try:
        return cast_func(value)
    except ValueError:
        # It is possible for a Deswik entity to have an attribute that doesn't match its layer's type spec.
        logger.debug(f"Not able to use `{cast_func}` to cast `{value}`")
        return None


def value_from_xproperties(obj: dw.BaseEntity, key: str, attr_type: AttributeType) -> Any:
    if obj.XProperties is None:
        return None
    value = get_xprops_value(obj.XProperties, key)
    if not value:
        return None
    match attr_type:
        case AttributeType.String | AttributeType.Category:
            return str(value) if value is not None else None
        case AttributeType.Integer:
            return _try_cast(int, value)
        case AttributeType.Double:
            return _try_cast(float, value)
        case AttributeType.DateTime | AttributeType.Boolean:
            return value if value not in {None, ""} else None
        case _:
            logger.warning(f"Unsupported attribute type {attr_type} for key {key}, returning None.")
            return None


def validify(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)[-255:]  # limit to 255 chars, keep the end


def get_name(obj: dw.BaseEntity) -> str:
    if isinstance(obj, dw.Layer):
        return obj.Name.split("\\")[-1]

    if (label := getattr(obj, "Label", None)) is not None:
        return validify(label)

    obj_name = f"{type(obj).__name__}-{obj.Guid}"
    if (layer := getattr(obj, "Layer", None)) is not None:
        layer_name = get_name(layer)
        return validify(f"{layer_name}-{obj_name}".strip("-_"))

    return validify(obj_name)


def vertices_array_to_go_and_bbox(data_client, vertices_array, table_klass):
    bounding_box_go = vertices_bounding_box(vertices_array)
    vertices_schema = pa.schema(
        [
            pa.field("x", pa.float64()),
            pa.field("y", pa.float64()),
            pa.field("z", pa.float64()),
        ]
    )
    vertices_table = pa.Table.from_arrays(
        [pa.array(vertices_array[:, i], type=pa.float64()) for i in range(len(vertices_schema))],
        schema=vertices_schema,
    )
    return table_klass(**data_client.save_table(vertices_table)), bounding_box_go


def indices_array_to_go(data_client, indices_array, table_klass):
    width = indices_array.shape[1]
    indices_schema = pa.schema([pa.field(f"n{i}", pa.uint64()) for i in range(width)])
    indices_table = pa.Table.from_arrays(
        [pa.array(indices_array[:, i], type=pa.uint64()) for i in range(width)],
        schema=indices_schema,
    )
    return table_klass(**data_client.save_table(indices_table))


def parts_to_go(
    data_client, parts: dict[str, int | dict[AttributeSpec, list]], parts_klass, chunks_klass=IndexArray2_V1_0_1
):
    if parts:
        parts_schema = pa.schema([pa.field("offset", pa.uint64()), pa.field("count", pa.uint64())])
        parts_table = pa.Table.from_arrays(
            [pa.array(parts["offset"], type=pa.uint64()), pa.array(parts["count"], type=pa.uint64())],
            schema=parts_schema,
        )
        chunks_go = chunks_klass(**data_client.save_table(parts_table))

        if attributes := parts["attributes"]:
            part_attributes_go = [spec.to_go(data_client, values) for spec, values in attributes.items()]
        else:
            part_attributes_go = None

        return parts_klass(
            chunks=chunks_go,
            attributes=part_attributes_go,
        )
    return None


def obj_list_and_indices_to_arrays(obj_list: list[dw.BaseEntity], indices_arrays: list[NDArray], evo_schema: EvoSchema):
    # Avoid mutating the input later on in the function
    indices_arrays = [arr.copy() for arr in indices_arrays]

    orig_num_vertices = sum(obj.VertexList.Count for obj in obj_list)
    num_parts = len(obj_list)

    layers = {obj.Layer for obj in obj_list}
    assert len(layers) == 1, "Objects must be from the same layer to combine"
    layer = layers.pop()

    axes = ("X", "Y", "Z")
    vertices_array = np.fromiter(
        (getattr(vert, axis) for polyface in obj_list for vert in polyface.VertexList for axis in axes),
        dtype=np.float64,
        count=orig_num_vertices * 3,
    ).reshape(orig_num_vertices, 3)

    unique_vertices_array, orig_to_unique = np.unique(vertices_array, return_inverse=True, axis=0)  # Ensure unique
    if len(unique_vertices_array) == orig_num_vertices:
        # No duplicates
        orig_to_unique = None
        unique_vertices_array = vertices_array  # np.unique sorts the returned array, we need to use the original here

    attribute_specs = AttributeSpec.layer_attributes(layer, evo_schema)
    if num_parts > 1 or attribute_specs:
        logger.info(f"Processing {num_parts} attributes for {len(obj_list)} entities")

        # We use parts to store object-level attributes, so we need at least a single part if we have any
        parts = {"offset": [], "count": [], "attributes": defaultdict(list)}
        attributes = parts["attributes"]

        offset = 0
        vertex_offset = 0
        for i, (obj, obj_indices_array) in enumerate(zip(obj_list, indices_arrays)):
            obj_num_vertices = obj.VertexList.Count
            obj_count = len(obj_indices_array)

            obj_indices_array += vertex_offset  # Shift indices to the combined vertices array

            parts["offset"].append(offset)
            parts["count"].append(obj_count)

            offset += obj_count
            vertex_offset += obj_num_vertices

            # Convert XProperties to attributes
            for spec in attribute_specs:
                attr = value_from_xproperties(obj, spec.name, spec.attr_type)
                if spec.required and attr is None:
                    # Hopefully not going to happen
                    logger.warning(f"Required attribute '{spec.name}' is missing in object {get_name(obj)}.")

                attributes[spec].append(attr)

            if i % 1000 == 0:
                logger.info(f"Processed attributes for entity {i}")
    else:
        parts = None

    flattened_indices_array = np.concatenate(indices_arrays, axis=0)

    if orig_to_unique is not None:
        # Some duplicates were removed, remap to unique array
        flattened_indices_array = orig_to_unique[flattened_indices_array]

    logger.debug(f"Num parts: {num_parts}")
    logger.debug(f"Indices: {flattened_indices_array.shape}")
    logger.debug(f"Vertices: {unique_vertices_array.shape}")
    logger.debug(f"Num {type(obj_list[0]).__name__} attributes: {len(attribute_specs)}")

    return unique_vertices_array, flattened_indices_array, parts
