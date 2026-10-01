#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from evo.data_converters.agsi.reader import AgsiPackage
from evo.data_converters.agsi.reader.errors import AGSIDataFileIOError, AGSIInvalidDataError

__all__ = ["AGSIDataFileIOError", "AGSIInvalidDataError", "read_agsi_file"]


def read_agsi_file(filepath: str) -> AgsiPackage:
    """Read an AGSi package from disk.

    ``filepath`` may be a ``.agsi`` ZIP archive, a folder with the extracted package contents,
    the main AGSi JSON file, or the package ``index.json``. Pre-1.0 (v0.6) documents are
    normalised to the AGSi 1.0.x layout.

    :param filepath: Path to the AGSi package or main JSON file.
    :return: The loaded package. Use ``package.document`` for the typed AGSi document and
        ``package.read_geometry(...)`` to parse supporting geometry files.

    :raise AGSIDataFileIOError: If the file cannot be opened or read.
    :raise AGSIInvalidDataError: If the file contents are invalid.
    """
    return AgsiPackage.open(filepath)
