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

import struct
from .orientation import Orientation


class Orientation_Parser:
    @staticmethod
    def parse(file, offset: int) -> Orientation:
        obj = Orientation()

        # Read eType (int32)
        obj.eType = struct.unpack_from("<i", file, offset)[0]
        offset += 4

        # Read dXo, dYo, dZo (3 x double)
        obj.dXo, obj.dYo, obj.dZo = struct.unpack_from("<ddd", file, offset)
        offset += 24

        # Read pdParms (8 x double)
        obj.pdParms = list(struct.unpack_from("<dddddddd", file, offset))
        offset += 64

        return obj
