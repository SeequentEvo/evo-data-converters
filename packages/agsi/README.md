<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-agsi/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-agsi" /></a>
    <a href="https://github.com/SeequentEvo/evo-data-converters/actions/workflows/on-merge.yaml"><img src="https://github.com/SeequentEvo/evo-data-converters/actions/workflows/on-merge.yaml/badge.svg" alt="" /></a>
</p>
<p align="center">
    <a href="https://developer.seequent.com/" target="_blank">Seequent Developer Portal</a>
    &bull; <a href="https://community.seequent.com/group/19-evo" target="_blank">Seequent Community</a>
    &bull; <a href="https://seequent.com" target="_blank">Seequent website</a>
</p>

## Evo

Evo is a unified platform for geoscience teams. It enables access, connection, computation, and management of subsurface data. This empowers better decision-making, simplified collaboration, and accelerated innovation. Evo is built on open APIs, allowing developers to build custom integrations and applications. Our open schemas, code examples, and SDK are available for the community to use and extend. 

Evo is powered by Seequent, a Bentley organisation.

## Pre-requisites

* Python virtual environment with Python 3.10, 3.11, or 3.12
* Git

## Installation

`pip install evo-data-converters-agsi`

## agsi converter

Converts [AGSi](https://ags-data-format-wg.gitlab.io/agsi/agsi_standard/latest/) ground models
to and from Evo `geological-sections` objects.

> **Status:** work in progress. This release contains the AGSi **reader** only;
> `convert_agsi` (import) and `export_agsi` (export) still raise `NotImplementedError`.

### Reading AGSi packages

`AgsiPackage.open` accepts:

* a `.agsi` (or `.zip`) archive with `index.json`, the main JSON file and its supporting files;
* a folder holding the extracted contents of such an archive;
* the main JSON file itself or `index.json`. Supporting files are resolved relative to its folder.

```python
from evo.data_converters.agsi.reader import AgsiPackage

package = AgsiPackage.open("Silvertown2D_wkt_1.agsi")
print(package.source_version)  # "0.6"; the document itself is normalised to AGSi 1.0.1

for model in package.models:
    for element in model.agsi_model_element:
        print(element.element_id, element.geometry_object_name)
        for role, geometry in element.geometry_files():  # role: "top", "bottom", ...
            data = package.read_geometry(geometry)
            if data.lines:
                vertices = data.single_line()  # (n, 2) chainage/elevation or (n, 3) x/y/z
            elif data.mesh is not None or data.polygons:
                mesh = data.to_triangle_mesh()  # vertices (n, 3), triangles (m, 3)
```

`read_agsi_file(filepath)` in `evo.data_converters.agsi.importer` returns the same `AgsiPackage`.
I/O problems raise `AGSIDataFileIOError`. Malformed documents raise `AGSIInvalidDataError`.

#### Supported AGSi versions

* **AGSi 1.0.x** is the canonical model (`reader.models`). Pydantic models cover the subset used
  by the converter: `agsSchema`, `agsFile`, `agsProject` (incl. coordinate systems), `agsiModel`,
  `agsiModelElement`, `agsiModelBoundary`, `agsiModelAlignment`, `agsiGeometryFromFile`,
  `agsiGeometryAreaFromLines`, `agsiGeometryVolFromSurfaces`, `agsiGeometryPlane`,
  `agsiGeometryLayer` and `agsiDataParameterValue`. Unknown attributes are kept
  (`model.extra_attributes`, `model.to_agsi()`).
* **AGSi 0.6** documents (e.g. the published Silvertown examples) are normalised to 1.0.1 by
  `reader.adapter`:
  * `agsi*` general objects are renamed;
  * single objects are wrapped in lists;
  * the missing `agsSchema`/`agsFile`/`agsProject` are synthesised.

  The changes made are listed in `package.notes`. These documents carry no coordinate system,
  so the CRS must be supplied when converting.

#### Geometry files

`reader.geometry_files.parse_geometry` returns numpy arrays (`GeometryData`) from:

* **WKT/EWKT**: `LINESTRING`, `POLYGON`, `MULTI*`, `GEOMETRYCOLLECTION` and TINs, 2D or 3D.
  Collections of triangles are returned as an indexed mesh.
* **DXF**: `LINE` chains, `LWPOLYLINE`, `POLYLINE` (incl. polyface meshes), `3DFACE` and `POINT`.
  `filePart` selects a layer.
* **STL**: ASCII and binary.

The reader tolerates quirks found in published examples:

* The declared `fileFormat` is checked against the file content.
* A missing `fileURI` is retried case-insensitively, then with other extensions
  (`.txt`/`.wkt`/`.dxf`/`.stl`).
* Numbers split over two lines in Mathematica's "exponent above" style are repaired.

URIs that point outside the package are rejected.

### Tests

```shell
cd packages/common && uv run test-agsi
```

To also run the integration tests against the published Silvertown examples (not committed; up
to 80 MB), set `AGSI_SAMPLE_DIR` to the folder containing the `Silvertown2D_*.agsi` and
`Silvertown3D_*.agsi` files.


## Code of conduct

We rely on an open, friendly, inclusive environment. To help us ensure this remains possible, please familiarise yourself with our [code of conduct.](https://github.com/SeequentEvo/evo-data-converters/blob/main/CODE_OF_CONDUCT.md)

## License
Evo data converters are open source and licensed under the [Apache 2.0 license.](./LICENSE.md)

Copyright © 2026 Bentley Systems, Incorporated.

Licensed under the Apache License, Version 2.0 (the "License").
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and