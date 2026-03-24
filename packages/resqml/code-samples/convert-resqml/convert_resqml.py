#!/usr/bin/env python

#  Copyright © 2025 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import argparse
import uuid

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.resqml.importer import RESQMLConversionOptions, convert_resqml

parser = argparse.ArgumentParser(description="Convert a RESQML file and print the generated Evo objects")
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

options = RESQMLConversionOptions(active_cells_only=not args.all_grid_cells)

for file_name in file_names:
    objects = convert_resqml(file_name, args.epsg_code, meta_data, None, options=options)
    for o in objects:
        print(o.json_dumps(indent=4))
