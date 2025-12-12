<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
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

## Data converters

This repository provides the source code for Evo-specific data converters.

When running a converter, data is imported from a supported file format, converted into geoscience objects, and then published to the Seequent Evo API.

The existing data converters can be used without modification or used as a template for your own integration.

| Package                                                 | Version                                                                                                                                                        |
|---------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [evo-data-converters-common](packages/common/README.md) | <a href="https://pypi.org/project/evo-data-converters-common/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-common" /></a> |
| [evo-data-converters-ags](packages/ags/README.md)       | <a href="https://pypi.org/project/evo-data-converters-ags/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-ags" /></a>       |
| [evo-data-converters-duf](packages/duf/README.md)       | <a href="https://pypi.org/project/evo-data-converters-duf/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-duf" /></a>       |
| [evo-data-converters-gocad](packages/gocad/README.md)   | <a href="https://pypi.org/project/evo-data-converters-gocad/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-gocad" /></a>   |
| [evo-data-converters-omf](packages/omf/README.md)       | <a href="https://pypi.org/project/evo-data-converters-omf/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-omf" /></a>       |
| [evo-data-converters-resqml](packages/resqml/README.md) | <a href="https://pypi.org/project/evo-data-converters-resqml/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-resqml" /></a> |
| [evo-data-converters-ubc](packages/ubc/README.md)       | <a href="https://pypi.org/project/evo-data-converters-ubc/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-ubc" /></a>       |
| [evo-data-converters-vtk](packages/vtk/README.md)       | <a href="https://pypi.org/project/evo-data-converters-vtk/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-vtk" /></a>       |

## Pre-requisites

* Python 3.10, 3.11, or 3.12

### Evo authorisation and discovery

Whether using the converters or undertaking development work on the modules themselves, integration with Evo will require that you are granted access as an Evo Partner or Customer, along with access to a specific Evo Workspace. Access is granted via a token. For more information on getting started, see the [Seequent Evo Developer Portal.](https://developer.seequent.com/)

### Using the data converters
See the documentation for each converter for information on how to use the data converters to upload or download geoscience objects from Seequent Evo.

For the data converter's common framework package, see [`evo-data-converters-common`](packages/common/README.md).

Currently supported converters are:
 * [AGS](packages/ags/README.md)
 * [DUF](packages/duf/README.md)
 * [GOCAD](packages/gocad/README.md)
 * [OMF](packages/omf/README.md)
 * [RESQML](packages/resqml/README.md)
 * [UBC](packages/ubc/README.md)
 * [VTK](packages/vtk/README.md)

 To use any of the data converters, you will need a few things:
  * An Evo *access token* for your user
  * The Evo *organisation ID*, *hub URL* and *workspace ID* that you would like to import your data to, or export it from.

To get an access token, see [Apps and Tokens](https://developer.seequent.com/docs/guides/getting-started/apps-and-tokens/) in the Seequent Evo Developer portal.

To find the URL of your hub, and the ID of your organisation, see [Evo Discovery.](https://developer.seequent.com/docs/guides/getting-started/discovery/)

For information on accessing and listing Workspaces, see [Workspaces.](https://developer.seequent.com/docs/guides/workspaces/)

There is more information in the [Welcome to Seequent Evo](https://developer.seequent.com/docs/guides/getting-started/) area of the Developer portal, so take a look there or ask questions in the [Community forum.](https://community.seequent.com/group/19-evo)

### Setting up and running Jupyter notebooks

To get up and running with this repository, including all Jupyter notebook examples in it, you will first need to
[install UV.](https://docs.astral.sh/uv/)

Notebooks can be run in your tool of choice (e.g. VS Code). To use Jupyter (the default):

```shell
uv sync --all-packages --all-extras
```

Then in the directory of the notebook(s) you want to run, type:

```shell
uv run jupyter notebook
```

It should open a browser where you can open the notebooks for the current directory.

## Getting started with Evo data converters samples

For examples of how to use Evo data converters, please refer to the samples in each convertor of the `packages` directory.

   * [OMF](packages/omf/samples)
   * [RESQML](packages/resqml/samples)
   * [VTK](packages/vtk/samples)
   * [UBC](packages/ubc/samples)
   * [GOCAD](packages/gocad/samples)
   * [DUF samples](packages/duf/samples)

## Contributing

Thank you for your interest in contributing to Seequent software. Please have a look over our [contribution guide.](./CONTRIBUTING.md)

### Install pre-commit hooks

Once you've installed UV, install pre-commit hooks. These are used to standardise development workflows for all contributors:

```shell
uv run pre-commit install
```

### Developing converters

See [`evo-data-converters-common`'s readme](packages/common/README.md) for information on how to work on the Evo data
converters, including both importers and exporters, and how to extend this library and build your own.

## Code of conduct

We rely on an open, friendly, inclusive environment. To help us ensure this remains possible, please familiarise yourself with our [code of conduct.](./CODE_OF_CONDUCT.md)

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
