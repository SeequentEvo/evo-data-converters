import struct
from .ipj_header import IPJ_Header


class IPJ_Header_Parser:
    @staticmethod
    def parse(data) -> IPJ_Header:
        header = IPJ_Header()
        
        # Read 12 bytes (3 x int32) from offset 0
        header.lSerialID, header.lID, header.lVersion = struct.unpack_from('<iii', data, 0)
        
        return header
