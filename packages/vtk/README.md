<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-vtk/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-vtk" /></a>
    <a href="https://github.com/SeequentEvo/evo-data-converters/actions/workflows/on-merge.yaml"><img src="https://github.com/SeequentEvo/evo-data-converters/actions/workflows/on-merge.yaml/badge.svg" alt="" /></a>
</p>
<p align="center">
    <a href="https://developer.seequent.com/" target="_blank">Seequent Developer Portal</a>
    &bull; <a href="https://community.seequent.com/" target="_blank">Seequent Community</a>
    &bull; <a href="https://seequent.com" target="_blank">Seequent website</a>
</p>

## Evo

Evo is a unified platform for geoscience teams. It enables access, connection, computation, and management of subsurface data. This empowers better decision-making, simplified collaboration, and accelerated innovation. Evo is built on open APIs, allowing developers to build custom integrations and applications. Our open schemas, code examples, and SDK are available for the community to use and extend. 

Evo is powered by Seequent, a Bentley organisation.

## Pre-requisites

* Python 3.10, 3.11, or 3.12

## Installation

```
pip install evo-data-converters-vtk
```

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


## Code of conduct

We rely on an open, friendly, inclusive environment. To help us ensure this remains possible, please familiarise yourself with our [code of conduct.](https://github.com/SeequentEvo/evo-data-converters/blob/main/CODE_OF_CONDUCT.md)

## License
Evo data converters are open source and licensed under the [Apache 2.0 license.](./LICENSE.md)

Copyright © 2025 Bentley Systems, Incorporated.

Licensed under the Apache License, Version 2.0 (the "License").
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
