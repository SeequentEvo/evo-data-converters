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

import numpy as np

dDUMMY = 1.0e-32
GRID_HEADER_SIZE = 512
HEADER_DATA_SIZE = 16
GRID_HEADER_SIZE_SIZE = 1024
GS_S4MX = 2147483647
GRIDCOMP_BLOCK_SIZE = 65536
GRID_HEADER_SIGNATURE_32BIT = -119023417
GS_BYTE = 0
GS_USHORT = 1
GS_SHORT = 2
GS_LONG = 3
GS_FLOAT = 4
GS_DOUBLE = 5
GS_UBYTE = 6
GS_ULONG = 7
GS_LONG64 = 8
GS_ULONG64 = 9
GS_FLOAT3D = 10
GS_DOUBLE3D = 11
GS_FLOAT2D = 12
GS_DOUBLE2D = 13
GS_MAXTYPE = 13
GS_MAXTYPESIZE = 24


def get_array(type, size):
    type_map = {
        GS_BYTE: np.int8,
        GS_UBYTE: np.uint8,
        GS_USHORT: np.uint16,
        GS_SHORT: np.int16,
        GS_LONG: np.int32,
        GS_ULONG: np.uint32,
        GS_LONG64: np.int64,
        GS_ULONG64: np.uint64,
        GS_FLOAT: np.float32,
        GS_DOUBLE: np.float64,
    }
    
    if type not in type_map:
        raise ValueError(f"Invalid type code: {type}. Must be one of GS_BYTE to GS_ULONG64")
    
    return np.empty(size, dtype=type_map[type])
