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

from evo.data_converters.duf.common import deswik_types as dw

# TODO The code for dealing with DUF XProperties is mostly unused. It was written before we had done much of this work
#  in C#.

possible_boxed_types: list[str] = [
    "Vector2_dp",
    "Vector3_dp",
    "Vector4_dp",
    "Color",
    "Boolean",
    "Byte",
    "SByte",
    "Char",
    "Double",
    "Single",
    "Int32",
    "UInt32",
    "Int64",
    "UInt64",
    "BaseObject",
    "Int16",
    "UInt16",
    "String",
    "Ticks",
    "DateTimeKind",
    "ArrayVector2_dp,ArrayVector3_dp,ArrayVector4_dp,ArrayColor",
    "ArrayBoolean",
    "ArrayByte",
    "ArraySByte",
    "ArrayChar",
    "ArrayDouble",
    "ArraySingle",
    "ArrayInt32",
    "ArrayUInt32",
    "ArrayInt64",
    "ArrayUInt64",
    "ArrayInt16",
    "ArrayUInt16",
    "ArrayString",
    "ArrayTicks",
    "ArrayDateTimeKind",
    "DufListVector2_dp",
    "DufListVector3_dp",
    "DufListVector4_dp",
    "DufListColor",
    "DufListBoolean",
    "DufListByte",
    "DufListSByte",
    "DufListChar",
    "DufListDouble",
    "DufListSingle",
    "DufListInt32",
    "DufListUInt32",
    "DufListInt64",
    "DufListUInt64",
    "DufListInt16",
    "DufListUInt16",
    "DufListString",
    "DufListTicks",
    "DufListDateTimeKind",
]


def _infer_boxed_type(prop: dw.PropValue) -> str | None:
    for pbt in possible_boxed_types:
        if getattr(prop, "Value" + pbt) is not None:
            return pbt
    return None


def get_xprops_value(xproperties: dw.XProperties, key: str):
    found, value = xproperties.TryGetValue(key)
    if not found:
        return None

    value = value.Value[0].Value
    return value


def _cast_to_csharp(value, csharp_type: str):
    match csharp_type:
        case "String":
            return dw.String(value)
        case "Boolean":
            return dw.Boolean(value)
        case "Int32":
            return dw.Int32(value)
        case "UInt32":
            return dw.UInt32(value)
        case "Double":
            return dw.Double(value)

    raise NotImplementedError(f"Unsupported type: {csharp_type}")


def _set_xprops_csharp_value(xproperties: dw.XProperties, key: str, values):
    props_list = dw.List[dw.PropValue]()
    for v in values:
        prop_value = dw.PropValue(v)
        props_list.Add(prop_value)

    xprop = dw.XProperty()
    xprop.Value = props_list
    xproperties.Remove(key)
    xproperties.Add(key, xprop)


def _set_xprops_value(xproperties: dw.XProperties, key: str, values, types: list[str]):
    assert len(values) == len(types)
    csharp_values = [_cast_to_csharp(v, t) for v, t in zip(values, types)]
    _set_xprops_csharp_value(xproperties, key, csharp_values), csharp_values[-1]


def _load_xpropertries(xproperties: dw.XProperties):
    return {key: get_xprops_value(key) for key in xproperties.Keys}


class XBindings:
    def _guard_possible_types(self, types: list[str]):
        possible_types = set(possible_boxed_types)
        return all(t in possible_types for t in types)

    def __init__(self, key: str, types: str | list[str], default=None, default_missing=None):
        self.types = [types] if isinstance(types, str) else types
        assert self._guard_possible_types(self.types)
        self.key = key
        self.defaults = default if (default is None or isinstance(default, list)) else [default]
        self.default_missing = default_missing

    def __get__(self, instance: "XPropertiesWrapper", owner):
        result = instance.get_xvalue(instance.key_with_prefix(self.key))
        if result is None:
            return self.default_missing
        return result

    def __set__(self, instance: "XPropertiesWrapper", values):
        values = values if isinstance(values, list) else [values]
        instance.set_xvalue(instance.key_with_prefix(self.key), values, self.types)

    def apply_default(self, instance):
        if self.defaults is None:
            return
        self.__set__(instance, self.defaults)


