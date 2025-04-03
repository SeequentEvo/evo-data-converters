<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://github.com/seequent/evo-open-data-converters/actions/workflows/on-merge.yaml"><img src="https://github.com/seequent/evo-open-data-converters/actions/workflows/on-merge.yaml/badge.svg" alt="" /></a>
</p>
<p align="center">
    <a href="https://developer.seequent.com/" target="_blank">Seequent Developer Portal</a>
    &bull; <a href="https://community.seequent.com/" target="_blank">Seequent Community</a>
    &bull; <a href="https://seequent.com" target="_blank">Seequent website</a>
</p>

## Evo

Evo is a unified platform for geoscience teams. It enables access, connection, computation, and management of subsurface data. This empowers better decision-making, simplified collaboration, and accelerated innovation. Evo is built on open APIs, allowing developers to build custom integrations and applications. Our open schemas, code examples, and SDK are available for the community to use and extend. 

Evo is powered by Seequent, a Bentley organisation.

## Data converters

This repository provides sample code along with the source code for Evo-specific data converters.

When running a converter, data is imported from a supported file format, converted into geoscience objects, and then published to the Seequent Evo API.

The existing data converters can be used as is, or you can use them as a template for your own integration.

## Repository structure

The top level sections for the repository are as follows.

- [Samples](samples/README.md) - Jupyter notebooks and code samples for importing data with the existing data converters
- [Data Converters](src/evo/data_converters/README.md) - Source code for the data converters module (`evo.data_converters`)
- Scripts - helper scripts for working with different types of data files
- Tests - unit tests for the data converter module

### Evo authorisation and discovery

Whether using either the Jupyter samples or undertaking development work on the data converter module itself, integration with Evo will require that you are granted access as an Evo Partner or Customer, along with access to a specific Evo Workspace. Access is granted via a token. For more information on getting started, see the [Seequent Evo Developer Portal](https://developer.seequent.com/).

Refer to the [auth-and-evo-discovery](samples/auth-and-evo-discovery/python/README.md) documentation to learn how to create an Evo access token and how to perform an Evo Discovery request.

## Setting up environment

Whether using the code samples or working on development of the converters the following initial setup instructions apply.

### Requirements

- Python >= 3.10, <= 3.12

### Using uv

This project uses [uv](https://docs.astral.sh/uv/) to manage all the python
versions, packages etc.

Run `uv sync --all-extras` to install everything you need.

Then use `uv run <command>` to run commands.

```shell
uv sync --all-extras
uv run pytest tests
```

### Publishing a new version

On merge to main, there is a workflow to publish the new package to Artifactory. So, if you want to publish a new version of this package, bump the version number in the `pyproject.toml` file, and land your change to main!

If you would like a dev build of the package, one is published on PR to GitHub artifacts where it is available for 90 days.

## Contributing

Thank you for your interest in contributing to Seequent software. Please have a look over our [contribution guide](./CONTRIBUTING.md).

## Code of conduct

We rely on an open, friendly, inclusive environment. To help us ensure this remains possible, please familiarise yourself with our [code of conduct](./CODE_OF_CONDUCT.md).

## License
Evo data converters are open source and licensed under the [Apache 2.0 license](./LICENSE.md).

Copyright © 2025 Bentley Systems, Incorporated.

Licensed under the Apache License, Version 2.0 (the "License").
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.