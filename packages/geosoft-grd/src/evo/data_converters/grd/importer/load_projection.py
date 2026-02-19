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