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

    def __init__(
        self,
        path: str,
        shx_path: str,
        dbf_path: str,
        data_client: ObjectDataClient,
        crs: Crs_V1_0_1,
        tags: dict[str, str] = None,
        cpg_path: str | None = None,
        sbn_path: str | None = None,
        sbx_path: str | None = None,
        xml_path: str | None = None,
    ):
        """
        Initialize the shapefile to triangle mesh converter.

        :param path: The path to the .shp geometry file.
        :param shx_path: The path to the .shx spatial index file.
        :param dbf_path: The path to the .dbf attribute file.
        :param data_client: Object data client for uploading parquet files (real or stub).
        :param crs: Coordiante reference system to use for the file. Cannot be None, but can be "unspecified".
        :param tags: (Optional) Dict of tags to add to the Geoscience Object(s).
        :param cpg_path: (Optional) Path to the .cpg code page file. If provided, the encoding
        specified in the file will be used when reading the .dbf attribute data.
        :param sbn_path: (Optional) Path to the .sbn spatial index file. Accepted but not currently used.
        :param sbx_path: (Optional) Path to the .sbx spatial index file. Accepted but not currently used.
        :param xml_path: (Optional) Path to the .shp.xml metadata file. Accepted but not currently used.
        """
        self.path = path
        self.shx_path = shx_path
        self.dbf_path = dbf_path
        self.data_client = data_client
        self.crs = crs
        self.tags = tags
        self.cpg_path = cpg_path
        self.sbn_path = sbn_path
        self.sbx_path = sbx_path
        self.xml_path = xml_path

    def parse_shp(self) -> TriangleMesh_V2_2_0:
        """
        Open, validate, and parse the shapefile, converting and returning it as a Triangle Mesh.

        :return: Triangle Mesh object representing the input shapefile.

        :raise InvalidSHPError: If the input shapefile is invalid or cannot be parsed
        """
        reader_kwargs: dict = {"shp": self.path, "shx": self.shx_path, "dbf": self.dbf_path}
        if self.cpg_path is not None:
            with open(self.cpg_path) as f:
                reader_kwargs["encoding"] = f.read().strip()

        with shapefile.Reader(**reader_kwargs) as sf:
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
