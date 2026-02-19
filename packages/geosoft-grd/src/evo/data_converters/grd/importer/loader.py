from .grid_to_json_parser import GRID_PARSER

def generate_evo_files(grid_path: str) -> None:
    """Generate EVO files from a grid path."""
    grid_parser = GRID_PARSER(grid_path)
    grid_parser.parse_grid()
