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

from pathlib import Path

import shapefile
from evo.data_converters.shp.importer.exceptions import InvalidSHPError
from evo.data_converters.shp.importer.implementation.mesh_builder import MeshBuilder
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components import BoundingBox_V1_0_1, Crs_V1_0_1
from evo_schemas.objects.triangle_mesh import TriangleMesh_V2_2_0


class ShpParser:
    """
    Converts multipatch shapefiles (consiting of at least .shp, .shx, and .dbf files) to Triangle Mesh format.
    Currently only supports multipatch files without rings.
    """

    def __init__(self, path: str, data_client: ObjectDataClient, crs: Crs_V1_0_1, tags: dict[str, str] = None):
        """
        Initialize the shapefile to triangle mesh converter.

        :param path: The path to the input shapefile. Can be just the basename, a path to any component file, or
        a path to a zip file containing the shapefile.
        :param data_client: Object data client for uploading parquet files (real or stub).
        :param crs: Coordiante reference system to use for the file. Cannot be None, but can be "unspecified".
        :param tags: (Optional) Dict of tags to add to the Geoscience Object(s)."
        """
        self.path = path
        self.data_client = data_client
        self.crs = crs
        self.tags = tags

    def parse_shp(self) -> TriangleMesh_V2_2_0:
        """
        Open, validate, and parse the shapefile, converting and returning it as a Triangle Mesh.

        :return: Triangle Mesh object representing the input shapefile.

        :raise InvalidSHPError: If the input shapefile is invalid or cannot be parsed
        """
        with shapefile.Reader(self.path) as sf:
            if sf.shapeType != shapefile.MULTIPATCH:
                raise InvalidSHPError(
                    "Provided shapefile is not multipatch. Only multipatch shapefiles without rings are supported."
                )

            mesh_builder = MeshBuilder(self.data_client, sf.fields[1:])

            bounding_box = BoundingBox_V1_0_1(
                min_x=sf.bbox[0],
                min_y=sf.bbox[1],
                min_z=sf.zbox[0] or 0.0,
                max_x=sf.bbox[2],
                max_y=sf.bbox[3],
                max_z=sf.zbox[1] or 0.0,
            )

            for shape_record in sf.iterShapeRecords():
                mesh_builder.add_shape_record(shape_record)

            embedded_mesh = mesh_builder.build()

            return TriangleMesh_V2_2_0(
                triangles=embedded_mesh.triangles,
                parts=embedded_mesh.parts,
                name=Path(self.path).stem,
                uuid=None,
                tags=self.tags,
                bounding_box=bounding_box,
                coordinate_reference_system=self.crs,
            )
