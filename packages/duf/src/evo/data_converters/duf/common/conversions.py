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

import numpy
import pandas

import evo.data_converters.duf.common.deswik_types as dw
from evo.data_converters.duf.common.types import AttributedEvoData, FetchedTriangleMesh, FetchedLines
from evo.data_converters.duf.common.attributes import EvoAttributes

EVO_TO_DW_TYPE_CONVERSION = {
    "string": dw.AttributeType.String,
    "scalar": dw.AttributeType.Double,
    "category": dw.AttributeType.String,
    "date_time": dw.AttributeType.DateTime,
    "integer": dw.AttributeType.Integer,
}


def np_to_dw(maybe_np):
    if isinstance(maybe_np, str) or numpy.issubdtype(maybe_np, numpy.str_):
        return str(maybe_np)
    elif isinstance(maybe_np, float) or numpy.issubdtype(maybe_np, numpy.floating):
        f = float(maybe_np)
        if numpy.isnan(f):
            # It appears that missing attributes in Deswik CAD are represented as an empty string
            return ""
        else:
            return f
    elif numpy.issubdtype(maybe_np, numpy.datetime64):
        return pandas.to_datetime(maybe_np).strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(maybe_np, int) or numpy.issubdtype(maybe_np, numpy.integer):
        return int(maybe_np)
    else:
        raise NotImplementedError(f"Unhandled type {type(maybe_np)}")


class Layer:
    def __init__(self, layer, dw_attributes):
        self.layer = layer
        self._attributes = dw_attributes

    @staticmethod
    def _get_unique_layer_name(duf, name: str):
        if not name:
            name = "default"
        if not duf.LayerExists(name):
            return name
        suffix = 2
        while duf.LayerExists(new_name := f"{name} ({suffix})"):
            suffix += 1
        return new_name

    @staticmethod
    def with_attributes(duf, evo_data: AttributedEvoData):
        new_layer_name = Layer._get_unique_layer_name(duf, evo_data.name)
        new_layer = duf.NewLayer(new_layer_name)
        dw_attributes = {
            attr.name: new_layer.AddAttribute(attr.name, EVO_TO_DW_TYPE_CONVERSION[attr.type])
            for attr in evo_data.attributes
        }
        return Layer(new_layer, dw_attributes)

    def __getitem__(self, item: str):
        return self._attributes[item]

    def set_attributes_to_entity(self, dw_entity, evo_attributes: list[EvoAttributes], i: int):
        for attr in evo_attributes:
            if attr.nan_mask is not None and attr.nan_mask[i]:
                # Missing/None/Null values get written as the empty string
                value = ""
            else:
                value = attr.values[i]
            converted = np_to_dw(value)
            dw_attr = self[attr.name]
            dw_entity.SetAttribute(dw_attr, converted)


class EvoDUFWriter:
    def __init__(self, duf):
        self._duf = duf

    def write_mesh_triangles(self, mesh_triangles: FetchedTriangleMesh):
        new_layer = Layer.with_attributes(self._duf, mesh_triangles)

        flattened_vertices = mesh_triangles.vertices.flatten()

        for i, part in enumerate(mesh_triangles.parts):
            new_polyface = self._duf.NewPolyface(new_layer.layer)
            # It is annoying to pay this amount of overhead. Pythonnet converts automatically for double arrays
            # (and maybe even avoids a copy), but it doesn't work for numpy integer arrays. If performance or memory
            # becomes a concern, then consider handling the numpy objects explicitly in the C# Duf wrapper library.
            flattened_triangles = part.flatten().tolist()
            new_polyface.SetVertices3D(flattened_vertices, flattened_triangles)

            new_layer.set_attributes_to_entity(new_polyface, mesh_triangles.attributes, i)

    def write_lines(self, lines: FetchedLines):
        new_layer = Layer.with_attributes(self._duf, lines)

        for i, path in enumerate(lines.paths):
            new_polyline = self._duf.NewPolyline(new_layer.layer)
            new_polyline.SetVertices3D(path.flatten())

            new_layer.set_attributes_to_entity(new_polyline, lines.attributes, i)
