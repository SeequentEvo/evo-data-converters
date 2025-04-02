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

from dataclasses import dataclass


@dataclass
class ResqmlConversionOptions:
    """Options to control the conversion of RESQML files"""

    """Only the active cells in grids are to be exported (default True)"""
    active_cells_only: bool = True

    """The grid.corner_points array can get very large.
       Grids will only be converted if the estimated size of grid.corner_points
       is less than the threshold

       Default 8 GiB"""
    memory_threshold: int = 8 * 1024 * 1024 * 1024
