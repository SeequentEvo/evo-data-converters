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
import pathlib

import pyarrow as pa


class LocalDataClient:
    """
    A data client which saves to a local folder.
    """

    def __init__(self, save_dir: str):
        """
        Initalizes the local data client.

        :param save_dir: The target directory of the data client. If it does not exist it will be created.
        """
        path = pathlib.Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        self.save_dir = path if path.is_dir() else pathlib.Path(pathlib.Path.cwd(), "local_data")

    def save_table(self, table: pa.Table) -> dict:
        """Save a pyarrow table to a file, returning the table info as a dictionary.

        :param table: The pyarrow table to save.

        :return: Information about the saved table.

        :raises TableFormatError: If the provided table does not match this format.
        :raises StorageFileNotFoundError: If the destination does not exist or is not a directory.
        """
        from evo.objects.utils.table_formats import get_known_format

        known_format = get_known_format(table)
        table_info = known_format.save_table(table=table, destination=pathlib.Path(self.save_dir))
        return table_info
