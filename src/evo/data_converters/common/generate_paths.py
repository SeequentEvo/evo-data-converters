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

from collections import defaultdict
from pathlib import PurePosixPath

from evo_schemas.components import BaseSpatialDataProperties_V1_0_1


def generate_paths(object_models: list[BaseSpatialDataProperties_V1_0_1], path_prefix: str = "") -> list[str]:
    """
    Generates a list of paths where each object will be uploaded to.

    The path for each object follows the pattern of: "<path_prefix>/<object_name>{_<n>}.json"

    For example: "myproject/mysite/myobject_2.json"
    """
    count: defaultdict[str, int] = defaultdict(int)
    paths: list[str] = []

    for obj in object_models:
        obj_path = obj.name + ".json"

        if (n := count[obj.name]) > 0:
            if n == 1:
                # must rename the existing path
                paths[paths.index(obj_path)] = obj.name + "_1.json"

            obj_path = f"{obj.name}_{n + 1}.json"

        paths.append(obj_path)
        count[obj.name] += 1

    if path_prefix:
        # prepend in-place
        for i, obj_path in enumerate(paths):
            paths[i] = str(PurePosixPath(path_prefix, obj_path)).lstrip("/")

    return paths
