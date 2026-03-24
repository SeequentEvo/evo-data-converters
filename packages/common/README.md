<p align="center"><a href="https://seequent.com" target="_blank"><picture><source media="(prefers-color-scheme: dark)" srcset="https://developer.seequent.com/img/seequent-logo-dark.svg" alt="Seequent logo" width="400" /><img src="https://developer.seequent.com/img/seequent-logo.svg" alt="Seequent logo" width="400" /></picture></a></p>
<p align="center">
    <a href="https://pypi.org/project/evo-data-converters-common/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/evo-data-converters-common" /></a>
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

* Python 3.10, 3.11, or 3.12

## Installation

```shell
pip install evo-data-converters-common
```

## Data converters

This package provides a framework for Evo-specific data converters.

When running a converter, data is imported from a supported file format, converted into geoscience objects, and then
published to the Seequent Evo API.

This framework (`evo.data_converters.common`) can be used to build custom data converters for any type of geoscience
data.

For an existing set of supported data converters, see:
* [GOCAD](../gocad/README.md)
* [OMF](../omf/README.md)
* [RESQML](../resqml/README.md)
* [UBC](../ubc/README.md)
* [VTK](../vtk/README.md)

Data converters can be optionally both an importer and an exporter.

* The importer will load data into Seequent Evo.
* The exporter will export data from Seequent Evo into the designated file format.

There are examples of both in the OMF converter.

Each converter will support a subset of Evo geoscience objects.

Existing converters can be extended to support additional geoscience objects depending on your data requirements.

New converters can be created to support additional data file types.

## Developing converters

### Working on data converters

