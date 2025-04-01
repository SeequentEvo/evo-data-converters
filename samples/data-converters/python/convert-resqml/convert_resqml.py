#!/usr/bin/env python
import argparse
import uuid

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.resqml.importer import ResqmlConversionOptions, convert_resqml

parser = argparse.ArgumentParser(description="Convert a RESQML file and print the generated EVO objects")
parser.add_argument("filename", help="Path to RESQML file", nargs="+")
parser.add_argument(
    "--epsg-code",
    help="EPSG code to use for the Coordinate Reference System. If not provided in the RESQML file",
    required=True,
    type=int,
)
parser.add_argument(
    "--all-grid-cells",
    action="store_true",
    help="Convert all grid cells rather than just the active cells",
)
args = parser.parse_args()

file_names = args.filename
meta_data = EvoWorkspaceMetadata(workspace_id=str(uuid.uuid4()))

options = ResqmlConversionOptions(active_cells_only=not args.all_grid_cells)

for file_name in file_names:
    objects = convert_resqml(file_name, args.epsg_code, meta_data, None, options=options)
    for o in objects:
        print(o.json_dumps(indent=4))
