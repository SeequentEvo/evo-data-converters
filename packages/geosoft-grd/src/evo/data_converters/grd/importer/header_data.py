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


class HEADER_DATA:
    """Geosoft version 2 header structure.

    Based on the C struct with the following fields:
    - signature: Signature (int32)
    - version: Version of compression (int32)
    - blocks: Number of Data Blocks (int32)
    - vectors_per_block: Number of vectors per block (int32)
    """

    def __init__(self):
        self.signature = 0  # int32_t - Signature
        self.version = 0  # int32_t - Version of compression
        self.blocks = 0  # int32_t - Number of Data Blocks
        self.vectors_per_block = 0  # int32_t - Number of vectors per block
