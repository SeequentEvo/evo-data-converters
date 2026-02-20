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

class DAT_GRID_HEADER:
    def __init__(self):
        # Element size in bytes: 1, 2, 4 or 8
        self.size = 0
        
        # Sign: 0 unsigned, 1 signed, 2 real, 3 color (4-byte only)
        self.sign = 0
        
        # Number of elements/vector
        self.ne = 0
        
        # Number of vectors
        self.nv = 0
        
        # Sense: +/-1 first point at lower left
        #        +/-2 first point at upper left
        #        +/-3 first point at upper right
        #        +/-4 first point at lower right
        #        + for right handed, - for left handed
        self.kx = 0
        
        # Element separation
        self.de = 0.0
        
        # Vector separation
        self.dv = 0.0
        
        # Lower left X location
        self.xo = 0.0
        
        # Lower left Y location
        self.yo = 0.0
        
        # Rotation angle
        self.rot = 0.0
        
        # Base removed
        self.base = 0.0
        
        # Multiplied by
        self.mult = 0.0
        
        # Grid label (48 bytes)
        self.label = bytearray(48)
        
        # Map number (16 bytes)
        self.mapno = bytearray(16)
        
        # Projection type
        self.proj = 0
        
        # Unit types (3 integers)
        self.units = [0, 0, 0]
        
        # Number of valid points in image
        self.nvpts = 0
        
        # Statistics (4 floats)
        self.stats = [0.0, 0.0, 0.0, 0.0]
        
        # Variance of grid
        self.var = 0.0
        
        # Process flag
        self.process = 0
        
        # User Data (81 floats)
        self.user = [0.0] * 81

