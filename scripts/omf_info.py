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
from tempfile import NamedTemporaryFile

import omf2

parser = argparse.ArgumentParser(description="Provides a detailed report on the contents of an OMF file.")
parser.add_argument("filename", help="Path to OMF file")
args = parser.parse_args()

omf_file = args.filename

print("Filename", omf_file)

if omf2.detect_omf1(omf_file):
    print("OMF1 format detected, converting to OMF2")

    omf1_converter = omf2.Omf1Converter()

    omf1_file = omf_file
    temporary_file = NamedTemporaryFile(suffix=".omf")
    conversion_problems = omf1_converter.convert(omf1_file, temporary_file.name)
    omf_file = temporary_file.name

    if conversion_problems:
        print("Warnings converting to OMF2")
        for problem in conversion_problems:
            print(problem)

print("Reading file")
reader = omf2.Reader(omf_file)
project, problems = reader.project()

if problems:
    print("Warnings reading OMF2 file:")
    for problem in problems:
        print(problem)

print("project.name:", project.name)

indent = "  "
print(f"{indent}project.author:", project.author)
print(f"{indent}project.description:", project.description)
print(f"{indent}project.application:", project.application)
print(f"{indent}project.coordinate_reference_system:", project.coordinate_reference_system)
print(f"{indent}project.origin:", project.origin)

elements = project.elements()

if len(elements) > 0:
    print("elements:")

element_index = 0
for element in elements:
    indent = "  "

    if element_index > 0:
        print(f"{indent}---")

    print(f"{indent}index:", element_index)
    element_index += 1

    print(f"{indent}name:", element.name)
    print(f"{indent}color:", element.color)
    print(f"{indent}metadata:", element.metadata)

    try:
        geometry = element.geometry()
        print(f"{indent}geometry type:", geometry.__class__.__name__)

        if isinstance(geometry, omf2.PointSet):
            print(f"{indent}vertex count:", geometry.vertices.item_count())

        elif isinstance(geometry, omf2.LineSet):
            print(f"{indent}vertex count:", geometry.vertices.item_count())
            print(f"{indent}segment count:", geometry.segments.item_count())

        elif isinstance(geometry, omf2.Surface):
            print(f"{indent}vertex count:", geometry.vertices.item_count())
            print(f"{indent}triangle count:", geometry.triangles.item_count())

        elif isinstance(geometry, omf2.GridSurface):
            heights = geometry.heights
            if heights:
                print(f"{indent}heights count:", heights.item_count())
            orient2 = geometry.orient
            print(f"{indent}orient u:", orient2.u)
            print(f"{indent}orient v:", orient2.v)
            grid = geometry.grid
            print(f"{indent}grid type:", grid.__class__.__name__)
            if isinstance(grid, omf2.Grid2Regular):
                print(f"{indent}grid size:", grid.size)
            elif isinstance(grid, omf2.Grid2Tensor):
                print(f"{indent}grid u count:", grid.u.item_count())
                print(f"{indent}grid v count:", grid.v.item_count())
            print(f"{indent}grid count:", grid.count())
            print(f"{indent}grid flat count:", grid.flat_count())
            print(f"{indent}grid flat corner count:", grid.flat_corner_count())

        elif isinstance(geometry, omf2.BlockModel):
            orient3 = geometry.orient
            print(f"{indent}orient u:", orient3.u)
            print(f"{indent}orient v:", orient3.v)
            print(f"{indent}orient w:", orient3.w)
            grid = geometry.grid
            print(f"{indent}grid type:", grid.__class__.__name__)
            if isinstance(grid, omf2.Grid3Regular):
                print(f"{indent}grid size:", grid.size)
            elif isinstance(grid, omf2.Grid3Tensor):
                print(f"{indent}grid u count:", grid.u.item_count())
                print(f"{indent}grid v count:", grid.v.item_count())
                print(f"{indent}grid w count:", grid.w.item_count())
            print(f"{indent}grid count:", grid.count())
            print(f"{indent}grid flat count:", grid.flat_count())
            print(f"{indent}grid flat corner count:", grid.flat_corner_count())

            subblocks = geometry.subblocks
            if subblocks:
                print(f"{indent}subblocks type:", subblocks.__class__.__name__)
                if isinstance(subblocks, omf2.RegularSubblocks):
                    print(f"{indent}subblocks mode:", subblocks.mode)
                    print(f"{indent}subblocks count:", subblocks.count)
                print(f"{indent}subblocks item count:", subblocks.subblocks.item_count())

    except omf2.OmfNotSupportedException:
        print(f"{indent}geometry type: unsupported")

    attributes = element.attributes()

    if len(attributes) > 0:
        print(f"{indent}attributes:")

    attribute_index = 0
    for attribute in attributes:
        indent = "    "

        if attribute_index > 0:
            print(f"{indent}---")

        print(f"{indent}index:", attribute_index)
        attribute_index += 1

        print(f"{indent}name:", attribute.name)
        print(f"{indent}description:", attribute.description)
        print(f"{indent}units:", attribute.units)
        print(f"{indent}metadata:", attribute.metadata)
        print(f"{indent}location:", attribute.location)

        data = attribute.get_data()
        print(f"{indent}data type:", data.__class__.__name__)

        if hasattr(data, "colormap"):
            print(f"{indent}colormap type:", data.colormap.__class__.__name__)
            indent = "      "
            if isinstance(data.colormap, omf2.NumberColormapContinuous):
                print(f"{indent}gradient:", reader.array_gradient(data.colormap.gradient))
                print(f"{indent}range:", data.colormap.range())
            elif isinstance(data.colormap, omf2.NumberColormapDiscrete):
                print(f"{indent}gradient:", reader.array_gradient(data.colormap.gradient))
                print(f"{indent}boundaries:", reader.array_boundaries(data.colormap.boundaries))

        indent = "    "
        if hasattr(data, "values"):
            values = data.values
            print(f"{indent}value item count:", values.item_count())
