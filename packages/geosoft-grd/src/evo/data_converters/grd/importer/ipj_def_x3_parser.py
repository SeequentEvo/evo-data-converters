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
from .ipj_def_x3 import IPJ_DEF_X3


class IPJ_DEF_X3_Parser:
    @staticmethod
    def parse(file, offset: int) -> IPJ_DEF_X3:
        obj = IPJ_DEF_X3()

        # Read szAuthority (64 bytes)
        obj.szAuthority = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        # Read lAuthoritativeID, lSafeProjType (2 x int32)
        obj.lAuthoritativeID, obj.lSafeProjType = struct.unpack_from("<ii", file, offset)
        offset += 8

        return obj