class XPropertiesWrapper:
    def __init__(self, xproperties: dw.XProperties):
        self._xproperties = xproperties

    def get_xvalue(self, key):
        return get_xprops_value(self._xproperties, key)

    def set_xvalue(self, key, values, types):
        _set_xprops_value(self._xproperties, key, values, types)

    def key_with_prefix(self, key: str) -> str:
        return key

    def apply_defaults(self):
        for item in self.__class__.__dict__.values():
            if isinstance(item, XBindings):
                item.apply_default(self)


class AttributesSpecXProperties(XPropertiesWrapper):
    def __init__(self, idx: int, xproperties: dw.XProperties):
        super().__init__(xproperties)
        self._idx = idx

    def key_with_prefix(self, key: str) -> str:
        return f"_dw_Attribute[{self._idx}].{key}"

    # TODO Review default. I have no idea whether they are sensible. They were pulled from an example duf file with
    #   attributes that I happened to get my hands on.
    Name = XBindings("Name", "String", default="")
    Type = XBindings("Type", "String", default="")
    DefaultValue = XBindings("DefaultValue", "String", default="")
    DisplayInProperties = XBindings("DisplayInProperties", "Boolean", default=True)
    Group = XBindings("Group", "String", default="")
    Prompt = XBindings(
        "Prompt",
        "Boolean",
        default=False,
    )
    Description = XBindings("Description", "String", default="")
    ValuesList = XBindings("ValuesList", "String", default="")  # TODO check type
    LimitToList = XBindings("LimitToList", "Boolean", default=False)
    LookupList = XBindings("LookupList", "String", default="")
    Format = XBindings("Format", "String", default="")
    Required = XBindings("Required", "Boolean", default=False)
    Locked = XBindings("Locked", "Boolean", default=False)
    WeightField = XBindings("WeightField", "String", default="")
    DisplayMode = XBindings("DisplayMode", "Int32", default=0)


class LayerXProperties(XPropertiesWrapper):
    DocumentDateTimeAttributesFixed = XBindings("_dw_DocumentDateTimeAttributesFixed", "Boolean")
    AttributeCount = XBindings("_dw_AttributeCount", "Int32", default_missing=0)
    VertexAttributeCount = XBindings("_dw_VertexAttributeCount", "Int32")
    LastModifiedBy = XBindings("_dw_LastModifiedBy", "String")
    LastModifiedDate = XBindings("_dw_LastModifiedDate", "String")
    X_ENTITIES_COUNT = XBindings("X_ENTITIES_COUNT", "Int32")

    def new_attribute(self) -> AttributesSpecXProperties:
        old_count = self.AttributeCount or 0
        self.AttributeCount = old_count + 1
        return self.attribute_specs[-1]

    @property
    def attribute_specs(self) -> list[AttributesSpecXProperties]:
        return [AttributesSpecXProperties(i, self._xproperties) for i in range(self.AttributeCount)]


class ObjAttributesXProperties(XPropertiesWrapper):
    def __init__(self, xproperties: dw.XProperties, layer: LayerXProperties):
        super().__init__(xproperties)
        self._layer = layer

    def __getitem__(self, item: str):
        return self.get_xvalue(item)

    def __setitem__(self, item: str, value: dw.String | dw.Double):
        # TODO The types should be able to be inferred from the xrops attribute specs. But for some reason it appears
        #  that the int attributes are written as doubles, so inference can't be relied on. (???)
        _set_xprops_csharp_value(self._xproperties, item, [value])

    def keys(self) -> list[str]:
        return [attr_spec.Name for attr_spec in self._layer.attribute_specs]

    def __repr__(self):
        return str({k: self[k] for k in self.keys()})
