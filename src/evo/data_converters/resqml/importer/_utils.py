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

"""
Utility and common functions for RESQML
"""

import pathlib

from resqpy.grid import Grid
from resqpy.surface import Surface


def get_metadata(object: Surface | Grid) -> dict[str, dict[str, str | dict[str, str]]]:
    """Generate metadata about the source file, and the RESQML object"""
    name = object.citation_title or ""
    uuid = str(object.uuid or "")
    originator = object.originator or ""
    return {
        "resqml": {
            "epc_filename": pathlib.Path(object.model.epc_file).name,
            "name": name,
            "uuid": uuid,
            "originator": originator,
        },
    }
