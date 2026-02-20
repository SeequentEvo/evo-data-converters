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

from .ipj_def_x4 import IPJ_DEF_X4

class IPJ_DEF_X4_Parser:
    @staticmethod
    def parse(file, offset: int) -> IPJ_DEF_X4:
        obj = IPJ_DEF_X4()
        
        # Read szDatum (129 bytes)
        raw_datum = file[offset:offset+129]
        obj.szDatum = raw_datum.decode('ascii', errors='ignore').rstrip('\x00')
        offset += 129
        
        # Read szDatumTrf (129 bytes)
        raw_datumtrf = file[offset:offset+129]
        obj.szDatumTrf = raw_datumtrf.decode('ascii', errors='ignore').rstrip('\x00')
        offset += 129
        
        return obj
