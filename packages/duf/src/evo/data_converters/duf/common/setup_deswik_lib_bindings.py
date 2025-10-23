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

import platform
import sys
import os

import evo.logging

from evo.data_converters.duf.common.consts import DESWIK_INSTALL_PATH_ENV, DEFAULT_WINDOWS_INSTALL_ROOT

if platform.system() != "Windows":
    raise ImportError("DUF conversion is only supported on Windows.")


if (deswik_path := os.getenv(DESWIK_INSTALL_PATH_ENV)) is None:
    missing_install_msg = (
        f"Deswik.Suite is expected to be installed somewhere under {DEFAULT_WINDOWS_INSTALL_ROOT}, but nothing is "
        f"there. If you know the install directory, then you can set the environment variable `DESWIK_PATH`."
    )

    if not os.path.exists(DEFAULT_WINDOWS_INSTALL_ROOT):
        raise OSError(missing_install_msg)

    installs = [path for path in os.listdir(DEFAULT_WINDOWS_INSTALL_ROOT) if "Suite" in path]
    if not installs:
        raise OSError(missing_install_msg)

    # Sort by version
    def by_version(path):
        version = path.split(" ")[-1]
        year, month = version.split(".")
        return int(year), int(month)

    most_recent_install_dir = sorted(installs, key=by_version, reverse=True)[0]
    deswik_path = os.path.join(DEFAULT_WINDOWS_INSTALL_ROOT, most_recent_install_dir)

if not os.path.exists(deswik_path):
    missing_install_msg = (
        f"Deswik.Suite is expected to be installed at {deswik_path}, but nothing is there. If you "
        f"know the install directory, then you can set the environment variable `DESWIK_PATH`."
    )
    raise OSError(missing_install_msg)


logger = evo.logging.getLogger("data_converters")
logger.debug("Looking for Deswik DLLs in: %s", deswik_path)

sys.path.insert(0, deswik_path)

import clr  # noqa: E402 # Do this after modifying sys.path, so that Deswik-bundled DLLs are prioritized

clr.AddReference("Deswik.Duf")
clr.AddReference("Deswik.Entities")
clr.AddReference("Deswik.Entities.Cad")
clr.AddReference("Deswik.Serialization")
clr.AddReference("Deswik.Core.Structures")
