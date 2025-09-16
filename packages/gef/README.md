<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-gef/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-gef" /></a>
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

The `gef` data-converter package depends upon the `pygef` package. Pygef should install automatically when evo-data-converter-gef is installed.

```shell
pip install evo-data-converters-gef
```

## GEF format

The GEF (Geotechnical Exchange Format) is a standardized text-based file format used for exchanging geotechnical data, such as Cone Penetration Test (CPT) and borehole (BORE) information. GEF files are widely used in geotechnical engineering and typically have the `.gef` extension.

### GEF CPT

This will convert Cone Penetration Tests to the Evo format.

### GEF BORE

This format will not be supported at this stage.

## Usage

You can either use the [convert-gef notebook](packages/gef/samples/convert-gef/convert-gef.ipynb) and modify to suit your needs, or write a python script using the following as a starting point:

```python
import glob
import tempfile
from pprint import pp

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.gef.importer import convert_gef

tmp_cache_dir = tempfile.TemporaryDirectory()
cache_dir = tmp_cache_dir.name

client_id = "your-client-id"
org_id = ""
workspace_id = ""
hub_url = ""
redirect_url = ""

workspace_metadata = EvoWorkspaceMetadata(client_id=client_id, hub_url=hub_url, org_id=org_id, workspace_id=workspace_id, redirect_url=redirect_url, cache_root=cache_dir)

gef_files = glob.glob("packages/gef/samples/convert-gef/data/input/*")

objects_metadata = convert_gef(
    filepaths=gef_files, evo_workspace_metadata=workspace_metadata, upload_path="gef-cli", overwrite_existing_objects=True
)

pp(objects_metadata)
```

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
