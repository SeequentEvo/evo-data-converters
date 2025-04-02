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
from typing import Optional

import omf


@dataclass
class OMFMetadata:
    name: Optional[str] = ""
    revision: Optional[str] = ""
    description: Optional[str] = ""

    def to_project(self, elements: list[omf.base.ProjectElement] = []) -> omf.Project:
        """Create an OMF project from this metadata

        :param elements: List of ProjectElement objects to include in the project.
        """
        project = omf.Project(name=self.name, description=self.description, revision=self.revision)

        project.elements = elements
        assert project.validate()

        return project
