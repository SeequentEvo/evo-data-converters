# VTK

The Visualization Toolkit (VTK) is open source software for manipulating and displaying scientific data

Refer here for more information: https://vtk.org/

To work with VTK files [the `vtk` Python package](https://pypi.org/project/vtk/) is used, which is a Python wrapper around the underlying `vtk` C++ library.

The VTK converter currently supports importing the following objects into geoscience objects:
- `vtkImageData`/`vtkUniformGrid`/`vtkStructuredPoints`
  - Imported as a `regular-3d-grid` object if there are no blank cells
  - Otherwise, imported as a `regular-masked-3d-grid` object
- `vtkRectilinearGrid`
  - Imported as a `tensor-3d-grid` object
- `vtkUnstructuredGrid`
  - Imported as an `unstructured-tet-grid` object if all cells are tetrahedrons
  - Imported as an `unstructured-hex-grid` object if all cells are hexahedrons
  - Otherwise, imported as an `unstructured-grid` object
