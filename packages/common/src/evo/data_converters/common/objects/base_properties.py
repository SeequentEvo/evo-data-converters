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
    def __init__(
        self,
        *,
        name: str,
        uuid: str | None = None,
        description: str | None = None,
        extensions: dict[str, typing.Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        self.name: str = name
        self.uuid: str | None = uuid
        self.description: str | None = description
        self.extensions: dict[str, typing.Any] | None = extensions
        self.tags: dict[str, str] | None = tags


class BaseSpatialDataProperties(BaseObjectProperties):
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
        super().__init__(name=name, uuid=uuid, description=description, extensions=extensions, tags=tags)
        self.coordinate_reference_system: int | str = coordinate_reference_system or "unspecified"

    def get_bounding_box(self) -> list[float]:
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
