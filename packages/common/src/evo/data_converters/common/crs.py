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

from pyproj import CRS
from pyproj._crs import is_wkt
from pyproj.exceptions import CRSError

from evo_schemas.components import Crs_V1_0_1 as Crs
from evo_schemas.components import Crs_V1_0_1_EpsgCode as Crs_EpsgCode
from evo_schemas.components import Crs_V1_0_1_OgcWkt as Crs_OgcWkt


class InvalidCRSError(ValueError):
    """Raised when a CRS definition cannot be parsed or validated."""


def _is_epsg_code(auth_code: int | str) -> bool:
    if isinstance(auth_code, int):
        return True
    if isinstance(auth_code, str) and auth_code.isnumeric():
        return True
    if isinstance(auth_code, str) and "EPSG:" in auth_code:
        return True
    return False


def crs_from_epsg_code(epsg_code: int | str) -> Crs_EpsgCode:
    """Parse and validate an EPSG code.

    If valid, return the Crs geoscience object with the integer EPSG code.

    :raises InvalidCRSError: If the EPSG code is invalid, unrecognized,
        or does not resolve to an EPSG authority.
    """
    if not _is_epsg_code(epsg_code):
        raise InvalidCRSError(f"Invalid or unrecognized EPSG code '{epsg_code}'")

    try:
        crs = CRS.from_user_input(epsg_code)
    except CRSError as e:
        raise InvalidCRSError(f"Invalid or unrecognized EPSG code '{epsg_code}'") from e

    authority = crs.to_authority()
    if not authority or authority[0] != "EPSG":
        raise InvalidCRSError(f"Input '{epsg_code}' resolved to authority '{authority}', not EPSG")

    return Crs_EpsgCode(epsg_code=int(authority[1]))


def crs_from_ogc_wkt(wkt_string: str) -> Crs_OgcWkt:
    """Parse an OGC WKT string.

    If valid, return the Crs geoscience object with normalized WKT2 string.

    :raises InvalidCRSError: If the WKT string is invalid or cannot be parsed.
    """
    try:
        crs = CRS.from_wkt(wkt_string)

        # Return Crs with canonical WKT2 format
        return Crs_OgcWkt(ogc_wkt=crs.to_wkt(version="WKT2_2019"))
    except CRSError as e:
        raise InvalidCRSError(f"Invalid or unrecognized WKT string: {e}") from e


def crs_unspecified() -> Crs:
    """
    When the Crs is not specified, the goescience Crs object is
    returned as a simple string constant
    """
    return "unspecified"


def crs_from_any(crs_def: str | int | None = None) -> Crs | Crs_EpsgCode | Crs_OgcWkt:
    """Select the applicable function to create a Crs geoscience object from *crs_def*.

    :raises InvalidCRSError: If the input is not a valid CRS definition.

    Usage:
        crs = crs_from_any()
        crs = crs_from_any(None)
        crs = crs_from_any(2193)
        crs = crs_from_any("2193")
        crs = crs_from_any("EPSG:2193")
        crs = crs_from_any("<valid OGC WKT string>")
    """
    if crs_def is None or crs_def == "unspecified":
        return crs_unspecified()
    elif _is_epsg_code(crs_def):
        return crs_from_epsg_code(crs_def)
    elif is_wkt(crs_def):
        return crs_from_ogc_wkt(crs_def)
    else:
        raise InvalidCRSError(f"Invalid or unrecognized CRS definition: {crs_def}")
