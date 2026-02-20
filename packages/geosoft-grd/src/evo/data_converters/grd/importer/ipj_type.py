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

from enum import Enum

# Define proj_type class with IPJ_CS enum
class PROJ_TYPE_ENUM(Enum):
    IPJ_CS_UNKNOWN = 0
    IPJ_CS_GEOGRAPHIC = 1
    IPJ_CS_LAMBERT_CONFORMAL_CONIC_1SP = 2
    IPJ_CS_LAMBERT_CONFORMAL_CONIC_2SP = 3
    IPJ_CS_LAMBERT_CONFORMAL_CONIC_2SP_BELGIUM = 4
    IPJ_CS_ALBERS_CONIC = 5
    IPJ_CS_EQUIDISTANT_CONIC = 6
    IPJ_CS_POLYCONIC = 7
    IPJ_CS_MERCATOR_1SP = 8
    IPJ_CS_MERCATOR_2SP = 9
    IPJ_CS_CASSINI_SOLDNER = 10
    IPJ_CS_TRANSVERSE_MERCATOR = 11
    IPJ_CS_TRANSVERSE_MERCATOR_SOUTH = 12
    IPJ_CS_TRANSVERSE_MERCATOR_SPHERICAL = 13
    IPJ_CS_POLAR_STEREOGRAPHIC = 14
    IPJ_CS_OBLIQUE_STEREOGRAPHIC = 15
    IPJ_CS_NEW_ZEALAND = 16
    IPJ_CS_HOTINE_OBLIQUE_MERCATOR = 17
    IPJ_CS_HOTINE_OBLIQUE_MERCATOR_2POINT = 18
    IPJ_CS_LABORDE_OBLIQUE_MERCATOR = 19
    IPJ_CS_SWISS_OBLIQUE_CYLINDRICAL = 20
    IPJ_CS_OBLIQUE_MERCATOR = 21
    IPJ_CS_LAMBERT_AZIMUTHAL_EQUALAREA = 22
    IPJ_CS_ROBINSON = 23
    IPJ_CS_KROVAK_NORTH_ORIENTATED = 24
    IPJ_CS_KROVAK_MODIFIED_NORTH_ORIENTATED = 25
    IPJ_CS_LOCAL = 26
    IPJ_CS_VAN_DER_GRINTEN = 27
    IPJ_CS_WEB_MERCATOR = 28
    IPJ_CS_POLAR_STEREOGRAPHIC_B = 29
    IPJ_CS_TRANSVERSE_MERCATOR_COMPLEX = 30
    IPJ_CS_MOLLWEIDE = 31
    IPJ_CS_MAX = 32   

class PROJ_TYPE:
    @staticmethod
    def parse_ipj_to_proj_type(type: int) -> str:
        mapping = {
            PROJ_TYPE_ENUM.IPJ_CS_LAMBERT_CONFORMAL_CONIC_1SP.value: "Lambert Conic Conformal (1SP)",
            PROJ_TYPE_ENUM.IPJ_CS_LAMBERT_CONFORMAL_CONIC_2SP.value: "Lambert Conic Conformal (2SP)",
            PROJ_TYPE_ENUM.IPJ_CS_LAMBERT_CONFORMAL_CONIC_2SP_BELGIUM.value: "Lambert Conic Conformal (2SP Belgium)",
            PROJ_TYPE_ENUM.IPJ_CS_KROVAK_NORTH_ORIENTATED.value: "Krovak (North Orientated)",
            PROJ_TYPE_ENUM.IPJ_CS_KROVAK_MODIFIED_NORTH_ORIENTATED.value: "Krovak Modified (North Orientated)",
            PROJ_TYPE_ENUM.IPJ_CS_ALBERS_CONIC.value: "Albers Equal Area",
            PROJ_TYPE_ENUM.IPJ_CS_POLYCONIC.value: "American Polyconic",
            PROJ_TYPE_ENUM.IPJ_CS_MERCATOR_1SP.value: "Mercator",
            PROJ_TYPE_ENUM.IPJ_CS_TRANSVERSE_MERCATOR_SPHERICAL.value: "Mercator (Spherical)",
            PROJ_TYPE_ENUM.IPJ_CS_WEB_MERCATOR.value: "Web Mercator",
            PROJ_TYPE_ENUM.IPJ_CS_CASSINI_SOLDNER.value: "Cassini-Soldner",
            PROJ_TYPE_ENUM.IPJ_CS_TRANSVERSE_MERCATOR.value: "Transverse Mercator",
            PROJ_TYPE_ENUM.IPJ_CS_TRANSVERSE_MERCATOR_SOUTH.value: "Transverse Mercator (South Orientated)",
            PROJ_TYPE_ENUM.IPJ_CS_OBLIQUE_MERCATOR.value: "Oblique Mercator",
            PROJ_TYPE_ENUM.IPJ_CS_HOTINE_OBLIQUE_MERCATOR.value: "Hotine Oblique Mercator",
            PROJ_TYPE_ENUM.IPJ_CS_LABORDE_OBLIQUE_MERCATOR.value: "Laborde Oblique Mercator",
            PROJ_TYPE_ENUM.IPJ_CS_LAMBERT_AZIMUTHAL_EQUALAREA.value: "Lambert Cylindrical Equal Area (Spherical)",
            PROJ_TYPE_ENUM.IPJ_CS_POLAR_STEREOGRAPHIC.value: "Stereographic",
            PROJ_TYPE_ENUM.IPJ_CS_OBLIQUE_STEREOGRAPHIC.value: "Oblique Stereographic",
            PROJ_TYPE_ENUM.IPJ_CS_ROBINSON.value: "Robison",
            PROJ_TYPE_ENUM.IPJ_CS_VAN_DER_GRINTEN.value: "Van Der Grinten",
            PROJ_TYPE_ENUM.IPJ_CS_MOLLWEIDE.value: "Mollweide",
            PROJ_TYPE_ENUM.IPJ_CS_NEW_ZEALAND.value: "New Zealand Map Grid",
            PROJ_TYPE_ENUM.IPJ_CS_TRANSVERSE_MERCATOR_COMPLEX.value: "Mercator variant C",
            PROJ_TYPE_ENUM.IPJ_CS_GEOGRAPHIC.value: "Geographic",
            PROJ_TYPE_ENUM.IPJ_CS_LOCAL.value: "Local",
        }
        return mapping.get(type, "Unknown Projection")
