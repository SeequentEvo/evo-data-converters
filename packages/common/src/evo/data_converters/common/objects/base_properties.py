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

import typing
from abc import ABC


class BaseObjectProperties(ABC):
    """Abstract base class for common object properties"""

    def __init__(
        self,
        *,
        name: str,
        uuid: str | None = None,
        description: str | None = None,
        extensions: dict[str, typing.Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """
        Initialise base object properties.

        :param name: The name of the object
        :param uuid: Optional unique identifier for the object
        :param description: Optional textual description of the object
        :param extensions: Optional dictionary of custom extension data
        :param tags: Optional key-value pairs for tagging/categorizing the object
        """
        self.name: str = name
        self.uuid: str | None = uuid
        self.description: str | None = description
        self.extensions: dict[str, typing.Any] | None = extensions
        self.tags: dict[str, str] | None = tags


class BaseSpatialDataProperties(BaseObjectProperties):
    """
    Abstract base class for spatial data properties.

    Extends BaseObjectProperties with spatial data capabilities, including
    coordinate reference system support and bounding box functionality.
    """

    def __init__(
        self,
        *,
        name: str,
        uuid: str | None = None,
        coordinate_reference_system: int | str | None = None,
        description: str | None = None,
        extensions: dict[str, typing.Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """
        Initialise base spatial data properties.

        :param name: The name of the spatial object
        :param uuid: Optional unique identifier for the object
        :param coordinate_reference_system: Optional CRS identifier (EPSG code or WKT string)
        :param description: Optional textual description of the object
        :param extensions: Optional dictionary of custom extension data
        :param tags: Optional key-value pairs for tagging/categorizing the object
        """
        super().__init__(name=name, uuid=uuid, description=description, extensions=extensions, tags=tags)
        self.coordinate_reference_system: int | str | None = coordinate_reference_system

    def get_bounding_box(self) -> list[float]:
        """
        Get the bounding box for the spatial data.

        Default implementation returns a zero-initialised bounding box.
        Subclasses should override this method to provide actual spatial extent.

        :return: List of 6 floats [min_x, max_x, min_y, max_y, min_z, max_z]
        """
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
