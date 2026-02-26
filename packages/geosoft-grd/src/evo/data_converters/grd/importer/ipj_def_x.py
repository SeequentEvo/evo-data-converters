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

from .ipj_units_x import IPJ_UNITS_X


class IPJ_DEF_X:
    def __init__(self):
        self.szIPJ = ""
        self.lProjType = 0
        self.lOrder = 0
        self.lWarp = 0
        self.szDatum = ""
        self.szEllipsoid = ""
        self.dRadius = 0.0
        self.dEccentricity = 0.0
        self.dPrimeMeridian = 0.0
        self.szDatumTrf = ""
        self.dDx = 0.0
        self.dDy = 0.0
        self.dDz = 0.0
        self.dRx = 0.0
        self.dRy = 0.0
        self.dRz = 0.0
        self.dScaleAdjust = 0.0
        self.Units = IPJ_UNITS_X()
        self.szProj = ""
        # Replace 8 individual double attributes with an array of 8 doubles
        self.proj_params = [0.0] * 8
