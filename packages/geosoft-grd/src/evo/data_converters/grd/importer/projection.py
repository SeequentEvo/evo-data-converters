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

from .ipj_header import IPJ_Header
from . import core_commons as commons
from .ipj_header_parser import IPJ_Header_Parser
from .ipj_def_x_parser import IPJ_DEF_X_Parser
from .ipj_def_x2_parser import IPJ_DEF_X2_Parser
from .ipj_def_x3_parser import IPJ_DEF_X3_Parser
from .ipj_def_x4_parser import IPJ_DEF_X4_Parser
from .orientation_parser import Orientation_Parser
from .wkt_manager import Wkt_Manager

class Projection:
    def __init__(self):    
        self.wkt = ""
        self.authority_struc = None
    
    def parse(self, data: bytes):
        offset = self.__get_ipj_initial_offset(data)
        # Parse the header
        header = IPJ_Header_Parser.parse(data[offset:])
        if not self.__validate_header(header):
            raise ValueError("Invalid IPJ header")
        offset += commons.IPJ_HEADER_SIZE

        # Parse IPJ_DEF_X
        def_x = IPJ_DEF_X_Parser.parse(data, offset)
        offset += commons.IPJ_DEF_X_SIZE + commons.IPJ_INNER_HEADER_SIZE

        # Parse IPJ_ORIENT
        orient = Orientation_Parser.parse(data, offset)
        offset += commons.IPJ_ORIENT_SIZE + commons.IPJ_INNER_HEADER_SIZE

        # Parse IPJ_DEF_X2
        # No clear usage of def_x2 for now, let's just comment
        #def_x2 = IPJ_DEF_X2_Parser.parse(data, offset)
        #Lot's of different combination can happen between those two, let jump right before x3
        offset = len(data) - commons.IPJ_DEF_X4_SIZE - commons.IPJ_DEF_X3_SIZE - commons.IPJ_INNER_HEADER_SIZE

        # Parse IPJ_DEF_X3
        def_x3 = IPJ_DEF_X3_Parser.parse(data, offset)
        # Move offset to IPJ_DEF_X4 (after x3 and inner header)
        offset += len(data) - commons.IPJ_DEF_X4_SIZE
        
        # Parse IPJ_DEF_X4
        # No clear usage of def_x4 for now, let's just comment
        # def_x4 = IPJ_DEF_X4_Parser.parse(data, offset)

        self.wkt = Wkt_Manager.get_wkt(def_x, def_x3)
        self.authority_struc = def_x3
    
    def __validate_header(self, header: IPJ_Header) -> bool:
        # Validate the header fields
        if header.lSerialID != -3401216:
            print("Invalid SerialID")
            return False
        if header.lID != 0x49504A20:  # "IPJ " in little-endian
            print(f"Invalid ID (expected 0x49504A20, got 0x{header.lID:08X})")
            return False
        if header.lVersion != 1:
            print(f"Unsupported version (got {header.lVersion})")
            return False
        return True
    
    def __get_ipj_initial_offset(self, data) -> int:        
        # Search for the IPJ signature (0x49504A20 = "IPJ " in little-endian: 20 4a 50 49)
        signature = b'\x20\x4a\x50\x49'
        sig_offset = data.find(signature)
        
        if sig_offset == -1:
            print("IPJ signature not found, trying to parse from offset 0")
            offset = 0
        else:
            # The signature is lID, which is the second field (offset -4 from signature)
            offset = sig_offset - 4
        return offset