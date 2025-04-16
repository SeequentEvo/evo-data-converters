<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters" /></a>
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

## Data converters

This repository provides the source code for Evo-specific data converters.

When running a converter, data is imported from a supported file format, converted into geoscience objects, and then published to the Seequent Evo API.

The existing data converters can be used without modification or used as a template for your own integration.

## Pre-requisites

* Python >= 3.10, <= 3.12

## Installation

```
pip install evo-data-converters
```

## Usage

The top level sections for the repository are as follows.

- [Samples](samples/README.md) - Jupyter notebook examples for importing data with the existing data converters
- [Data Converters](src/evo/data_converters/README.md) - Source code for the data converters module (`evo.data_converters`)
- Scripts - helper scripts for working with different types of data files
- Tests - unit tests for the data converter module

### Evo authorisation and discovery

Whether using the converters or undertaking development work on the modules themselves, integration with Evo will require that you are granted access as an Evo Partner or Customer, along with access to a specific Evo Workspace. Access is granted via a token. For more information on getting started, see the [Seequent Evo Developer Portal.](https://developer.seequent.com/)

### Using the data converters
See the documentation for each converter for information on how to use the data converters to upload or download geoscience objects from Seequent Evo.

Currently supported converters are:
 * [OMF](/src/evo/data_converters/omf/README.md)
 * [RESQML](/src/evo/data_converters/resqml/README.md)
 * [VTK](/src/evo/data_converters/vtk/README.md)
 * [UBC](/src/evo/data_converters/ubc/README.md)
 * [GOCAD](/src/evo/data_converters/gocad/README.md)

 To use any of the data converters, you will need a few things:
  * An *access token* for your user
  * The *organisation ID*, *hub URL* and *workspace ID* that you would like to import your data to, or export it from.

To get an access token, see [Apps and Tokens](https://developer.seequent.com/docs/guides/getting-started/apps-and-tokens/) in the Seequent Evo Developer portal.

To find the URL of your hub, and the ID of your organisation, see [Evo Discovery.](https://developer.seequent.com/docs/guides/getting-started/discovery/)

For information on accessing and listing Workspaces, see [Workspaces.](https://developer.seequent.com/docs/guides/workspaces/)

There is more information in the [Welcome to Seequent Evo](https://developer.seequent.com/docs/guides/getting-started/) area of the Developer portal, so take a look there or ask questions in the [Community forum.](https://community.seequent.com/categories/evo)

## Contributing

Thank you for your interest in contributing to Seequent software. Please have a look over our [contribution guide.](./CONTRIBUTING.md)

### Using uv

This project uses [uv](https://docs.astral.sh/uv/) to manage all the Python
versions, packages etc.

Run `uv sync --all-extras` to install everything you need.

Then use `uv run <command>` to run commands.

```shell
uv sync --all-extras
uv run pytest tests
```

### evo-sdk-common
The `evo-sdk-common` Python library can be used to log in. An organisation, hub, and workspace can be then be used to publish objects.

```python
from evo.aio import AioTransport
from evo.common import APIConnector, BaseAPIClient
from evo.common.utils import BackoffIncremental
from evo.discovery import DiscoveryAPIClient
from evo.oauth import AuthorizationCodeAuthorizer, OIDCConnector
from evo.workspaces import WorkspaceAPIClient

# Configure the transport.
transport = AioTransport(
    user_agent="evo-client-common-poc",
    max_attempts=3,
    backoff_method=BackoffIncremental(2),
    num_pools=4,
    verify_ssl=True,
)

# Login to the Evo platform.
# User Login
authorizer = AuthorizationCodeAuthorizer(
    redirect_url="<redirect_url>",
    oidc_connector=OIDCConnector(
        transport=transport,
        oidc_issuer="<issuer_url>",
        client_id="<client_id>",
    ),
)
await authorizer.login()

# Select an Organization.
async with APIConnector("https://discover.api.seequent.com", transport, authorizer) as api_connector:
    discovery_client = DiscoveryAPIClient(api_connector)
    organizations = await discovery_client.list_organizations()

selected_org = organizations[0]

# Select a hub and create a connector.
hub_connector = APIConnector(selected_org.hubs[0].url, transport, authorizer)

# Select a Workspace.
async with hub_connector:
    workspace_client = WorkspaceAPIClient(hub_connector, selected_org.id)
    workspaces = await workspace_client.list_workspaces()

workspace = workspaces[0]
workspace_env = workspace.get_environment()

# Interact with a service.
async with hub_connector:
    service_client = BaseAPIClient(workspace_env, hub_connector)
    ...
```

### Developing converters

See [Data converters](/src/evo/data_converters/README.md) for information on how to work on the Evo Data Converters.
This includes both importers and exporters.

We encourage both extending the functionality of the existing converters, or adding new ones for the object formats you would like to see.

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