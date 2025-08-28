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

import evo.logging
from evo.data_converters.duf.common import DUFWrapper, ObjectCollector

logger = evo.logging.getLogger("data_converters")


class DUFCollectorContext:
    def __init__(self, filepath: str):
        self._collector = ObjectCollector()

        with DUFWrapper(filepath, self._collector) as instance:
            instance.LoadEverything()

    @property
    def collector(self) -> ObjectCollector:
        return self._collector

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"Error during DUF collection: {exc_val}")
        return False
