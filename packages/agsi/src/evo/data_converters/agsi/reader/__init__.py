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

"""Reader for AGSi (AGS ground model data) packages.

Loads AGSi 1.0.x documents (and normalises pre-1.0 v0.6 documents to the 1.0.x layout) into
typed models, and parses the WKT, DXF and STL supporting geometry files into numpy arrays.
"""

from .adapter import CURRENT_VERSION, detect_version, is_legacy_version, normalise_document
from .errors import AGSIDataFileIOError, AGSIInvalidDataError
from .geometry_files import (
    GeometryData,
    GeometryFileFormat,
    TriangleMesh,
    chain_lines,
    parse_dxf,
    parse_geometry,
    parse_stl,
    parse_wkt,
    sniff_format,
)
from .models import (
    GEOMETRY_OBJECT_TYPES,
    AgsFile,
    AgsiDataParameterValue,
    AgsiDocument,
    AgsiGeometryAreaFromLines,
    AgsiGeometryFromFile,
    AgsiGeometryLayer,
    AgsiGeometryPlane,
    AgsiGeometryVolFromSurfaces,
    AgsiModel,
    AgsiModelAlignment,
    AgsiModelBoundary,
    AgsiModelElement,
    AgsProject,
    AgsProjectCoordinateSystem,
    AgsSchema,
)
from .package import AgsiPackage

__all__ = [
    "CURRENT_VERSION",
    "GEOMETRY_OBJECT_TYPES",
    "AGSIDataFileIOError",
    "AGSIInvalidDataError",
    "AgsFile",
    "AgsProject",
    "AgsProjectCoordinateSystem",
    "AgsSchema",
    "AgsiDataParameterValue",
    "AgsiDocument",
    "AgsiGeometryAreaFromLines",
    "AgsiGeometryFromFile",
    "AgsiGeometryLayer",
    "AgsiGeometryPlane",
    "AgsiGeometryVolFromSurfaces",
    "AgsiModel",
    "AgsiModelAlignment",
    "AgsiModelBoundary",
    "AgsiModelElement",
    "AgsiPackage",
    "GeometryData",
    "GeometryFileFormat",
    "TriangleMesh",
    "chain_lines",
    "detect_version",
    "is_legacy_version",
    "normalise_document",
    "parse_dxf",
    "parse_geometry",
    "parse_stl",
    "parse_wkt",
    "sniff_format",
]
