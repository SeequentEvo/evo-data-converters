from .ipj_def_x2 import IPJ_DEF_X2


class IPJ_DEF_X2_Parser:
    @staticmethod
    def parse(file, offset: int) -> IPJ_DEF_X2:
        obj = IPJ_DEF_X2()
        
        # Read szIPJ2 (64 bytes)
        obj.szIPJ2 = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        return obj
