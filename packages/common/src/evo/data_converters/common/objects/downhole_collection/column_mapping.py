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

from dataclasses import dataclass, field


@dataclass
class ColumnMapping:
    """
    Provide a way to map dataframe configurations to a set of collection types
    """

    # The hole index should relate to the index of the hole_id in the collars table (1-based)
    HOLE_INDEX_COLUMNS: list[str] = field(default_factory=lambda: ["hole_index"])

    DEPTH_COLUMNS: list[str] = field(default_factory=list)

    FROM_COLUMNS: list[str] = field(default_factory=list)
    TO_COLUMNS: list[str] = field(default_factory=list)
