from .img import Img

def load_grid(file_path: str) -> Img:
    """
    Load a grid file and return an Img object.
    
    Args:
        file_path: Path to the grid file to load
        
    Returns:
        Img: An Img object containing the loaded grid data
    """
    with open(file_path, 'rb', buffering=0) as file:
        img = Img(file)
        return img