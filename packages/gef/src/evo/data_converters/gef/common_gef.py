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
import dataclasses
import enum
from pathlib import Path

from pygef.cpt import CPTData


class CPTSource(enum.Enum):
    GEF = enum.auto()
    BRO_XML = enum.auto()
    UNKNOWN = enum.auto()

    @classmethod
    def infer_from_filename(cls, filename: str):
        ext = Path(filename).suffix.lower()
        if ext == ".gef":
            return cls.GEF
        elif ext == ".xml":
            return cls.BRO_XML
        else:
            return cls.UNKNOWN

    @classmethod
    def infer_from_cpt_data(cls, cpt_data: CPTData):
        if cpt_data.alias is not None:
            return cls.GEF
        elif cpt_data.bro_id is not None:
            return cls.BRO_XML
        else:
            return cls.UNKNOWN


@dataclasses.dataclass
class CPTContext:
    filename: str

    @property
    def source_type(self) -> CPTSource:
        return CPTSource.infer_from_filename(self.filename)
