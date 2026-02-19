import struct
from .ipj_def_x import IPJ_DEF_X


class IPJ_DEF_X_Parser:
    @staticmethod
    def parse(file, offset: int) -> IPJ_DEF_X:
        obj = IPJ_DEF_X()
        
        # Read szIPJ (64 bytes)
        obj.szIPJ = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        # Read lProjType, lOrder, lWarp (3 x int32)
        obj.lProjType, obj.lOrder, obj.lWarp = struct.unpack_from('<iii', file, offset)
        offset += 12
        
        # Read szDatum (64 bytes)
        obj.szDatum = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        # Read szEllipsoid (64 bytes)
        obj.szEllipsoid = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        # Read dRadius, dEccentricity, dPrimeMeridian (3 x double)
        obj.dRadius, obj.dEccentricity, obj.dPrimeMeridian = struct.unpack_from('<ddd', file, offset)
        offset += 24
        
        # Read szDatumTrf (64 bytes)
        obj.szDatumTrf = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        # Read dDx, dDy, dDz, dRx, dRy, dRz, dScaleAdjust (7 x double)
        obj.dDx, obj.dDy, obj.dDz, obj.dRx, obj.dRy, obj.dRz, obj.dScaleAdjust = struct.unpack_from('<ddddddd', file, offset)
        offset += 56
        
        # Read Units.szID (64 bytes)
        obj.Units.szID = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        # Read Units.dScale (double)
        obj.Units.dScale = struct.unpack_from('<d', file, offset)[0]
        offset += 8
        
        # Read szProj (64 bytes)
        obj.szProj = file[offset:offset+64].decode('ascii', errors='ignore').rstrip('\x00')
        offset += 64
        
        # Read projection parameters (8 x double) into proj_params array
        obj.proj_params = list(struct.unpack_from('<dddddddd', file, offset))
        offset += 64
        return obj
