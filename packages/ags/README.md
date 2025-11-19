<p align="center">
    <a href="https://seequent.com" target="_blank">
        <picture>
            <source media="(prefers-color-scheme: dark)"
                srcset="https://developer.seequent.com/img/seequent-logo-dark.svg"
                alt="Seequent logo" width="400" />
            <img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" />
        </picture>
    </a>
</p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-duf/">
        <img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-duf" />
    </a>
    <a href="https://github.com/SeequentEvo/evo-data-converters/actions/workflows/on-merge.yaml">
        <img src="https://github.com/SeequentEvo/evo-data-converters/actions/workflows/on-merge.yaml/badge.svg" alt=""/>
    </a>
</p>
<p align="center">
    <a href="https://developer.seequent.com/" target="_blank">Seequent Developer Portal</a>
    &bull; <a href="https://community.seequent.com/" target="_blank">Seequent Community</a>
    &bull; <a href="https://seequent.com" target="_blank">Seequent website</a>
</p>

## Evo

Evo is a unified platform for geoscience teams. It enables access, connection, computation, and management of subsurface
data. This empowers better decision-making, simplified collaboration, and accelerated innovation. Evo is built on open
APIs, allowing developers to build custom integrations and applications. Our open schemas, code examples, and SDK are
available for the community to use and extend.

Evo is powered by Seequent, a Bentley organisation.

## Pre-requisites

* Python virtual environment with Python 3.10, 3.11, or 3.12

## Installation

The package can be installed from PyPI using pip:

```shell
pip install evo-data-converters-ags
```

## AGS

AGS (Association of Geotechnical and Geoenvironmental Specialists) is a standard data format widely used in the geotechnical and geoenvironmental industry for exchanging data. AGS files contain structured data in a tabular format, typically including borehole information, laboratory test results, and field observations.

This converter currently supports **Cone Penetration Test (CPT) data** and converts AGS files into Evo Downhole Collection objects.

### Supported AGS Groups

**Required Groups:**
- `LOCA` - Location Details (downhole/test locations)
- `SCPG` - Static Cone Penetration Tests - General
- `SCPT` - Seismic Cone Penetration Test results

**Optional Groups (imported if present):**
- `SCPP` - Static Cone Penetration Tests - Derived Parameters
- `GEOL` - Field Geological Descriptions
- `SCDG` - Static Cone Dissipation Tests - General
  - NOTE: SCDT (Static Cone Dissipation Tests - Data) is not imported, as this is time-series data. General dissipation information is present in SCDG.

## Usage

### Publish geoscience objects from an AGS file

The `convert_ags` function reads an AGS file and converts it into a Downhole Collection Geoscience Object that can be published to Evo.

```python
from evo.data_converters.ags.importer import convert_ags
from evo.notebooks import ServiceManagerWidget

# Login to Evo
manager = await ServiceManagerWidget.with_auth_code(client_id="your-client-id").login()

# Convert and publish AGS file
objects_metadata = convert_ags(
    filepath="path/to/your/file.ags",
    service_manager_widget=manager,
    tags={"source": "field_survey"},
    upload_path="cpt_data",
    overwrite_existing_objects=False,
)
```

For a complete working example, see the [import-ags notebook](./samples/import-ags/import-ags.ipynb).

### Export objects to AGS

Export functionality is not yet implemented.

## Code of conduct

We rely on an open, friendly, inclusive environment. To help us ensure this remains possible, please familiarise
yourself with our [code of conduct.](https://github.com/SeequentEvo/evo-data-converters/blob/main/CODE_OF_CONDUCT.md)

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