To work on your local version of the data converters module, first follow the directions in [Setting up your environment.](https://github.com/seequentevo/evo-data-converters/blob/main/README.md)

In the root directory of the project run:

```shell
uv sync --all-packages --all-extras
```

### General converter architecture

Within `packages/common` the directory structure for converters comprises a top level common directory, containing
common modules that are usable across all converters. In the other `packages` folders are various supported data
converter packages that build on the "common" library:

```text
.
├── common/
├── omf/
├── resqml/
├── vtk/
└── README.md
```
Expanding this out, each converter type contains an `importer` directory, an `exporter` directory (if supported), and
any other utility modules specific to this converter type:

```text
.
├── common/src/evo/data_converters/common/
│   ├── __init__.py
│   └── blockmodel_client.py
│   └── evo_client.py
│   └── exceptions.py
│   └── generate_paths.py
│   └── publish.py
│   └── utils.py
│   └── (and more common modules)
├── omf/code-samples/
├── omf/src/evo/data_converters/omf/
│   ├── exporter/
│   │   └── __init__.py
│   │   └── evo_to_omf.py
│   │   └── (and more modules specific to omf/exporter)
│   ├── importer/
│   │   └── __init__.py
│   │   └── omf_to_evo.py
│   │   └── (and more modules specific to omf/importer)
│   ├── __init__.py
│   ├── utils.py
│   └── (and more common modules for omf)
├── resqml/code-samples/
├── resqml/src/evo/data_converters/resqml/
│   ├── importer/
│   │   └── __init__.py
│   │   └── resqml_to_evo.py
│   │   └── (and more modules specific to resqml/importer)
│   ├── __init__.py
│   ├── utils.py
│   └── (and more common modules for resqml)
├── vtk/src/evo/data_converters/vtk/
│   ├── importer/
│   │   └── __init__.py
│   │   └── vtk_to_evo.py
│   │   └── (and more modules specific to vtk/importer)
│   ├── __init__.py
└── README.md
```

### Structure of a converter

The converters are designed to follow a consistent coding pattern to encourage reusability and commonality.  Within
this pattern there is much room for flexibility, although this is expected to come at the lower level when addressing
the needs of specific data sources.

#### Importer

An importer takes geoscience data from a specific file type, converts it to Evo geoscience objects and uploads these
objects to Evo.

As observable in the example Jupyter notebook for [converting an OMF file](../omf/code-samples/convert-omf/convert-omf.ipynb) the main interface to a convertor
is the `convert_*` function.  This function will be in a module in the root directory of the
named `yourfiletype_to_evo.py`.

Within this function the following tasks must be completed:

* Read the passed data file
* Extract supported geoscience objects from the file
* Convert source geoscience objects into Evo geoscience objects
* Publish the geoscience objects to [the Geoscience Object API](https://developer.seequent.com/docs/guides/objects)

By convention the convert function should return a list, and the items in the list are either instances of the
`BaseSpatialDataProperties_V1_0_1` class or the `ObjectMetadata` class.

The return items will be `BaseSpatialDataProperties_V1_0_1` class if returning geoscience objects directly.  The
purpose of this option is if you wish to use the converter to transform data into Evo geoscience objects but not
publish directly to the Geoscience Object API.

The return items will be `ObjectMetadata` class if returning the output of the upload to the Geoscience Object API.

#### Example importer

The following pseudocode shows the bare basics of a new converter for `yourfiletype` importing point set data, based
of the existing OMF importer.

```python
# Import common objects for working with the Geoscience Object API
from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
    publish_geoscience_objects,
)

# Import file parsing modules required - this is pure pseudocode and will vary
# depending on the type of file
from yourfileparsermodule import yourfileparser

# Define the main convert function
def convert_yourfiletype(
    filepath: str,
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    upload_path: str = "",
    overwrite_existing_objects: bool = False
) -> list[ObjectMetadata]:
    geoscience_objects = []

    # create a service and data clients to handle upload to the Seequent Evo API
    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )

    # Read your specific file type to an object ready for conversion (pseudocode only here)
    reader = yourfileparser(filepath)

    # Loop through the elements found in the file - converting any point set elements into to
    # Evo geoscience objects
    for element in reader.elements():
        geoscience_object = None
        if element.type == "pointset":
            # Call the specific pointset converter here
            geoscience_object = _convert_pointset(element, reader, data_client, epsg_code)

        if geoscience_object:
            geoscience_objects.append(geoscience_object)

    # Publish the found geoscience objects to Evo
    objects_metadata = publish_geoscience_objects(
        geoscience_objects, object_service_client, data_client, upload_path, overwrite_existing_objects
    )

    # Return the publishing response
    return objects_metadata

```

**Note:** this example only returns the `ObjectMetadata`, and will publish immediately.  Refer to the existing
converter examples to see usage for the optional return of `BaseSpatialDataProperties_V1_0_1`.


##### Parameters

The following parameters are passed into the convert function.  By convention these are the typical minimum parameters
a convert function should have, however additional ones can be added as needed for specific usage needs.

| Parameter          | Description  |
|---------------|--------|
| `filepath`  |Path to the OMF file.  |
| `epsg_code`        | The EPSG code to use when creating a coordinate reference system object. For information on other supported coordinate reference systems refer to [the "common data types" documentation.](https://developer.seequent.com/docs/api/fundamentals/common-data-types#coordinate-reference-systems) |
| `evo_workspace_metadata` | (Optional) Evo workspace metadata.  |
| `service_manager_widget` | (Optional) Service Manager Widget for use in Jupyter notebooks. |
| `tags` | (Optional) Key value pair list of metadata tags to attach to the geoscience object. |
| `upload_path` | (Optional) Path objects will be published under.  Defaults to the root of the workspace. |

#### File parsing

Both the OMF and RESQML converters use external libraries for parsing the file into usable Python objects by the
converter function.  This will vary for different file types and in some cases file parsers may need to be developed
from scratch.  Refer to OMF and RESQML converters for existing examples of this (`omf2` and `resqpy` respectively).

#### Conversion to geoscience objects

As observable in the example above, the top level convert function will then use specific conversion functions for
each type of geoscience data.  As with file parsing, the specific method for conversion will vary depending on the
data source.  All these functions should return an Evo supported geoscience object type ready for upload to Evo.
For the point set example, this will be `Pointset_V1_2_0`.

### Exporter

An exporter takes specified geoscience objects from Evo and converts them to a specified file format on disk.

Reversing the pattern of the importer, the main interface of an exporter is the `export_*` function that takes a
specified list of Evo objects and a filepath to create the file.

### Example exporter

Refer to [evo_to_omf.py](../omf/src/evo/data_converters/omf/exporter/evo_to_omf.py) for an example of the `export_omf` function.

#### Parameters

| Parameter          | Description  |
|---------------|--------|
| `filepath`  | Path of the OMF file to create. |
| `objects`        | List of `EvoObjectMetadata` objects containing the UUID and version of the Evo objects to export. |
| `omf_metadata` | (Optional) Project metadata to embed in the OMF file. |
| `evo_workspace_metadata` | (Optional) Evo workspace metadata. |
| `service_manager_widget` | (Optional) `ServiceManagerWidget` for use in notebooks. |

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
