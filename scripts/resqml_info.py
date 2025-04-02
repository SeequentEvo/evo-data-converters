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

from resqpy.grid import Grid
from resqpy.model import ModelContext
from resqpy.organize import FaultInterpretation, TectonicBoundaryFeature
from resqpy.property import AttributePropertySet, Property
from resqpy.surface import Surface

from evo.data_converters.resqml import convert_size, estimate_corner_points_size
from evo.data_converters.resqml.importer._time_series_converter import _load_timestamps

parser = argparse.ArgumentParser(description="Provides a detailed report on the contents of a RESQML file.")
parser.add_argument("filename", help="Path to RESQML file")
parser.add_argument("-a", "--all", action="store_true", help="Show all details")
parser.add_argument("-g", "--grids", action="store_true", help="Show details of grids")
parser.add_argument("-s", "--surfaces", action="store_true", help="Show details of surfaces")
parser.add_argument("-b", "--boundaries", action="store_true", help="Show details of tectonic boundaries")
parser.add_argument("-f", "--faults", action="store_true", help="Show details of fault interpretations")
parser.add_argument("-t", "--time-series", action="store_true", help="Show details of time series")
args = parser.parse_args()


file_name = args.filename
with ModelContext(file_name) as model:
    print("File name", model.epc_file)
    print("   Summary")
    print("   -------")
    summary = model.parts_count_by_type()
    if len(summary):
        for part, count in summary:
            print(f"       {part:<70} {count:>9}")

    if args.grids or args.time_series or args.all:
        print("")
        print("   Grids")
        print("   -----")
        uuids = model.uuids(obj_type="IjkGridRepresentation")
        for uuid in uuids:
            grid = Grid(model, uuid=uuid)
            print(f"       {grid.citation_title:<43} {uuid}")
            cells = (grid.nk or 1) * (grid.nj or 1) * (grid.ni or 1)
            print(f"                       Number of cells: {cells:,}")
            estimate = estimate_corner_points_size(grid)
            print(f"          Estimated corner points size: {convert_size(estimate)}")
            if args.time_series or args.all:
                print("       Time Series")
                print("       -----------")
                related_uuids = model.uuids(related_uuid=uuid, obj_type="PropertySet")
                for uuid in related_uuids:
                    ps = AttributePropertySet(model, property_set_uuid=uuid, support=grid)
                    title = model.title_for_part(model.part_for_uuid(uuid))
                    print(f"       {title} {uuid}")
                    for kind in ps.property_kind_list():
                        ts = set()
                        for p in ps.properties():
                            if p.property_kind != kind:
                                continue
                            ts.add(p.time_series_uuid)
                        print(f"           {kind}")
                        for ts_uuid in ts:
                            root = model.root_for_uuid(ts_uuid)
                            dt = _load_timestamps(root)
                            if dt is not None:
                                dt.sort()
                                print(f"               {dt[0]} to {dt[-1]} {ts_uuid}")

    if args.surfaces or args.all:
        print("")
        print("   Surfaces")
        print("   --------")
        uuids = model.uuids(obj_type="TriangulatedSetRepresentation")
        for uuid in uuids:
            surface = Surface(model, uuid=uuid)
            print(f"       {surface.citation_title:<43} {uuid}")
            triangles, points = surface.triangles_and_points()
            triangles = [] if triangles is None else triangles
            points = [] if points is None else points
            print(f"          triangles: {len(triangles)}, points, {len(points)}")
            np = len(points)
            if not all([t[0] < np and t[1] < np and t[2] < np for t in triangles]):
                print("              WARNING Inconsistent indices, surface can not be imported")
            related_uuids = model.uuids(related_uuid=uuid)
            for r_uuid in related_uuids:
                part = model.part(uuid=r_uuid)
                part_type = model.type_of_part(part)
                indexable = ""
                patches = ""
                values = None
                if part_type is not None:
                    part_type = part_type.removeprefix("obj_")
                    if "Property" in part_type:
                        property = Property(model, r_uuid)
                        indexable = property.indexable_element()
                        try:
                            values = property.array_ref().size  # pyright: ignore
                        except AssertionError:
                            patches = "(multiple patches), property will not be imported"
                part_name = model.title_for_part(part)
                print(f"          {part_name:<43} {part_type}  {indexable} {values or ''} {patches}")

    if args.boundaries or args.all:
        print("")
        print("   Tectonic Boundary Features")
        print("   ---------------------------")
        uuids = model.uuids(obj_type="TectonicBoundaryFeature")
        for uuid in uuids:
            feature = TectonicBoundaryFeature(model, uuid=uuid)
            print(f"       {feature.citation_title:<43} {uuid}")
            related_uuids = model.uuids(related_uuid=uuid)
            for r_uuid in related_uuids:
                part = model.part(uuid=r_uuid)
                part_type = model.type_of_part(part)
                print(r_uuid, part, part_type)

    if args.faults or args.all:
        print("")
        print("   Fault Interpretations")
        print("   ---------------------")
        uuids = model.uuids(obj_type="FaultInterpretation")
        for uuid in uuids:
            feature = FaultInterpretation(model, uuid=uuid)
            print(f"       {feature.citation_title:<43} {uuid}")
            related_uuids = model.uuids(related_uuid=uuid)
            for r_uuid in related_uuids:
                part = model.part(uuid=r_uuid)
                part_type = model.type_of_part(part)
                print(r_uuid, part, part_type)
