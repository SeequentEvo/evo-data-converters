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
    <a href="https://pypi.org/project/evo-data-converters-ags/">
        <img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-ags" />
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

* Python 3.11 or newer

## Installation

The package can be installed from PyPI using pip:

```shell
pip install evo-data-converters-ags
```

For the Jupyter notebook examples below, install `evo-data-converters-ags[notebooks]` instead.

## AGS converter

Import **AGS4 Cone Penetration Test (CPT) data** into Evo as Downhole Collections, including geological descriptions
and hole orientation data where available.

### Supported data

- Files need project details (`PROJ` with a `PROJ_ID`), locations (`LOCA`), and CPT data (`SCPG` and `SCPT`).
- Derived CPT parameters (`SCPP`), geological descriptions (`GEOL`), and hole orientation (`HORN`) are included when present.
- Other AGS groups are not imported. AGS3 files and export to AGS are not supported.

## Usage

### Import and publish

In a Jupyter notebook, sign in to Evo and import your file:

```python
from evo.data_converters.ags import convert_ags
from evo.notebooks import ServiceManagerWidget

manager = await ServiceManagerWidget.with_auth_code(client_id="your-client-id").login()

objects = await convert_ags(
    filepaths=["survey.ags"],
    service_manager_widget=manager,
    upload_path="cpt_data",
)
```

Add more filenames to `filepaths` to import several files at once. Compatible files with the same project ID are
combined into one collection. Set `merge_files=False` to keep them separate.

To convert without publishing to Evo, add `publish_objects=False`.

For a complete working example, see the [convert-ags notebook](./samples/convert-ags/convert-ags.ipynb).

### Warnings and errors

If some files cannot be imported, the remaining valid files are still processed. Holes without usable coordinates
are skipped along with their measurements.

Use `diagnostics` to see what needs attention. If no files can be imported, `AgsParsingError` explains the problem:

```python
from evo.data_converters.ags import AgsParsingError

issues = []
try:
    objects = await convert_ags(
        filepaths=["survey.ags"],
        service_manager_widget=manager,
        diagnostics=issues,
    )
except AgsParsingError as error:
    issues = error.diagnostics
for issue in issues:
    print(issue.code, issue.group, issue.reason)
```

## Things to know

- Only the first CPT push at each location is imported.
- Combined files must use compatible coordinate systems and matching units for shared columns.
  Use `merge_files=False` to import incompatible files separately.
- Source values and units are preserved wherever possible. Hole geometry is converted only where needed for
  consistent positioning.
- Grid coordinates and latitude/longitude are supported. Coordinates should match their declared reference.
  No reprojection or vertical datum conversion is performed.
- Use recognised length units for grid coordinates and depths, and degrees or radians for longitude/latitude.
  Coordinates without a usable unit are kept as extra data, but are not used to position holes.
- Final hole depth comes from the deepest imported CPT reading or geological interval. The recorded final depth
  (`LOCA_FDEP`) is kept as extra data, not used to override it.
- Missing or invalid ground levels default to zero, so check them before using the imported data.
- Where hole orientation is unavailable, the hole is assumed to be vertical.

## Resources

- [AGS Data Format Specification](https://www.ags.org.uk/data-format/)
- [Evo Downhole Collections](https://developer.seequent.com/docs/data-structures/geoscience-objects/schemas/downhole-collection)

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
