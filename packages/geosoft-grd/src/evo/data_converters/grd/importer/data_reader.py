import numpy as np
import zlib
from . import geosoft_commons as commons

class DATA_PARSER:
    def __init__(self, file, type, isInverted): 
        self.file = file
        self.data_type = type
        self.is_inverted = isInverted

    def init_decompression_arrays_util(self, blockElements, data_header_blocks):
        self.block_elements = blockElements

        offset = commons.GRID_HEADER_SIZE + commons.HEADER_DATA_SIZE

        self.offset_array = self.__get_array(self.file, offset, data_header_blocks, commons.GS_LONG64, self.is_inverted)

        offset += data_header_blocks * 8
        offset = self._align_to_16(offset)
        
        self.size_array = self.__get_array(self.file, offset, data_header_blocks, commons.GS_LONG, self.is_inverted)

    def get_decompressed_data(self, current_block):
        compressed_size = int(self.size_array[current_block])
        compressed_offset = int(self.offset_array[current_block])

        return self.__get_compressed_array(
            self.file, compressed_offset, compressed_size, self.block_elements, self.data_type, self.is_inverted
        )
    
    def get_uncompressed_data(self, number_elements):
        return self.__get_array(self.file, commons.GRID_HEADER_SIZE, number_elements, self.data_type, self.is_inverted)

    def _align_to_16(self, offset):
        """Align offset to next 16-byte boundary to match alignas(16)"""
        return ((offset + 15) // 16) * 16

    def __get_array_type(self, GS_Type):
        type_map = {
            commons.GS_BYTE: np.int8,
            commons.GS_UBYTE: np.uint8,
            commons.GS_USHORT: np.uint16, 
            commons.GS_SHORT: np.int16,
            commons.GS_LONG: np.int32,
            commons.GS_ULONG: np.uint32,
            commons.GS_LONG64: np.int64,
            commons.GS_ULONG64: np.uint64,
            commons.GS_FLOAT: np.float32,
            commons.GS_DOUBLE: np.float64,
        }
        if GS_Type not in type_map:
            raise ValueError(f"Invalid GS_Type: {GS_Type}")
        return type_map[GS_Type]

    def __get_array(self, file, offset, numberOfElements, GS_Type, isInverted):
        array = commons.get_array(GS_Type, numberOfElements)
    
        # Seek to the appropriate position based on isInverted
        if isInverted:
            file.seek(-offset, 2)
        else:
            file.seek(offset, 0)
    
        # Read data in 4096-byte chunks to match external application
        dtype = self.__get_array_type(GS_Type)
        element_size = np.dtype(dtype).itemsize
        total_bytes = numberOfElements * element_size
        
        chunks = []
        bytes_remaining = total_bytes
        
        while bytes_remaining > 0:
            chunk_size = min(4096, bytes_remaining)
            chunk_data = file.read(chunk_size)
            
            if len(chunk_data) < chunk_size:
                raise ValueError(f"Insufficient data: expected {total_bytes} bytes, got {total_bytes - bytes_remaining + len(chunk_data)}")
            
            chunks.append(chunk_data)
            bytes_remaining -= chunk_size
        
        # Combine all chunks and convert to numpy array
        all_bytes = b''.join(chunks)
        data = np.frombuffer(all_bytes, dtype=dtype, count=numberOfElements)
    
        array[:] = data
    
        return array

    def __get_compressed_array(self, file, offset, compressed_size, numberOfElements, GS_Type, isInverted):
        """Read and decompress zlib-compressed data with 16-byte header."""
        
        dtype = self.__get_array_type(GS_Type)
        element_size = np.dtype(dtype).itemsize
        expected_bytes = numberOfElements * element_size
    
        # Check if data might be uncompressed (compressed_size == expected_bytes)
        if compressed_size == expected_bytes:
            # Data is not compressed
            if isInverted:
                file.seek(-offset, 2)
            else:
                file.seek(offset, 0)
            
            data_bytes = file.read(compressed_size)
            if len(data_bytes) != compressed_size:
                raise ValueError(f"Insufficient data: expected {compressed_size} bytes, got {len(data_bytes)}")
            
            array = commons.get_array(GS_Type, numberOfElements)
            data = np.frombuffer(data_bytes, dtype=dtype, count=numberOfElements)
            array[:] = data
            return array
    
        # Skip 16-byte custom header and seek to zlib-compressed data
        header_size = 16
        if isInverted:
            file.seek(-(offset + header_size), 2)
        else:
            file.seek(offset + header_size, 0)
        
        # Create zlib streaming decompressor
        decompressor = zlib.decompressobj(zlib.MAX_WBITS)
        decompressed_chunks = []
        
        # Read and decompress in chunks (matching C code pattern)
        actual_compressed_size = compressed_size - header_size
        bytes_remaining = actual_compressed_size
        
        while bytes_remaining > 0:
            chunk_size = min(32767, bytes_remaining)
            compressed_chunk = file.read(chunk_size)
            
            # if len(compressed_chunk) < chunk_size:
            #     raise ValueError(f"Insufficient compressed data: expected {chunk_size} bytes, got {len(compressed_chunk)}")
            
            # Decompress this chunk
            decompressed_chunk = decompressor.decompress(compressed_chunk)
            if decompressed_chunk:
                decompressed_chunks.append(decompressed_chunk)
            
            bytes_remaining -= chunk_size
        
        # Finish decompression (flush any remaining data)
        final_chunk = decompressor.flush()
        if final_chunk:
            decompressed_chunks.append(final_chunk)
        
        # Combine all decompressed chunks
        decompressed_data = b''.join(decompressed_chunks)

        # Calculate actual number of elements available (avoid reading past buffer)
        actual_elements = min(numberOfElements, len(decompressed_data) // element_size)
        data = np.frombuffer(decompressed_data, dtype=dtype, count=actual_elements)
        array = commons.get_array(GS_Type, actual_elements)
        array[:actual_elements] = data
    
        return array