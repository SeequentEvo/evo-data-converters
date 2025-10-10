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
* Microsoft Windows - this package is not currently supported on Linux or macOS
* Deswik Spatial - https://www.deswik.com/products/spatial
* .NET Framework v4.7.2 or higher (or other compatible .NET runtime)

## Installation

### Windows

#### Python package

The package can be installed from PyPI using pip:

    pip install evo-data-converters-duf

#### Deswik Suite

The `duf` data-converter package depends on an installed version of `Deswik.Suite` for interacting with DUF files. The
package will search for `Deswik.Suite` in `C:\Program Files\Deswik`, and use the latest version installed. If you have
installed `Deswik.Suite` in a different location, you will need to set the environment variable `DESWIK_PATH` to point
to your installation location, for example:

    set DESWIK_PATH="D:\Applications\Deswik\Deswik.Suite 2024.1"

This package has been tested with Deswik Suite version 2024.1.

#### .NET Framework

The package uses [pythonnet](https://pythonnet.github.io/pythonnet/) to resolve the appropriate .NET runtime. For Deswik.Suite 2024.1 up until (but not including) Deswik.Suite 2025.2, .NET Framework 4.7.2 or later is required. For 2025.2 and later, .NETCoreApp 8 or later is required.

If pythonnet fails to load the runtime, and you know where the runtime is installed, then you can set the environment variable DOTNET_ROOT. For other suggestions and more reading, see [here](https://pythonnet.github.io/pythonnet/python.html#loading-a-runtime). However, things described there are untested and may not work with your Deswik Suite installation.

### macOS

Not currently supported.

### Linux

Not currently supported.

## DUF

Deswik Unified File (DUF) is a proprietary file format from Deswik Mining Consultants Pty Ltd.

### Publish geoscience objects from a DUF file

[The `evo-sdk-common` Python library](https://pypi.org/project/evo-sdk-common/) can be used to sign in. After
successfully signing in, the user can select an organisation, an Evo hub, and a workspace. Use
[`evo-objects`](https://pypi.org/project/evo-objects/) to get an `ObjectAPIClient`, and
[`evo-data-converters-common`](https://pypi.org/project/evo-data-converters-common/) to convert your file.

Choose the DUF file you want to publish. Choose an EPSG code to use for the Coordinate Reference System. You can also
specify tags to add to the created geoscience objects.

The flag `combine_objects_in_layers` can be specified `True` to cause the convert to attempt to combine objects of the 
same type found in the same layer. For example, where a layer in the file contains only `Polyface` objects, these can
all be published as parts on a single Evo triangle-mesh object. Where a layer contains a mix of object types, or a
single type, but the Evo type the objects map to does not support multiple parts, the objects will be published as
separate Evo objects.

Then call `convert_duf`, passing it the DUF file path, EPSG code, the workspace metadata or service manager widget, the
tags, optionally the flag `combine_objects_in_layers`, and finally a path you want the published objects to appear under
in your workspace.

See [the convert-duf sample notebook](https://github.com/seequentevo/evo-data-converters/blob/main/packages/duf/samples/convert-duf/convert-duf.ipynb)
for a complete example.

**Note:** Some geometry types are not yet supported. A warning will be shown for each element that could not be
converted. Currently, for publishing we support polyface objects and polylines, and all attribute types except for colour
attributes.

### Export objects to DUF

To do.

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
