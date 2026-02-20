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

from .ipj_def_x2 import IPJ_DEF_X2


class IPJ_DEF_X2_Parser:
    @staticmethod
    def parse(file, offset: int) -> IPJ_DEF_X2:
        obj = IPJ_DEF_X2()

        # Read szIPJ2 (64 bytes)
        obj.szIPJ2 = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        return obj
