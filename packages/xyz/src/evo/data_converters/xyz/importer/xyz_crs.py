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

import pyproj as pyproj


def is_valid_epsg(epsg_code: int) -> bool:
    """Check if the provided EPSG code is valid."""
    try:
        pyproj.CRS.from_epsg(epsg_code)
        return True
    except pyproj.exceptions.CRSError:
        return False
