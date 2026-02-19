import struct
from .geosoft_commons import HEADER_DATA_SIZE
from .header_data import HEADER_DATA

# Size of HEADER_DATA structure in bytes
# 4 int32_t fields (4 bytes each) = 16 bytes

def read_Compressed_header_data(file, offset, isInverted):
    """Read header data from a file object and return a HEADER_DATA object.
    
    Args:
        file: An open binary file object
        offset: Byte offset from the start (if isInverted=False) or end (if isInverted=True)
        isInverted: Boolean indicating if the data format is inverted.
                    If True, reads from the end of the file; if False, from the beginning.
        
    Returns:
        HEADER_DATA: The parsed header data structure
    """
    # Seek to the appropriate position based on isInverted
    if isInverted:
        # Seek from end of file (2 = SEEK_END)
        file.seek(-offset, 2)
    else:
        # Seek from beginning of file (0 = SEEK_SET)
        file.seek(offset, 0)
    
    # Read the header data bytes
    header_data_bytes = file.read(HEADER_DATA_SIZE)
    
    if len(header_data_bytes) < HEADER_DATA_SIZE:
        raise ValueError(f"Insufficient data: expected {HEADER_DATA_SIZE} bytes, got {len(header_data_bytes)}")
    
    # Create the header data object
    header_data = HEADER_DATA()
    
    # Parse the binary data
    # Format: 4 int32 (signature, version, blocks, vectors_per_block)
    # Using little-endian ('<') format
    header_data.signature, header_data.version, header_data.blocks, header_data.vectors_per_block = struct.unpack('<4i', header_data_bytes)
    
    return header_data
