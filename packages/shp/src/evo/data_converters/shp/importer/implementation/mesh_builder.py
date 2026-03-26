#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from collections.abc import Iterable

import pyarrow as pa
import shapefile
from evo.data_converters.shp.importer.exceptions import InvalidSHPError
from evo.data_converters.shp.importer.implementation.triangles_builder import TrianglesBuilder
from evo.data_converters.shp.importer.implementation.utils import date_to_evo_timestamp
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components import (
    BoolAttribute_V1_1_0,
    ContinuousAttribute_V1_1_0,
    DateTimeAttribute_V1_1_0,
    EmbeddedTriangulatedMesh_V2_1_0,
    EmbeddedTriangulatedMesh_V2_1_0_Parts,
    IntegerAttribute_V1_1_0,
    NanCategorical_V1_0_1,
    NanContinuous_V1_0_1,
    OneOfAttribute_V1_2_0_Item,
    StringAttribute_V1_1_0,
)
from evo_schemas.elements import (
    BoolArray1_V1_0_1,
    DateTimeArray_V1_0_1,
    FloatArray1_V1_0_1,
    IndexArray2_V1_0_1,
    IntegerArray1_V1_0_1,
    StringArray_V1_0_1,
)
from numpy import iinfo


class MeshBuilder:
    """Uses pyshp ShapeRecords to build an EmbeddedTriangulatedMesh and associated objects."""

    class _Mesh_Part_Data:
        """
        Represents one set of attributes for the mesh parts.
        """

        def __init__(self, nan_def, data_type: shapefile.FieldType):
            """
            :param nan_def: The value of NaN for this data type.
            :param data_type: The pyshp data type of this attruibute.
            """
            self.nan_def = nan_def
            self.data_type = data_type
            self.data = []

    data_client: ObjectDataClient
    triangles_builder: TrianglesBuilder
    mesh_parts: list[tuple[int, int]]
    mesh_part_attributes: dict[str, _Mesh_Part_Data]

    def __init__(self, data_client: ObjectDataClient, fields: Iterable[shapefile.Field]):
        """
        Intialize the MeshBuilder.

        :param data_client: Object data client for uploading parquet files (real or stub).
        :param fields: A list of the shapefile fields and their data types.
        """
        self.data_client = data_client
        self.triangles_builder = TrianglesBuilder(data_client)
        self.mesh_parts = []
        self.mesh_part_attributes = {}

        for field in fields:
            self.mesh_part_attributes[field.name] = self._Mesh_Part_Data(
                self._get_nan_def(field.field_type), field.field_type
            )

    def add_shape_record(self, shape_record: shapefile.ShapeRecord):
        """
        Adds all triangles and attributes in the provided ShapeRecord to the mesh.

        :param shape_record: The ShapeRecord to add.

        :raise: InvalidSHPError if the shaperecord is not a multipatch or contains rings.
        """
        shape = shape_record.shape
        record = shape_record.record

        # TODO: Need to figure out how to handle NULL shapes. These are 'shapes' which have associated data but no geometry. Perhaps storing them in a separate file is best? For now we discard them.
        if shape.shapeType == shapefile.NULL:
            return

        # The last part extends to the end of the array, so we bookend it here for easier parsing.
        parts = list(shape.parts) + [len(shape.points)]
        points = self._shppoint_to_XYZ(shape.points, shape.z)

        shape_start = self.triangles_builder.get_num_triangles()
        shape_length = 0

        for i in range(len(parts) - 1):
            start = parts[i]
            end = parts[i + 1]
            partXYZ = points[start:end]
            partM = shape.m[start:end]
            match shape.partTypes[i]:
                case shapefile.TRIANGLE_STRIP:
                    shape_length += self.add_triangle_strip(partXYZ, partM)
                case shapefile.TRIANGLE_FAN:
                    shape_length += self.add_triangle_fan(partXYZ, partM)
                case _:
                    raise InvalidSHPError(
                        "Provided shapefile contains rings. Only multipatch shapefiles without rings are supported."
                    )

        record_dict = record.as_dict()
        for key in self.mesh_part_attributes.keys():
            value = record_dict.get(key)
            # Convert dates to a microsecond timestamp.
            if self.mesh_part_attributes[key].data_type == shapefile.FieldType.D:
                value = date_to_evo_timestamp(value)

            default = self.mesh_part_attributes[key].nan_def
            self.mesh_part_attributes[key].data += [value if value is not None else default]

        self.mesh_parts.append((shape_start, shape_length))

    def add_triangle_strip(self, partXYZ: list[tuple[float, float, float]], partM: list[float | None]) -> int:
        """
        Adds a list of points stored in triangle strip format and associated point data to the mesh. Triangle strips
        are a set of points where every triple of consectuive points represents a triangle, so given points [a, b, c, d, e],
        the triangles are a-b-c, b-c-d, and c-d-e.

        :param partXYZ: Points stored in the triangle mesh format.
        :params partM: Point data for every point. len(partM) == len(partXYZ)

        :return: The number of triangles added.
        """
        triangles_added = 0
        for i in range(len(partXYZ) - 2):
            self.triangles_builder.add_triangle(partXYZ[i : i + 3], partM[i : i + 3])
            triangles_added += 1

        return triangles_added

    def add_triangle_fan(self, partXYZ: list[tuple[float, float, float]], partM: list[float | None]) -> int:
        """
        Adds a list of points stored in triangle fan format and associated point data to the mesh. Triangle fans
        are a set of points where every consecutive double of points forms a triangle with the first point, so
        given points [a, b, c, d, e], the triangles are a-b-c, a-c-d, and a-d-e.

        :param partXYZ: Points stored in the triangle mesh format.
        :params partM: Point data for every point. len(partM) == len(partXYZ)

        :return: The number of triangles added.
        """
        assert len(partM) == len(partXYZ), (
            "Not every point has a value (if a point has no value, an explicit None should be provided.)."
        )

        triangles_added = 0
        center_vertex = partXYZ[0]
        center_data = partM[0]
        for i in range(1, len(partXYZ) - 1):
            triangle = [center_vertex] + partXYZ[i : i + 2]
            triangle_data = [center_data] + partM[i : i + 2]
            self.triangles_builder.add_triangle(triangle, triangle_data)
            triangles_added += 1

        return triangles_added

    def build(self) -> EmbeddedTriangulatedMesh_V2_1_0:
        """
        Builds an EmbeddedTriangleMesh from the ShapeRecords added so far.
        """
        attributes = []
        for name, part in self.mesh_part_attributes.items():
            attribute = self._attribute_from_mesh_part(name, part)
            attributes.append(attribute)

        # Mesh parts here do not correspond to shapefile 'parts' but instead shapefile 'shapes'. This is because records are per-shape.
        offset, count = zip(*self.mesh_parts)
        schema = pa.schema([("offset", pa.uint64()), ("count", pa.uint64())])
        table = pa.table({"offset": offset, "count": count}, schema=schema)
        chunk_hash = self._create_parquet_file(table)
        chunks = IndexArray2_V1_0_1(data=chunk_hash, length=len(self.mesh_parts))

        parts = EmbeddedTriangulatedMesh_V2_1_0_Parts(attributes=attributes, chunks=chunks)

        triangles = self.triangles_builder.build()

        return EmbeddedTriangulatedMesh_V2_1_0(triangles=triangles, parts=parts)

    def _shppoint_to_XYZ(
        self, points: Iterable[tuple[float, float]], z: Iterable[float]
    ) -> list[tuple[float, float, float]]:
        """
        Converts points stored in the (x, y), z format of pyshp to (x, y, z) format for ease of use.

        :param points: (x, y) coordinates of the points.
        :param z: z values for the points. len(z) == len(x, y)
        """
        assert len(points) == len(z), "Mismatched number of x, y, and z coordinates for shapefile points."
        return [points[i] + (z[i],) for i in range(len(points))]

    def _get_nan_def(self, field_type: shapefile.FieldType):
        """
        Get an appropriate default NaN definition for the given pyshp FieldType.

        :param field_type: pyshp field type.

        :return: A NaN value for the given type (usually the minimum value).
        """
        match field_type:
            case shapefile.FieldType.N:
                return iinfo("int64").min
            case shapefile.FieldType.F:
                return float("nan")
            case shapefile.FieldType.D:
                return iinfo("int64").min
            case _:
                return None

    def _attribute_from_mesh_part(self, field_name: str, part: _Mesh_Part_Data) -> OneOfAttribute_V1_2_0_Item:
        """
        Takes a mesh part and returns an appropriate geoscience object based on the field type.

        :param field_name: The name of the field.
        :param part: The data, NaN definition, and type of this part.

        :return: A geoscience object representing the part.
        """
        match part.data_type:
            case shapefile.FieldType.N:
                nan_description = NanCategorical_V1_0_1(values=[part.nan_def])
                schema = pa.schema([("values", pa.int64())])
                table = pa.table({"values": part.data}, schema=schema)
                data_hash = self._create_parquet_file(table)
                values = IntegerArray1_V1_0_1(data=data_hash, length=len(part.data), data_type="int64")
                return IntegerAttribute_V1_1_0(
                    name=field_name,
                    key=data_hash,
                    attribute_description=None,
                    nan_description=nan_description,
                    values=values,
                )
            case shapefile.FieldType.F:
                nan_description = NanContinuous_V1_0_1(values=[part.nan_def])
                schema = pa.schema([("values", pa.float64())])
                table = pa.table({"values": part.data}, schema=schema)
                data_hash = self._create_parquet_file(table)
                values = FloatArray1_V1_0_1(data=data_hash, length=len(part.data), data_type="float64")
                return ContinuousAttribute_V1_1_0(
                    name=field_name,
                    key=data_hash,
                    attribute_description=None,
                    nan_description=nan_description,
                    values=values,
                )
            case shapefile.FieldType.C | shapefile.FieldType.M:
                schema = pa.schema([("values", pa.string())])
                table = pa.table({"values": part.data}, schema=schema)
                data_hash = self._create_parquet_file(table)
                values = StringArray_V1_0_1(data=data_hash, length=len(part.data))
                return StringAttribute_V1_1_0(name=field_name, key=data_hash, attribute_description=None, values=values)
            case shapefile.FieldType.L:
                schema = pa.schema([("values", pa.bool_())])
                table = pa.table({"values": part.data}, schema=schema)
                data_hash = self._create_parquet_file(table)
                values = BoolArray1_V1_0_1(data=data_hash, length=len(part.data))
                return BoolAttribute_V1_1_0(name=field_name, key=data_hash, attribute_description=None, values=values)
            case shapefile.FieldType.D:
                schema = pa.schema([("values", pa.timestamp("us", tz="UTC"))])
                # pyshp provides dates as date objects so we must convert to datetimes. Time is set to 00:00:00.
                table = pa.table({"values": part.data}, schema=schema)
                nan_description = NanCategorical_V1_0_1(values=[part.nan_def])
                data_hash = self._create_parquet_file(table)
                values = DateTimeArray_V1_0_1(data=data_hash, length=len(part.data))
                return DateTimeAttribute_V1_1_0(
                    name=field_name,
                    key=data_hash,
                    attribute_description=None,
                    nan_description=nan_description,
                    values=values,
                )
            case _:
                return None

    def _create_parquet_file(self, table: pa.table) -> str:
        """
        Writes a parquet file from the given table using the data client.

        :param table: The table to write.

        :return: The file hash of the written table.
        """
        saved_table_info = self.data_client.save_table(table)
        return saved_table_info["data"]
