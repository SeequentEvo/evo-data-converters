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
