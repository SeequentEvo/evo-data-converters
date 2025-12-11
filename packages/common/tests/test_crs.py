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

from unittest import TestCase

from evo_schemas.components import Crs_V1_0_1 as Crs
from evo_schemas.components import Crs_V1_0_1_EpsgCode as Crs_EpsgCode
from evo_schemas.components import Crs_V1_0_1_OgcWkt as Crs_OgcWkt

from evo.data_converters.common import crs_from_any, crs_from_epsg_code, crs_from_ogc_wkt, crs_unspecified


class TestCrs(TestCase):
    """
    Tests for crs
    """

    ogc_wkt_string = """
PROJCS["NZGD2000 / New Zealand Transverse Mercator 2000",
    GEOGCS["NZGD2000",
        DATUM["New Zealand Geodetic Datum 2000",
            SPHEROID["GRS 1980", 6378137, 298.257222101],
            TOWGS84[0,0,0,0,0,0,0]
        ],
        PRIMEM["Greenwich", 0],
        UNIT["degree", 0.0174532925199433],
        AUTHORITY["EPSG","4167"]
    ],
    PROJECTION["Transverse_Mercator"],
    PARAMETER["latitude_of_origin", 0],
    PARAMETER["central_meridian", 173],
    PARAMETER["scale_factor", 0.9996],
    PARAMETER["false_easting", 1600000],
    PARAMETER["false_northing", 10000000],
    UNIT["metre",1],
    AUTHORITY["EPSG","2193"]
]
"""
    expected_ogc_wkt = """BOUNDCRS[SOURCECRS[PROJCRS["NZGD2000 / New Zealand Transverse Mercator 2000",BASEGEOGCRS["NZGD2000",DATUM["New Zealand Geodetic Datum 2000",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4167]],CONVERSION["unnamed",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",173,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",1600000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",10000000,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],ID["EPSG",2193]]],TARGETCRS[GEOGCRS["WGS 84",DATUM["World Geodetic System 1984",ELLIPSOID["WGS 84",6378137,298.257223563,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],CS[ellipsoidal,2],AXIS["latitude",north,ORDER[1],ANGLEUNIT["degree",0.0174532925199433]],AXIS["longitude",east,ORDER[2],ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4326]]],ABRIDGEDTRANSFORMATION["Transformation from NZGD2000 to WGS84",METHOD["Position Vector transformation (geog2D domain)",ID["EPSG",9606]],PARAMETER["X-axis translation",0,ID["EPSG",8605]],PARAMETER["Y-axis translation",0,ID["EPSG",8606]],PARAMETER["Z-axis translation",0,ID["EPSG",8607]],PARAMETER["X-axis rotation",0,ID["EPSG",8608]],PARAMETER["Y-axis rotation",0,ID["EPSG",8609]],PARAMETER["Z-axis rotation",0,ID["EPSG",8610]],PARAMETER["Scale difference",1,ID["EPSG",8611]]]]"""

    def test_integer_epsg_code_crs(self) -> None:
        epsg_code = 2193
        crs_obj = crs_from_epsg_code(epsg_code)
        self.assertIsInstance(crs_obj, Crs_EpsgCode)
        self.assertEqual(epsg_code, crs_obj.epsg_code)

    def test_string_epsg_code_crs_with_prefix(self) -> None:
        epsg_code = 2193
        epsg_code_str = f"EPSG:{epsg_code}"
        crs_obj = crs_from_epsg_code(epsg_code_str)
        self.assertIsInstance(crs_obj, Crs_EpsgCode)
        self.assertEqual(epsg_code, crs_obj.epsg_code)

    def test_string_epsg_code_crs_without_prefix(self) -> None:
        epsg_code = 2193
        epsg_code_str = str(epsg_code)
        crs_obj = crs_from_epsg_code(epsg_code_str)
        self.assertIsInstance(crs_obj, Crs_EpsgCode)
        self.assertEqual(epsg_code, crs_obj.epsg_code)

    def test_raise_expected_exception_when_epsg_code_is_invalid(self) -> None:
        exception_msg = "Invalid or unrecognized EPSG code"
        with self.assertRaises(ValueError) as context:
            crs_from_epsg_code(0)
        self.assertIn(exception_msg, str(context.exception))

    def test_ogc_wkt_crs(self) -> None:
        crs_obj = crs_from_ogc_wkt(self.ogc_wkt_string)
        self.assertIsInstance(crs_obj, Crs_OgcWkt)
        self.assertEqual(crs_obj.ogc_wkt, self.expected_ogc_wkt)

    def test_raise_expected_exception_when_ogc_wkt_is_invalid(self) -> None:
        exception_msg = "Invalid or unrecognized WKT string: Invalid WKT string: invalid wkt"
        with self.assertRaises(ValueError) as context:
            crs_from_ogc_wkt("invalid wkt")
        self.assertIn(exception_msg, str(context.exception))

    def test_raise_expected_exception_when_esri_wkt_is_found(self) -> None:
        exception_msg = "Invalid or unrecognized WKT string: Invalid WKT string: ESRI wkt string"
        with self.assertRaises(ValueError) as context:
            crs_from_ogc_wkt("ESRI wkt string")
        self.assertIn(exception_msg, str(context.exception))

    def test_unspecified_crs(self) -> None:
        crs_obj = crs_unspecified()
        self.assertIsInstance(crs_obj, Crs)
        self.assertEqual("unspecified", crs_obj)

    def test_any_integer_epsg_code_crs(self) -> None:
        epsg_code = 2193
        crs_obj = crs_from_any(epsg_code)
        self.assertIsInstance(crs_obj, Crs_EpsgCode)
        self.assertEqual(epsg_code, crs_obj.epsg_code)

    def test_any_string_epsg_code_crs_with_prefix(self) -> None:
        epsg_code = 2193
        epsg_code_str = f"EPSG:{epsg_code}"
        crs_obj = crs_from_any(epsg_code_str)
        self.assertIsInstance(crs_obj, Crs_EpsgCode)
        self.assertEqual(epsg_code, crs_obj.epsg_code)

    def test_any_string_epsg_code_crs_without_prefix(self) -> None:
        epsg_code = 2193
        epsg_code_str = str(epsg_code)
        crs_obj = crs_from_any(epsg_code_str)
        self.assertIsInstance(crs_obj, Crs_EpsgCode)
        self.assertEqual(epsg_code, crs_obj.epsg_code)

    def test_any_raise_expected_exception_when_epsg_code_is_invalid(self) -> None:
        exception_msg = "Invalid or unrecognized EPSG code"
        with self.assertRaises(ValueError) as context:
            crs_from_any(0)
        self.assertIn(exception_msg, str(context.exception))

    def test_any_ogc_wkt_crs(self) -> None:
        crs_obj = crs_from_any(self.ogc_wkt_string)
        self.assertIsInstance(crs_obj, Crs_OgcWkt)
        self.assertEqual(crs_obj.ogc_wkt, self.expected_ogc_wkt)

    def test_any_raise_expected_exception_when_ogc_wkt_is_invalid(self) -> None:
        exception_msg = "Invalid or unrecognized CRS definition: invalid wkt"
        with self.assertRaises(ValueError) as context:
            crs_from_any("invalid wkt")
        self.assertIn(exception_msg, str(context.exception))

    def test_any_raise_expected_exception_when_esri_wkt_is_found(self) -> None:
        exception_msg = "Invalid or unrecognized CRS definition: ESRI wkt string"
        with self.assertRaises(ValueError) as context:
            crs_from_any("ESRI wkt string")
        self.assertIn(exception_msg, str(context.exception))

    def test_any_unspecified_crs(self) -> None:
        crs_obj = crs_from_any(None)
        self.assertIsInstance(crs_obj, Crs)
        self.assertEqual("unspecified", crs_obj)

    def test_any_unspecified_crs_from_literal_unspecified(self) -> None:
        crs_obj = crs_from_any("unspecified")
        self.assertIsInstance(crs_obj, Crs)
        self.assertEqual("unspecified", crs_obj)

    def test_any_unspecified_crs_no_args(self) -> None:
        crs_obj = crs_from_any()
        self.assertIsInstance(crs_obj, Crs)
        self.assertEqual("unspecified", crs_obj)
