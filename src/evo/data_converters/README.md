## Data converters

There are currently data converters for the following file formats:

* [OMF](omf/README.md)
* [RESQML](resqml/README.md)
* [GOCAD](gocad/README.md)
* [UBC](ubc/README.md)
* [VTK](vtk/README.md)

Data converters can be optionally both an importer and an exporter.

* The importer will load data into Seequent Evo.
* The exporter will export data from Seequent Evo into the designated file format.

There are examples of both in the OMF converter.

Each converter will support a subset of Evo Geoscience Objects.

Existing converters can be extended to support additional geoscience objects depending on your data requirements.

New converters can be created to support additional data file types.


## Working on data converters

To work on your local version of the data converters module, first follow the directions in [Setting up your environment](../../../README.md).

In the root directory of the project run:

```
uv sync --all-extras

```

## General converter architecture

Within `src/eco/data_converters/` the directory structure for converters comprises a top level common directory, containing common modules that are usable across all types of converters, and a top level directory for each supported converter type:

```
.
├── common/
├── omf/
├── resqml/
├── vtk/
├── __init__.py
└── README.md
```
Expanding this out, each converter type contains an `importer` directory, an `exporter` directory (if supported), and any other utility modules specific to this converter type:

```
.
├── common/
│   ├── __init__.py
│   └── blockmodel_client.py
│   └── evo_client.py
│   └── exceptions.py
│   └── generate_paths.py
│   └── publish.py
│   └── utils.py
│   └── (and more common modules)
├── omf/
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
├── resqml/
│   ├── importer/
│   │   └── __init__.py
│   │   └── resqml_to_evo.py
│   │   └── (and more modules specific to resqml/importer)
│   ├── __init__.py
│   ├── utils.py
│   └── (and more common modules for resqml)
├── vtk/
│   ├── importer/
│   │   └── __init__.py
│   │   └── vtk_to_evo.py
│   │   └── (and more modules specific to vtk/importer)
│   ├── __init__.py
├── __init__.py
└── README.md
```

## Structure of a converter

The converters are designed to follow a consistent coding pattern to encourage reusability and commonality.  Within this pattern there is much room for flexibility, although this is expected to come at the lower level when addressing the needs of specific data sources.

### Importer

An importer takes geoscience data from a specific file type, converts it to Evo Geoscience Objects and uploads these objects to Evo.

As observable in the example Jupyter notebook for [publishing an OMF file](../../../samples/data-converters/python/convert-omf/publish-omf.ipynb) the main interface to a convertor is the `convert_*` function.  This function will be in a module in the root directory of the named `yourfiletype_to_evo.py`.

Within this function the following tasks must be completed:

* Read the passed data file
* Extract supported geoscience objects from the file
* Convert source geoscience objects into Evo Geoscience Objects
* Publish the geoscience objects to the Seequent Evo API

By convention the convert function should return a list, and the items in the list are either instances of the `BaseSpatialDataProperties_V1_0_1` class or the `ObjectMetadata` class.

The return items will be `BaseSpatialDataProperties_V1_0_1` class if returning thing geoscience objects directly.  The purpose of this option is if you wish to use the converter to transform data into Evo Geoscience Objects but not publish directly to the Seequent Evo API.

The return items will be `ObjectMetadata` class if returning the output of the upload to the Seequent Evo API.

### Example importer

The following pseudocode shows the bare basics of a new converter for `yourfiletype` importing point set data, based of the existing OMF importer.

```
# Import common objects for working with the Seequent Evo API
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
    filepath: str
    epsg_code: int,
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
    upload_path: str = "",
) -> list[ObjectMetadata]:
    geoscience_objects = []

    # create a service and data clients to handle upload to the Seequent Evo API
    object_service_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata, service_manager_widget=service_manager_widget
    )

    # Read your specific file type to an object ready for conversion (pseudocode only here)
    reader = yourfileparser(filepath)

    # Loop through the elements found in the file - converting any point set elements into to
    # Evo Geoscience Objects
    for element in reader.elements():
        geoscience_object = None
        if element.type = "pointset":
            # Call the specific pointset converter here
            geoscience_object = _convert_pointset(element, reader, data_client, epsg_code)

        if geoscience_object:
            geoscience_objects.append(geoscience_object)

    # Publish the found geoscience objects to Evo
    objects_metadata = None
    objects_metadata = publish_geoscience_objects(
        geoscience_objects, object_service_client, data_client, upload_path
    )

    # Return the publishing response
    return objects_metadata

```

_Note: this example only returns the `ObjectMetadata`, with no option to not publish immediately.  Refer to the existing converter examples to see usage for the optional return of `BaseSpatialDataProperties_V1_0_1`._


#### Parameters

The following parameters are passed into the convert function.  By convention these are the typical minimum parameters a convert function should have, however additional ones can be added as needed for specific usage needs.

| Parameter          | Description  |
|---------------|--------|
| filepath  |Path to the OMF file.  |
| epsg_code        | The EPSG code to use when creating a coordinate reference system object. For information on other supported coordinate reference systems refer to: https://developer.seequent.com/docs/api/fundamentals/common-data-types#coordinate-reference-systems |
| evo_workspace_metadata | (Optional) Evo workspace metadata.  |
| service_manager_widget |(Optional) Service Manager Widget for use in Jupyter notebooks. |
| upload_path | (Optional) Path objects will be published under.  Defaults to the root of the workspace. |

#### File parsing

Both the OMF and RESQML converters use external libraries for parsing the file into usable Python objects by the converter function.  This will vary for different file types and in some cases file parsers may need to be developed from scratch.  Refer to OMF and RESQML converters for existing examples of this (`omf2` and `resqpy` respectively).

#### Conversion to geoscience objects

As observable in the example above, the top level convert function will then use specific conversion functions for each type of geoscience data.  As with file parsing, the specific method for conversion will vary depending on the data source.  All these functions should return an Evo supported geoscience object type ready for upload to Evo.  For the point set example, this will be `Pointset_V1_2_0`.

### Exporter

An exporter takes specified Geoscience objects from Evo and converts them to a specified file format on disk.

Reversing the pattern of the importer, the main interface of an exporter is the `export_*` function that takes a specified list of Evo objects and a filepath to create the file.

### Example exporter

Refer to [evo_to_omf.py](omf/exporter/evo_to_omf.py) for an example of the `export_omf` function.

#### Parameters

| Parameter          | Description  |
|---------------|--------|
| filepath  |Path of the OMF file to create.  |
| objects        | List of EvoObjectMetadata objects containing the UUID and version of the Evo objects to export.  |
| omf_metadata | Optional project metadata to embed in the OMF file. |
| evo_workspace_metadata | Optional Evo Workspace metadata  |
| service_manager_widget | Optional ServiceManagerWidget for use in notebooks.|
