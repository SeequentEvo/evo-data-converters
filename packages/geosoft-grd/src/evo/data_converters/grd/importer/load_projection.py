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

import os
from .projection import Projection
import olefile

def load_projection(file_str: str) -> Projection:
    projection = Projection()

    if(not os.path.exists(file_str) or not olefile.isOleFile(file_str)):
        return projection

    # Open the compound file
    ole = olefile.OleFileIO(file_str)
    
    stream_name = 'ipj'
    if ole.exists(stream_name):
        ipj_data = ole.openstream(stream_name).read()
    else:
        return projection
    ole.close()

    try:
        projection.parse(ipj_data)
    except Exception as e:
        print(f"Error parsing projection: {e}")

    return projection