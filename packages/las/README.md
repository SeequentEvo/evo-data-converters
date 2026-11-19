<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-las/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-las" /></a>
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

* Python virtual environment with Python 3.11 or newer
* Git

## Installation

`pip install evo-data-converters-las`

## LAS converter

Imports one or more [LAS 2.0](https://www.cwls.org/products/) files into a single Evo **downhole collection**, and also creates a **point set** with one point per log sample.

* One hole per file; the hole id is the `WELL` header value (falling back to `UWI`, then the file name).
* The index curve must be depth (`DEPT`/`DEPTH`); depths in feet are converted to metres. Time/index-based files are rejected.
* Wrapped and unwrapped data, `#` comments, `NULL` values (read as NaN), and space, comma or tab delimiters are supported.
* All other curves become continuous attributes of a single depth-indexed "Well logs" table (units and descriptions are kept as attribute tags). Curves missing from a hole are NaN.
* The point set (named `<collection name> points`) has a `holeid` category attribute plus one attribute per curve (NaN where a hole lacks the curve). Each point's x, y, z is the minimum curvature position along the hole trajectory at the sample depth (z is elevation).
* Collar and survey come from optional Petrel deviation (`.dev`) files (collar from the `WELL HEAD X/Y` and `KB` header, survey from `MD`, `AZIM`, `INCL`; `INCL` is converted to Evo dip as `90 - INCL`). Without them each hole gets a collar at (0, 0, 0) and a vertical path.

```python
from evo.data_converters.las import convert_las

await convert_las(
    filepath=["BR-I-1.las", "BR-I-2.las"],
    evo_workspace_metadata=metadata,
    deviation_files="path/to/dev-directory",  # or a list of files, or {"BR-I-1": "BR-I-1.dev"}
    # coordinate_reference_system=32650,  # optional; omit for a local (unspecified) CRS
)
```

Deviation files are matched to holes by well name or file name. If `deviation_files` is given and a hole has no match, an error is raised unless `allow_missing_deviation=True`. Deviation coordinates and depths are assumed to be in metres.


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