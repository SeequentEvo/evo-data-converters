<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-kml/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-kml" /></a>
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

`pip install evo-data-converters-kml`

## KML and KMZ files

KML (Keyhole Markup Language) is an XML format for geographic features such as points, paths, and polygons. KMZ is the compressed ZIP variant that contains KML content.

Refer to the OGC KML standard for details: https://www.ogc.org/standards/kml/

### Supported KML geometries
The KML converter currently supports importing placemarks that contain `Point` and `LineString` geometries from `.kml` and `.kmz` files.

### Implementations

The converter reads KML XML content using Python's built-in `xml.etree.ElementTree` module. KMZ archives are opened with Python's built-in `zipfile` module.

Parsed placemarks are translated to Evo objects as follows:
- `Point` geometries are converted to pointset objects.
- `LineString` geometries are converted to line segments objects.

### Publish geoscience objects from KML/KMZ files

[The `evo-sdk-common` Python library](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/common) can be used to sign in. After successfully signing in, the user can select an organisation, an Evo hub, and a workspace. Use [`evo-objects`](https://github.com/SeequentEvo/evo-python-sdk/tree/main/packages/evo-objects) to get an `ObjectAPIClient`, and [`evo-data-converters-kml`](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/kml) to convert your file.

Have a look at the `code-samples/convert-kml/convert-kml.ipynb` notebook for an example of how to publish KML/KMZ data.

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
limitations under the License.