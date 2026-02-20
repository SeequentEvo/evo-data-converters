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

from .data_reader import DATA_PARSER
from . import geosoft_commons as commons
import numpy as np


class DATA_MANAGER:
    def __init__(self, file, header, element_size, isInverted, type, header_data=None):
        self.file = file

        self.header = header
        self.element_size = element_size
        self.is_inverted = isInverted
        self.type = type

        if header_data is not None:
            self.header_data = header_data
            self.vectorBytes = header.ne * self.element_size
            self.vectorsPerBlock = max(1, commons.GRIDCOMP_BLOCK_SIZE // self.vectorBytes)
            self.blockSize = header_data.vectors_per_block * self.vectorBytes
            self.blockElements = header_data.vectors_per_block * header.ne
            self.numBlocks = (header.nv - 1) // self.vectorsPerBlock + 1

    def __get_data_parser(self):
        return DATA_PARSER(self.file, self.type, self.is_inverted)

    def get_decompressed_data(self):
        data_parser = self.__get_data_parser()
        data_parser.init_decompression_arrays_util(self.blockElements, self.header_data.blocks)
        # Collect all blocks in a list
        blocks = []
        current_block = -1

        for i in range(self.numBlocks):
            current_block += 1
            block_data = data_parser.get_decompressed_data(current_block)
            blocks.append(block_data)

        # Concatenate all blocks into a single 1D array
        array1D = np.concatenate(blocks)

        # Reshape to 2D: Row 0 = [0:vectorsPerBlock], Row 1 = [vectorsPerBlock:2*vectorsPerBlock], etc.
        array2D = array1D.reshape(self.header.nv, self.header.ne)

        # Subtract base from all values of array2D and then multiply by mult
        array2D = (array2D - self.header.base) * self.header.mult

        return array2D

    def get_uncompressed_data(self):
        data_parser = self.__get_data_parser()

        data = data_parser.get_uncompressed_data(self.header.ne * self.header.nv)

        array2D = data.reshape(self.header.nv, self.header.ne)

        # Subtract base from all values of array2D and then multiply by mult
        array2D = (array2D - self.header.base) * self.header.mult
        return array2D
