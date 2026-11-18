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

This converter currently supports **Cone Penetration Test (CPT) data** and converts AGS files into Evo Downhole Collection objects. The converter uses the [python-ags4](https://gitlab.com/ags-data-format-wg/ags-python-library) library for parsing and validating AGS files.

**Related Resources:**
- [AGS Data Format Specification](https://www.ags.org.uk/data-format/)
- [AGS4.1.1 Specification PDF](https://www.ags.org.uk/content/uploads/2022/02/AGS4-v-4.1.1-2022.pdf)
- [Evo Downhole Collection Schema](https://developer.seequent.com/docs/data-structures/geoscience-objects/schemas/downhole-collection)

## Usage

### Publish geoscience objects from an AGS file

The `convert_ags` function reads AGS files and converts them into Downhole Collection Geoscience Objects that can be published to Evo.
Multiple projects can be imported at once, and all files within the same project (`PROJ_ID`) will be included in a downhole collection together.

```python
from evo.data_converters.ags.importer import convert_ags
from evo.notebooks import ServiceManagerWidget

# Login to Evo
manager = await ServiceManagerWidget.with_auth_code(client_id="your-client-id").login()

# Convert and publish AGS file
objects_metadata = await convert_ags(
    filepaths=["path/to/your/file.ags"],
    service_manager_widget=manager,
    tags={"source": "field_survey"},
    upload_path="cpt_data",
    overwrite_existing_objects=False,
)
```

For a complete working example, see the [convert-ags notebook](./samples/convert-ags/convert-ags.ipynb).

### Export objects to AGS

Export functionality is not yet implemented.

## Importing AGS - details

### Supported AGS Groups

**Required Groups:**
- `LOCA` - Location Details (hole/test locations with coordinates)
- `SCPG` - Static Cone Penetration Tests - General (test metadata)
- `SCPT` - Seismic Cone Penetration Test results (distance-based measurements)

**Optional Groups (imported if present):**
- `SCPP` - Static Cone Penetration Tests - Derived Parameters (interval data)
- `GEOL` - Field Geological Descriptions (interval data)
  - **Note:** GEOL rows without corresponding CPT data (LOCA_ID not in SCPG/LOCA tables) are dropped with a warning

**Other Groups Used (if present):**
- `PROJ` - Project metadata (used for naming and grouping files)
- `HORN` - Hole orientation data (for non-vertical downholes)
- `TYPE` - Data type definitions for columns

Any additional groups will be discarded.

### AGS Types

AGS TYPE codes are mapped to appropriate pandas/Python types:

- Integer types: 0DP
- Float types: 1DP, 2DP, 3DP, 4DP, 5DP, MC (moisture content), scientific notation (nSCI), significant figures (nSF)
- Datetime: DT (supports multiple formats including ISO, dd/mm/yyyy, etc.)
- Timedelta: T (elapsed time with unit conversion)
- Boolean: YN (Y/N values)
- String: ID, PA, PT, PU, RL, U, X, XN and others default to string

### CRS (Coordinate Reference System) Handling

- Supports standard AGS abbreviations: OSGB (EPSG:27700), OSI (EPSG:29902), ITM (EPSG:2157)
- Resolves the CRS per hole (`LOCA` row) from CRS names and EPSG codes in `LOCA_GREF`, falling back to `LOCA_LLZ`
- Rejects a file whose holes declare different CRSs, because a downhole collection has a single CRS; during conversion that file is skipped and logged
- Holes without a declared CRS adopt the CRS declared by the other holes, with a warning
- Projected CRSs use only complete `LOCA_NATE`/`LOCA_NATN` pairs
- Geographic CRSs use only `LOCA_LON`/`LOCA_LAT`, even when projected columns are populated
- Raises `AgsFileInvalidException` if any imported hole lacks a complete coordinate pair in the detected CRS family
- Handles LOCAL as "unspecified" CRS
- When the CRS cannot be resolved, selects one coordinate family and logs that it cannot be verified
- Non-standard columns such as `LOCA_EASTING`/`LOCA_NORTHING` are not read

### Importing multiple files

- Multiple AGS files can be processed together
- Files with the same PROJ_ID are automatically merged into a single DownholeCollection
- Files can be imported into separate downhole collections by using the `merge_files` parameter

### Non-Vertical Downholes and Geometry

- HORN table data is used to calculate dip and azimuth for measurement depths
- Measurements unspecified or outside HORN intervals default to vertical (90°/0°)

### Assumptions & Limitations

- **Coordinate families and elevation:** Local coordinates (`LOCA_LOCX`/`LOCA_LOCY`) use `LOCA_LOCZ`, which AGS defines relative to the local datum named in `LOCA_DATM`. AGS defines `LOCA_GL` as ground level relative to the datum of the location, but does not declare that vertical datum, and `LOCA_GREF`/`LOCA_LLZ` identify only the horizontal reference system. As a parser convention, national grid coordinates (`LOCA_NATE`/`LOCA_NATN`) and geographic coordinates (`LOCA_LON`/`LOCA_LAT`) use `LOCA_GL` as the collar elevation, because AGS has no separate elevation field for either family. When `LOCA_GL` is used and `LOCA_DATM` is blank or absent, the parser warns that the vertical datum is undeclared. The original `LOCA_DATM` is retained as a collar attribute, with blank or absent values represented as `"undeclared"`. The collection CRS therefore describes X/Y only; Z is stored as the source value and is not expressed in a vertical axis of that CRS. The parser does not mix coordinate families to fill missing values, so it never falls back from `LOCA_GL` to `LOCA_LOCZ` or the reverse. If the selected family's elevation is missing or non-numeric, the affected hole is logged and Z defaults to 0.0. No coordinate transformation, elevation-unit conversion, or vertical datum conversion is performed.
- **Unspecified coordinate reference:** A declared local reference (`LOCA_GREF=LOCAL` or `LOCA_LREF`) selects the local coordinate family and requires complete `LOCA_LOCX`/`LOCA_LOCY` values. If no reference is declared, the parser chooses one available coordinate family for the table in national, local, then geographic order and logs that the family cannot be verified.
- **Hole identification:** Holes are uniquely identified by the combination of `LOCA_ID` and `SCPG_TESN`. The display `hole_id` is formatted as `"LOCA_ID:SCPG_TESN"` or just `"LOCA_ID"` if no TESN (e.g., geological descriptions from GEOL).
- **CRS preference:** When a hole has CRS information in both `LOCA_GREF` and `LOCA_LLZ`, `LOCA_GREF` is preferred.
- **AGS validation rules:** Some AGS format rules are ignored during validation to accommodate real-world files (see `IGNORED_RULES` in [ags_context.py](./src/evo/data_converters/ags/common/ags_context.py)).

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
