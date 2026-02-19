class HEADER_DATA:
    """Geosoft version 2 header structure.
    
    Based on the C struct with the following fields:
    - signature: Signature (int32)
    - version: Version of compression (int32)
    - blocks: Number of Data Blocks (int32)
    - vectors_per_block: Number of vectors per block (int32)
    """
    
    def __init__(self):
        self.signature = 0        # int32_t - Signature
        self.version = 0          # int32_t - Version of compression
        self.blocks = 0           # int32_t - Number of Data Blocks
        self.vectors_per_block = 0  # int32_t - Number of vectors per block
