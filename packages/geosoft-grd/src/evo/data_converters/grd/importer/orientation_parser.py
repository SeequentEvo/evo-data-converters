import struct
from .orientation import Orientation


class Orientation_Parser:
    @staticmethod
    def parse(file, offset: int) -> Orientation:
        obj = Orientation()
        
        # Read eType (int32)
        obj.eType = struct.unpack_from('<i', file, offset)[0]
        offset += 4
        
        # Read dXo, dYo, dZo (3 x double)
        obj.dXo, obj.dYo, obj.dZo = struct.unpack_from('<ddd', file, offset)
        offset += 24
        
        # Read pdParms (8 x double)
        obj.pdParms = list(struct.unpack_from('<dddddddd', file, offset))
        offset += 64
        
        return obj
