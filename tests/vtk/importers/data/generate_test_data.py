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

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk


def _generate_poly_data(z: float = 0.0) -> vtk.vtkPolyData:
    plane = vtk.vtkPlaneSource()
    plane.SetCenter(0, 0, z)
    plane.SetResolution(2, 2)
    plane.Update()
    return plane.GetOutput()


def generate_unsupported() -> None:
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName("unsupported.vtp")
    writer.SetInputData(_generate_poly_data())
    writer.Write()


def generate_all_unsupported() -> None:
    dataset = vtk.vtkMultiBlockDataSet()
    for i in range(2):
        dataset.SetBlock(i, _generate_poly_data(i))

    writer = vtk.vtkXMLMultiBlockDataWriter()
    writer.SetFileName("all_unsupported.vtm")
    writer.SetInputData(dataset)
    writer.Write()


def generate_image_data() -> vtk.vtkImageData:
    image_data = vtk.vtkImageData()
    image_data.SetDimensions(2, 3, 5)
    image_data.SetSpacing(3.4, 2.5, 1.2)
    image_data.SetOrigin(-1.4, 1.2, 2.4)

    point_data = numpy_to_vtk(np.linspace(0, 1, image_data.GetNumberOfPoints()), deep=True)
    point_data.SetName("point_data")
    image_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, image_data.GetNumberOfCells()), deep=True)
    cell_data.SetName("cell_data")
    image_data.GetCellData().AddArray(cell_data)

    writer = vtk.vtkXMLImageDataWriter()
    writer.SetFileName("image_data.vti")
    writer.SetInputData(image_data)
    writer.Write()

    return image_data


def generate_rectilinear_grid() -> vtk.vtkRectilinearGrid:
    vtk_data = vtk.vtkRectilinearGrid()
    vtk_data.SetDimensions(2, 3, 4)
    vtk_data.SetXCoordinates(numpy_to_vtk(np.array([2.4, 3.2]), deep=True))
    vtk_data.SetYCoordinates(numpy_to_vtk(np.array([1.2, 3.3, 5.1]), deep=True))
    vtk_data.SetZCoordinates(numpy_to_vtk(np.array([-1.3, 0.1, 4.9, 5.0]), deep=True))

    point_data = numpy_to_vtk(np.linspace(0, 1, 24), deep=True)
    point_data.SetName("point_data")
    vtk_data.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk(np.linspace(0, 1, 6), deep=True)
    cell_data.SetName("cell_data")
    vtk_data.GetCellData().AddArray(cell_data)

    writer = vtk.vtkXMLRectilinearGridWriter()
    writer.SetFileName("rectilinear_grid.vtr")
    writer.SetInputData(vtk_data)
    writer.Write()

    return vtk_data


def generate_data_with_ghosts() -> None:
    image_data = vtk.vtkImageData()
    image_data.SetDimensions(2, 3, 5)
    image_data.SetSpacing(3.4, 2.5, 1.2)
    image_data.SetOrigin(-1.4, 1.2, 2.4)

    ghost_array = np.zeros(image_data.GetNumberOfCells(), dtype=np.uint8)
    ghost_array[3] = vtk.vtkDataSetAttributes.DUPLICATECELL
    vtk_ghost_array = numpy_to_vtk(ghost_array, deep=True)
    vtk_ghost_array.SetName("vtkGhostType")
    image_data.GetCellData().AddArray(vtk_ghost_array)

    writer = vtk.vtkXMLImageDataWriter()
    writer.SetFileName("image_data_with_ghosts.vti")
    writer.SetInputData(image_data)
    writer.Write()


def generate_unstructured_grid() -> vtk.vtkUnstructuredGrid:
    points = vtk.vtkPoints()
    points.InsertNextPoint(0, 0, 0)
    points.InsertNextPoint(1, 0, 0)
    points.InsertNextPoint(1, 1, 0)
    points.InsertNextPoint(0, 0, 1)
    unstructured_grid = vtk.vtkUnstructuredGrid()
    unstructured_grid.SetPoints(points)

    point_data = numpy_to_vtk(np.linspace(0, 1, 4), deep=True)
    point_data.SetName("point_data")
    unstructured_grid.GetPointData().AddArray(point_data)

    cell_data = numpy_to_vtk([2.1], deep=True)
    cell_data.SetName("cell_data")
    unstructured_grid.GetCellData().AddArray(cell_data)

    unstructured_grid.InsertNextCell(vtk.VTK_TETRA, 4, [0, 1, 2, 3])
    writer = vtk.vtkXMLUnstructuredGridWriter()
    writer.SetFileName("unstructured_grid.vtu")
    writer.SetInputData(unstructured_grid)
    writer.Write()

    return unstructured_grid


def generate_collection(children: dict[str, vtk.vtkDataSet]) -> None:
    collection = vtk.vtkMultiBlockDataSet()
    for i, (key, value) in enumerate(children.items()):
        collection.SetBlock(i, value)
        collection.GetMetaData(i).Set(vtk.vtkCompositeDataSet.NAME(), key)

    writer = vtk.vtkXMLMultiBlockDataWriter()
    writer.SetFileName("collection.vtm")
    writer.SetInputData(collection)
    writer.Write()


if __name__ == "__main__":
    generate_unsupported()
    generate_all_unsupported()
    image_data = generate_image_data()
    rect_grid = generate_rectilinear_grid()
    generate_data_with_ghosts()
    unstructured_grid = generate_unstructured_grid()

    # Generate a collection of some of the generated data
    generate_collection({"image_data": image_data, "rect_grid": rect_grid, "unstructured_grid": unstructured_grid})
