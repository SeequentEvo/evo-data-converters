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

import struct
from . import geosoft_commons as commons
from .dat_grid_header import DAT_GRID_HEADER

def __parse_header(header_bytes):
    """Parse header bytes and return a DAT_GRID_HEADER object"""
    header = DAT_GRID_HEADER()
    offset = 0
    
    # 5 int32_t fields
    header.size, header.sign, header.ne, header.nv, header.kx = struct.unpack_from('<5i', header_bytes, offset)
    offset += 20
    
    # 7 double fields
    header.de, header.dv, header.xo, header.yo, header.rot, header.base, header.mult = struct.unpack_from('<7d', header_bytes, offset)
    offset += 56
    
    # label (48 bytes)
    header.label = bytearray(struct.unpack_from('48b', header_bytes, offset))
    offset += 48
    
    # mapno (16 bytes)
    header.mapno = bytearray(struct.unpack_from('16b', header_bytes, offset))
    offset += 16
    
    # proj (1 int32_t)
    header.proj = struct.unpack_from('<i', header_bytes, offset)[0]
    offset += 4
    
    # units (3 int32_t)
    header.units = list(struct.unpack_from('<3i', header_bytes, offset))
    offset += 12
    
    # nvpts (1 int32_t)
    header.nvpts = struct.unpack_from('<i', header_bytes, offset)[0]
    offset += 4
    
    # stats (4 floats)
    header.stats = list(struct.unpack_from('<4f', header_bytes, offset))
    offset += 16
    
    # var (1 double)
    header.var = struct.unpack_from('<d', header_bytes, offset)[0]
    offset += 8
    
    # process (1 int32_t)
    header.process = struct.unpack_from('<i', header_bytes, offset)[0]
    offset += 4
    
    # user (81 floats)
    header.user = list(struct.unpack_from('<81f', header_bytes, offset))
    
    return header

def read_from_file(file):
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    
    if file_size < commons.GRID_HEADER_SIZE:
        raise ValueError(f"File too small: expected at least {commons.GRID_HEADER_SIZE} bytes, got {file_size}")
    
    # Try reading from the beginning (normal format)
    file.seek(0)
    header_bytes = file.read(commons.GRID_HEADER_SIZE)
    
    # Check the size field (first int32) to determine if order is correct
    size = struct.unpack_from('<i', header_bytes, 0)[0]
    
    # Try parsing from beginning (normal format)
    try:
        header = __parse_header(header_bytes)
        if __validate_header(header):
            return (header, False)
    except Exception:
        pass  # Will try inverted format below
    
    # Try inverted format - header at end
    try:
        file.seek(file_size - commons.GRID_HEADER_SIZE)
        header_bytes = file.read(commons.GRID_HEADER_SIZE)
        header = __parse_header(header_bytes)
        if __validate_header(header):
            return (header, True)
    except Exception:
        pass
    
    # Both attempts failed
    raise ValueError("Failed to parse and validate header from both normal and inverted formats")
    
def __validate_header(header):
    return ((header.kx == 1 or header.kx == -1) and header.ne > 0 and header.nv > 0 and header.de > 0 and header.dv > 0)