<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-shp/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-shp" /></a>
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

`pip install evo-data-converters-shp`

## Shapefiles

A shapefile is a set of files which can contain points, lines, and polygons with associated attributes. At minimum, it consists of a main .shp file, an index .shx file, and a dBASE .dbf file.

Refer to this page for more information: https://desktop.arcgis.com/en/arcmap/latest/manage-data/shapefiles/what-is-a-shapefile.htm or view the technical specification here: https://www.esri.com/content/dam/esrisites/sitecore-archive/Files/Pdfs/library/whitepapers/pdfs/shapefile.pdf

### Multipatch Shapefiles
There are multiple shape types which can be used to define a shapefile, though all (non-null) shapes in a given file must be of the same type. Multipatch shapes consist of triangles (defined as 'triangle strips' or 'triangle fans') and rings.

### Implementations

The python [pyshp](https://pypi.org/project/pyshp/) package is used to work with shapefiles.

The SHP converter currently only supports importing multipatch shapefiles which do not contain any rings. These are translated to the triangle-mesh schema and published to an Evo workspace. NULL shapes are discarded.

### Publish geoscience objects from ESRI Shapefile files

[The `evo-sdk-common` Python library](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/common) can be used to sign in. After successfully signing in, the user can select an organisation, an Evo hub, and a workspace. Use [`evo-objects`](https://github.com/SeequentEvo/evo-python-sdk/tree/main/packages/evo-objects) to get an `ObjectAPIClient`, and [`evo-data-converters-shp`](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/shp) to convert your file.

Have a look at the `code-samples/convert-shp.ipynb` notebook for an example of how to publish shapefiles.

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