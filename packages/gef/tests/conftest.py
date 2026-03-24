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

import os

import numpy
import pandas
import pyarrow.parquet as pq
import pytest

from evo.data_converters.common import (
    EvoWorkspaceMetadata,
    create_evo_object_service_and_data_client,
)


# TODO - Merge with duf test fixture
@pytest.fixture(scope="session")
def evo_metadata(tmp_path_factory):
    cache_root_dir = tmp_path_factory.mktemp("temp", numbered=False)
    return EvoWorkspaceMetadata(
        workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae",
        cache_root=cache_root_dir.name,
    )


# TODO - Merge with duf test fixture
class TestDataClient:
    def __init__(self, data_client):
        self.data_client = data_client

    def __getattr__(self, name):
        return getattr(self.data_client, name)

    def load_table(self, table):
        chunks_parquet_file = os.path.join(str(self.data_client.cache_location), table.data)
        return pq.read_table(chunks_parquet_file)

    def load_columns(self, table) -> list:
        table_pd = self.load_table(table).to_pandas()
        return [table_pd[col].to_numpy() for col in table_pd.columns]

    def load_category(self, attr_go):
        lookup_df = self.load_table(attr_go.table).to_pandas().set_index("key")
        values_df = self.load_table(attr_go.values).to_pandas()

        lookup_values_col_name = lookup_df.columns[0]
        value_keys = values_df[values_df.columns[0]]

        def do_lookup(k):
            return lookup_df.loc[k, lookup_values_col_name]

        return numpy.vectorize(do_lookup)(value_keys)

    def _load_attr(self, attr):
        match attr.attribute_type:
            case "string":
                return self.load_table(attr.values).to_pandas()
            case "scalar":
                # TODO - deal with nan
                return self.load_table(attr.values).to_pandas()
            case "date_time":
                return self.load_table(attr.values).to_pandas()
            case _:
                raise NotImplementedError(attr.attribute_type)

    def load_attributes(self, attrs):
        columns = [self._load_attr(attr) for attr in attrs]
        table = pandas.concat(columns, axis=1)
        table.columns = [attr.name for attr in attrs]
        return table


# TODO - Merge with duf test fixture
@pytest.fixture(scope="session")
def data_client(evo_metadata) -> TestDataClient:
    _, data_client = create_evo_object_service_and_data_client(evo_metadata)
    return TestDataClient(data_client)
