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

import pythonnet

import evo.logging


DEFAULT_WINDOWS_INSTALL_ROOT = r"C:\Program Files\Deswik"
DESWIK_INSTALL_PATH_ENV = "DESWIK_PATH"


if platform.system() != "Windows":
    raise RuntimeError("This script is only supported on Windows.")


def get_version(path):
    try:
        version = path.split(" ")[-1]
        year, month = version.split(".")
        return int(year), int(month)
    except (IndexError, TypeError):
        return -1, -1


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

    most_recent_install_dir = sorted(installs, key=get_version, reverse=True)[0]
    deswik_path = os.path.join(DEFAULT_WINDOWS_INSTALL_ROOT, most_recent_install_dir)


deswik_version = get_version(os.path.basename(deswik_path))


if not os.path.exists(deswik_path):
    missing_install_msg = (
        f"Deswik.Suite is expected to be installed at {deswik_path}, but nothing is there. If you "
        f"know the install directory, then you can set the environment variable `DESWIK_PATH`."
    )
    raise ImportError(missing_install_msg)


if deswik_version == (-1, -1):
    raise ImportError(f"Deswik install at path {deswik_path} does not appear to have a valid version")


logger = evo.logging.getLogger("data_converters")
logger.debug("Looking for Deswik DLLs in: %s", deswik_path)

sys.path.insert(0, deswik_path)

if (dotnet_root := os.environ.get("DOTNET_ROOT")) is not None and not os.path.exists(dotnet_root):
    # DOTNET_ROOT was observed to be set to an unexpected value, which will cause `pythonnet.load()` to fail.

    # During development, DOTNET_ROOT was observed to be set to a directory that didn't exist by an application
    # installer. It cannot be assumed to be set correctly. Instead of failing, silently ignore it (with a warning).
    del os.environ["DOTNET_ROOT"]
    msg = f"The environment variable DOTNET_ROOT is set to {dotnet_root}, but there is nothing there, so it is being ignored."
    logger.warn(msg)

if deswik_version >= (2025, 2):
    # Target the newer .NETCoreApp runtime
    pythonnet.load("coreclr")
else:
    # Target the legacy .NET Framework runtime. It might not be necessary, because specifying "coreclr" regardless of
    # Deswik version seemed to work. But the older Deswik versions require .NET Framework 4.7.2 so "netfx" is specified.
    pythonnet.load("netfx")

# Import clr _after_ `pythonnet.load()`.
import clr  # noqa: E402 # Do this after modifying sys.path, so that Deswik-bundled DLLs are prioritized

clr.AddReference("Deswik.Duf")
clr.AddReference("Deswik.Entities")
clr.AddReference("Deswik.Entities.Cad")
clr.AddReference("Deswik.Serialization")
clr.AddReference("Deswik.Core.Structures")
