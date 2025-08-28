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


if platform.system() != "Windows":
    raise RuntimeError("This script is only supported on Windows.")

if (deswik_path := os.getenv("DESWIK_PATH")) is None:
    if not os.path.exists(r"C:\Program Files\Deswik"):
        raise RuntimeError("Deswik.Suite is not installed. Please install Deswik.Suite to run this script.")

    installs = [pth for pth in os.listdir(r"C:\Program Files\Deswik") if "Suite" in pth]
    if not installs:
        raise RuntimeError("Deswik.Suite is not installed. Please install Deswik.Suite to run this script.")

    # Sort by version
    def by_version(path):
        version = path.split(" ")[-1]
        year, month = version.split(".")
        return int(year), int(month)

    deswik_path = os.path.join(r"C:\Program Files\Deswik", sorted(installs, key=by_version)[-1])

logger = evo.logging.getLogger("data_converters")
logger.debug("Looking for Deswik DLLs in: %s", deswik_path)

sys.path.insert(0, deswik_path)

import clr  # noqa: E402 # Do this after modifying sys.path, so that Deswik-bundled DLLs are prioritized

clr.AddReference("Deswik.Duf")
clr.AddReference("Deswik.Entities")
clr.AddReference("Deswik.Entities.Cad")
clr.AddReference("Deswik.Serialization")
clr.AddReference("Deswik.Core.Structures")
