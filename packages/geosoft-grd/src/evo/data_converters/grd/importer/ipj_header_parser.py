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
from .ipj_header import IPJ_Header


class IPJ_Header_Parser:
    @staticmethod
    def parse(data) -> IPJ_Header:
        header = IPJ_Header()

        # Read 12 bytes (3 x int32) from offset 0
        header.lSerialID, header.lID, header.lVersion = struct.unpack_from("<iii", data, 0)

        return header
