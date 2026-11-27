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
    Configuration for mapping DataFrame columns to downhole collection data structures.

    Provides lists of possible column names for each type of column, allowing matching
    against various input formats. Column matching is case-insensitive.

    **Attributes:**

    - HOLE_INDEX_COLUMNS: Column names for the hole index (1-based integer relating to collar table)
    - DEPTH_COLUMNS: Column names for point measurement depths (used by DistanceTable)
    - FROM_COLUMNS: Column names for interval start depths (used by IntervalTable)
    - TO_COLUMNS: Column names for interval end depths (used by IntervalTable)

    Each attribute contains a list of possible column names to search for.
    """

    HOLE_INDEX_COLUMNS: list[str] = field(default_factory=lambda: ["hole_index"])
    """Column names that identify which hole each measurement belongs to (1-based index)."""

    DEPTH_COLUMNS: list[str] = field(default_factory=list)
    """Column names for point measurement depths/distances along the hole."""

    FROM_COLUMNS: list[str] = field(default_factory=list)
    """Column names for interval start depths."""

    TO_COLUMNS: list[str] = field(default_factory=list)
    """Column names for interval end depths."""

    DIP_COLUMNS: list[str] = field(default_factory=list)
    """Column names for downhole inclinations."""

    AZIMUTH_COLUMNS: list[str] = field(default_factory=list)
    """Column names for azimuth values."""
