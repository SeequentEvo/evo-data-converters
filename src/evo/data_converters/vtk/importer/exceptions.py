#  Copyright © 2025 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


class VTKImportError(Exception):
    """Exception that is raised if there is an error during the reading of a VTK file."""


class VTKConversionError(Exception):
    """Exception that is raised if there is an error during the conversion of a VTK data object."""


class GhostValueError(VTKConversionError):
    """Exception that is raised if ghost cells or points are detected in the VTK data object.

    This includes if points are blanked out in the VTK data object.
    """


class UnsupportedCellTypeError(VTKConversionError):
    """Exception that is raised if an unsupported cell type is detected in the VTK unstructured grid."""
