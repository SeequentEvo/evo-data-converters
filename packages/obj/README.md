<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-obj/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-obj" /></a>
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

`pip install evo-data-converters-obj`

## OBJ

The OBJ 3D mesh format is a legacy of Wavefront Technologies, but is now a common format for specifying polygon meshes,
optionally with texture data (stored in a separate MTL file).

### Implementations

The Python [Trimesh](https://trimesh.org/index.html) package is used to work with OBJ files by default, for import and export. There is a second importer implementation that uses [TinyOBJ](https://github.com/tinyobjloader/tinyobjloader). To use TinyOBJ, the `--extra optional_parsers` dependencies need to be installed then pass "tinyobj" as the `implementation` string to `convert_obj()`. First you will have to uncomment the tinyobjloader lines from pyproject.toml. TinyOBJ might be more suitable for larger meshes.

### Publish geoscience objects from an OBJ file

[The `evo-sdk-common` Python library](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/common) can be used to sign in. After successfully signing in, the user can select an organisation, an Evo hub, and a workspace. Use [`evo-objects`](https://github.com/SeequentEvo/evo-python-sdk/tree/main/packages/evo-objects) to get an `ObjectAPIClient`, and [`evo-data-converters-common`](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/common) to convert your file.

Have a look at the `samples/publish-obj.ipynb` Notebook for an example of how to publish an OBJ (and related) files.

Also see the `samples/publish-obj-script.py` example of using `convert_obj()` inside a python script.

### Exporting Triangle Mesh objects to OBJ

To export Triangle Mesh objects from Evo to an OBJ file, call `await export_obj()` supplying an output file path and a list of `EvoObjectMetadata` containing the UUIDs of the Evo objects.

`EvoObjectMetadata` can also specify the version of each object to export. If not specified, so it will export the latest version.

See documentation on the `ObjectAPIClient` for listing objects and getting their IDs and versions.

You will need the same selection of organisation, Evo hub, and workspace that is needed for importing objects.

See the `samples/export-obj.ipynb` Notebook for an example of how to download a Evo Geoscience object to an OBJ.

Also see the `samples/export-obj-script.py` example of using `export_obj()` inside a python script.

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
