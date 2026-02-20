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
from .ipj_def_x import IPJ_DEF_X


class IPJ_DEF_X_Parser:
    @staticmethod
    def parse(file, offset: int) -> IPJ_DEF_X:
        obj = IPJ_DEF_X()

        # Read szIPJ (64 bytes)
        obj.szIPJ = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        # Read lProjType, lOrder, lWarp (3 x int32)
        obj.lProjType, obj.lOrder, obj.lWarp = struct.unpack_from("<iii", file, offset)
        offset += 12

        # Read szDatum (64 bytes)
        obj.szDatum = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        # Read szEllipsoid (64 bytes)
        obj.szEllipsoid = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        # Read dRadius, dEccentricity, dPrimeMeridian (3 x double)
        obj.dRadius, obj.dEccentricity, obj.dPrimeMeridian = struct.unpack_from("<ddd", file, offset)
        offset += 24

        # Read szDatumTrf (64 bytes)
        obj.szDatumTrf = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        # Read dDx, dDy, dDz, dRx, dRy, dRz, dScaleAdjust (7 x double)
        obj.dDx, obj.dDy, obj.dDz, obj.dRx, obj.dRy, obj.dRz, obj.dScaleAdjust = struct.unpack_from(
            "<ddddddd", file, offset
        )
        offset += 56

        # Read Units.szID (64 bytes)
        obj.Units.szID = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        # Read Units.dScale (double)
        obj.Units.dScale = struct.unpack_from("<d", file, offset)[0]
        offset += 8

        # Read szProj (64 bytes)
        obj.szProj = file[offset : offset + 64].decode("ascii", errors="ignore").rstrip("\x00")
        offset += 64

        # Read projection parameters (8 x double) into proj_params array
        obj.proj_params = list(struct.unpack_from("<dddddddd", file, offset))
        offset += 64
        return obj
