from enum import Enum
from . import geosoft_commons as commons
from .dat_grid_header_loader import read_from_file
from .header_data_loader import read_Compressed_header_data
from .data_manager import DATA_MANAGER

class File_Mode(Enum):
    ReadOnly = 1
    ReadWrite = 2

class Compression_Type(Enum):
   BF_COMPRESS_DEFAULT = -1,    #-1: Use default setting
   BF_COMPRESS_NONE = 0,        # 0: None
   BF_COMPRESS_SIMPLE = 1,      # 1: "Simple" compression (very fast)
   BF_COMPRESS_ZIP_LOW = 2,     # 2: ZIP low compression (fast)
   BF_COMPRESS_ZIP_MEDIUM = 3,  # 3: ZIP medium compression (medium)
   BF_COMPRESS_ZIP_HIGH = 4     # 4: ZIP high compression (slow)


class Img:
    def __init__(self, file):
        #!!! ---- Header Import ---- !!!#
        (header, isInverted) = read_from_file(file)

        self.is_inverted = isInverted
        self.__set_dimensions(header)

        self.kx = header.kx
        self.rotation = header.rot
        self.x_origin = header.xo
        self.y_origin = header.yo

        self.compression = Compression_Type.BF_COMPRESS_NONE
        if (header.size & 0x400):
            self.compression = Compression_Type.BF_COMPRESS_SIMPLE
            header.size &= ~0x400

        # Determine type based on size and sign
        self.__set_type(header.size, header.sign)
        self.__set_element_size();

        if (header.mult == 0):
            header.mult = 1.0
        if (header.mult < 0):
            header.mult = header.mult * -1.0

        if (header.sign == 3):
            self.fColor = True
            self.type = 3  # Force to signed 4-byte
            self.base = 0.0
            self.mult = 1.0

        if(header.ne * header.nv > commons.GS_S4MX):
            raise ValueError("Invalid grid size: number of elements exceeds maximum allowed")
        if(header.ne == 0 or header.nv == 0):
            raise ValueError("Empty grid file: number of elements cannot be zero")

        self.__set_stats(header)

        #!!! End of Header Import !!!#

        #!!! --- Read the Data --- !!!#
        if (self.compression != Compression_Type.BF_COMPRESS_NONE):
            data_header = read_Compressed_header_data(file, commons.GRID_HEADER_SIZE, isInverted)
            if(not self.__validate_compressed_data_header(data_header, header)):
                raise ValueError("Invalid data header parameters")
            
            data_manager = DATA_MANAGER(file, header, self.element_size, isInverted, self.type, data_header)
            self.data = data_manager.get_decompressed_data()   
        else:
            data_manager = DATA_MANAGER(file, header, self.element_size, isInverted, self.type)
            self.data = data_manager.get_uncompressed_data()   


    def __validate_compressed_data_header(self, data_header, header):
        isSignValid = data_header.signature == commons.GRID_HEADER_SIGNATURE_32BIT
        isVersionCorrect = data_header.version == 1 or data_header.version == 2
        isSizeCorrect = data_header.blocks * data_header.vectors_per_block >= header.nv
        return isSignValid and isVersionCorrect and isSizeCorrect

    def __set_dimensions(self, header):
        if(header.kx == 1):
            self.dx = header.de
            self.dy = header.dv
            self.nx = header.ne
            self.ny = header.nv
        else:
            self.dx = header.dv
            self.dy = header.de
            self.nx = header.nv
            self.ny = header.ne
        
    def __set_type(self, size, sign):
        if size == 1:
            self.type = commons.GS_BYTE  # Unsigned 8-bit
        elif size == 2:
            self.type = commons.GS_USHORT if sign == 0 else commons.GS_SHORT  # Unsigned or Signed 16-bit
        elif size == 4:
            self.type = commons.GS_FLOAT if sign == 2 else commons.GS_LONG  # Float or Signed 32-bit
        elif size == 8:
            self.type = commons.GS_DOUBLE  # Double 64-bit
        else:
            raise ValueError(f"Invalid size/sign combination: size={size}, sign={sign}")
        
    def __set_stats(self, header):
        if(header.nvpts >= 0 and (header.nvpts < (header.ne * header.nv))):
            self.has_valid_points = True
            self.items = header.nvpts
            self.var = header.var / header.mult / header.mult

            if (self.type == commons.GS_DOUBLE):
                self.min = commons.dDUMMY
                self.max = commons.dDUMMY
                self.mean = commons.dDUMMY
            else:
                self.min = header.stats[0]
                self.min = self.min if self.min == commons.dDUMMY else self.min / header.mult

                self.max = header.stats[1]
                self.max = self.max if self.max == commons.dDUMMY else self.max / header.mult

                self.mean = header.stats[2]
                self.mean = self.mean if self.mean == commons.dDUMMY else self.mean / header.mult
        
        if(header.user[0] != commons.dDUMMY):
            self.trend0 = header.user[0]
        if(header.user[1] != commons.dDUMMY):
            self.trend1 = header.user[1]
        if(header.user[2] != commons.dDUMMY):
            self.trend2 = header.user[2]
        if(header.user[3] != commons.dDUMMY):
            self.num_tr_coef = header.user[3]
 
    def __set_element_size(self):
        if self.type == commons.GS_BYTE or self.type == commons.GS_UBYTE:
            self.element_size = 1
        elif self.type == commons.GS_SHORT or self.type == commons.GS_USHORT:
            self.element_size = 2
        elif self.type == commons.GS_LONG or self.type == commons.GS_ULONG or self.type == commons.GS_FLOAT:
            self.element_size = 4
        elif self.type == commons.GS_DOUBLE:
            self.element_size = 8
        elif self.type == commons.GS_LONG64 or self.type == commons.GS_ULONG64 or self.type == commons.GS_FLOAT2D:
            self.element_size = 8
        elif self.type == commons.GS_FLOAT3D:
            self.element_size = 12
        elif self.type == commons.GS_DOUBLE2D:
            self.element_size = 16
        elif self.type == commons.GS_DOUBLE3D:
            self.element_size = 24
        else:
            raise ValueError(f"Unsupported data type: {self.type}")