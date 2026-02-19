import struct
from .ipj_def_x3 import IPJ_DEF_X3


class IPJ_DEF_X3_Parser:
    @staticmethod
    def parse(file, offset: int) -> IPJ_DEF_X3:
        obj = IPJ_DEF_X3()
        
        # Read szAuthority (64 bytes)
        obj.szAuthority = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        # Read lAuthoritativeID, lSafeProjType (2 x int32)
        obj.lAuthoritativeID, obj.lSafeProjType = struct.unpack_from('<ii', file, offset)
        offset += 8
        
        return obj
