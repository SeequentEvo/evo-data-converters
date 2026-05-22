<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-xyz/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-xyz" /></a>
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

`pip install evo-data-converters-xyz`

## XYZ

XYZ (`.xyz`) is a simple ASCII file format where each line contains space- or comma-separated coordinate values. The converter automatically detects the file variant from the first data line. Header lines (any line not starting with a digit, `.`, `+`, or `-`) are automatically skipped. Sentinel values (`*`) are replaced with `-1.0e32`.

### Supported file types

| Type | Delimiter | Columns | Example |
|------|-----------|---------|---------|
| **Points** | comma | 3 numeric (x, y, z) | `10.2,10.2,10.3` |
| **Binary** | comma | 2 numeric (x, y) | `12.2,12.3` |
| **Geochemistry (comma)** | comma | label + 3 numeric (x, y, z) | `C,10.1,10.2,10.3` |
| **Geochemistry (space)** | space | label + 3 numeric (x, y, z) | `C 10.1 10.2 10.3` |
| **Geosoft Binary XYZ** | space | 2 numeric (x, y); z set to `0.0` | `-0.69 -1.40` |
| **Geosoft Binary XYZ + Data** | space | ≥3 columns; x, y + data value; z set to `0.0` | `-0.69 -1.40 5.2` |
| **Geosoft XYZ Triplet** | space | 3 numeric (x, y, z) | `-0.69 -1.40 0.20` |
| **Geosoft XYZ Triplet + Data** | space | ≥4 columns; x, y, z + data value | `-0.69 -1.40 0.20 5.2` |

> **Type disambiguation for multi-column Geosoft files:** when the file has ≥3 space-separated columns, the detected type depends on the `z_index` and `data_index` parameters passed to `convert_xyz`:
> - `data_index` set, `z_index = -1` → **Geosoft Binary XYZ + Data** (z forced to `0.0`)
> - `data_index` set, `z_index` set → **Geosoft XYZ Triplet + Data**
> - neither set → **Geosoft XYZ Triplet**

### Column index parameters

All index parameters default to `-1`, which means "use the natural column order". Pass explicit zero-based column indices to select different columns from the file. These are only used in the **Geosoft** types, being ignored for all the others.

| Parameter | Default (`-1`) | Custom (≥ 0) |
|-----------|----------------|--------------|
| `x_index` | column 0 | picks the specified column |
| `y_index` | column 1 | picks the specified column |
| `z_index` | column 2 (or `0.0` for binary types) | picks the specified column; also promotes the type to Triplet + Data when `data_index` is also set |
| `data_index` | no attribute created | picks the specified column as a per-point `data` attribute on the pointset |

### Implementations

The XYZ converter currently supports:

- **Reading** – Parse a `.xyz` file into a NumPy `float64` array of shape `(N, 3)` plus an optional `list[float]` of per-point data values.
- **Type detection** – Automatically identify the XYZ variant from the first data line, refined by the `z_index`/`data_index` parameters.
- **Parquet export** – Save the parsed coordinates to a Parquet file with three `float64` columns (`x`, `y`, `z`). Per-point data values are saved to a separate Parquet file.
- **Publishing** – Import the XYZ file as a `Pointset` (schema `pointset/1.3.0`) into an Evo workspace. When data values are present they are attached as a `ContinuousAttribute` named `data` on the pointset locations.


### Publish geoscience objects from an XYZ file(s)

The [`evo-sdk-common`](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/common) Python library can be used to sign in. After successfully signing in, the user can select an organisation, an Evo hub, and a workspace. Use [`evo-objects`](https://github.com/SeequentEvo/evo-python-sdk/tree/main/packages/evo-objects) to get an `ObjectAPIClient`, and [`evo-data-converters-xyz`](https://github.com/SeequentEvo/evo-data-converters/tree/main/packages/xyz) to convert your file.

Have a look at the `code-samples/convert-xyz.ipynb` notebook for an example of how to publish XYZ files.

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