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

""" """

import tempfile
from os import path
from unittest import TestCase

import numpy as np
import numpy.typing as npt
import pandas as pd
import pyarrow.parquet as pq
import resqpy.grid as rqg
import resqpy.model as rqm
import resqpy.olio.vector_utilities as vec
import resqpy.property as rqp
from evo_schemas.components import CategoryAttribute_V1_0_1 as CategoryAttribute
from evo_schemas.components import ContinuousAttribute_V1_0_1 as ContinuousAttribute
from evo_schemas.components import IntegerAttribute_V1_0_1 as IntegerAttribute
from evo_schemas.components import VectorAttribute_V1_0_0 as VectorAttribute
from pandas import DataFrame

from evo.data_converters.common.evo_client import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.resqml.importer._attribute_converters import (
    convert_categorical_property,
    convert_continuous_property,
    convert_discrete_property,
    convert_points_property,
    create_category_lookup_and_data,
)


class TestConvertAttributeProperties(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        _, self.data_client = create_evo_object_service_and_data_client(
            EvoWorkspaceMetadata(
                org_id="8ac3f041-b186-41f9-84ba-43d60f8683be",
                workspace_id="2cf1697f-2771-485e-848d-e6674d2ac63f",
                cache_root=self.cache_root_dir.name,
            )
        )
        self.data_dir = tempfile.TemporaryDirectory()
        model_file = path.join(self.data_dir.name, "new_file.epc")
        self.model = rqm.new_model(model_file)
        self.grid_extent_kji = (2, 3, 4)
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=self.grid_extent_kji,
            origin=(0.0, 0.0, 1000.0),
            dxyz=(100.0, 100.0, -10.0),
            title="test grid",
        )
        grid.k_direction_is_down = False
        grid.grid_is_right_handed = not grid.grid_is_right_handed
        grid.write_hdf5()
        grid.create_xml(
            add_relationships=False, write_active=False, write_geometry=False, add_cell_length_properties=False
        )
        self.grid = grid

        self.DISCRETE_NULL_VALUE = -10000
        self.discrete_property = rqp.Property.from_array(
            self.model,
            np.random.random(self.grid.extent_kji).astype(np.int64),
            discrete=True,
            source_info="test data",
            property_kind="DiscreteProperty",
            indexable_element="cells",
            keyword="Discrete Property Test",
            support_uuid=self.grid.uuid,
            uom="m",
            null_value=self.DISCRETE_NULL_VALUE,
        )
        self.assertTrue(self.discrete_property.minimum_value() > self.DISCRETE_NULL_VALUE)

        self.continuous_property = rqp.Property.from_array(
            self.model,
            np.random.random(self.grid.extent_kji).astype(np.float64),
            discrete=False,
            source_info="test data",
            property_kind="ContinuousProperty",
            indexable_element="cells",
            keyword="Continuous Property Test",
            support_uuid=self.grid.uuid,
            uom="m",
            null_value=np.NaN,
        )

        # create a set of category labels
        string_lookup = rqp.StringLookup(self.model)
        string_lookup.set_string("0", "sandstone")
        string_lookup.set_string("1", "shale")
        string_lookup.set_string("2", "limestone")
        string_lookup.create_xml()

        # save the RESQML lookup table for tests
        lookup_as_dict = string_lookup.as_dict()
        indices = list(lookup_as_dict.keys())
        names = lookup_as_dict.values()
        df = pd.DataFrame({"data": names, "index": indices})
        df.set_index("index", inplace=True)
        self.categorical_property_lookup_df, _ = create_category_lookup_and_data(df)

        self.CATEGORICAL_NULL_VALUE = -1
        # randomly assign a category to each cell
        self.categorical_property = rqp.Property.from_array(
            self.model,
            np.random.randint(0, 3, size=self.grid.extent_kji),
            discrete=True,
            source_info="test data",
            property_kind="CategoricalProperty",
            indexable_element="cells",
            keyword="Categorical Property Test",
            support_uuid=self.grid.uuid,
            string_lookup_uuid=string_lookup.uuid,
            uom="m",
            null_value=self.CATEGORICAL_NULL_VALUE,
        )

        # Points Property
        if self.grid.property_collection is None:
            self.grid.property_collection = rqp.PropertyCollection(support=grid)
        pc = self.grid.property_collection

        # Define shape to be the grid plus x,y,z points
        self.points_extent = tuple(list(self.grid_extent_kji) + [3])

        # Create a static points property with some random stress data
        stress = vec.unit_vectors(np.random.random(self.points_extent) + 0.1)
        pc.add_cached_array_to_imported_list(
            cached_array=stress,
            source_info="random stress vectors",
            keyword="stress direction",
            uom="m",
            property_kind="length",
            indexable_element="cells",
            points=True,
        )
        pc.write_hdf5_for_imported_list()
        pc.create_xml_for_imported_list_and_add_parts_to_model()
        self.model.store_epc()

        self.points_part = pc.singleton(citation_title="stress direction", points=True)
        assert self.points_part is not None
        stress_uuid = pc.uuid_for_part(self.points_part)
        self.points_property = rqp.Property(self.model, uuid=stress_uuid)
        assert self.points_property is not None
        assert self.points_property.is_points()

    def get_data_from_parquet_file(self, pq_hash: str) -> DataFrame:
        return pq.read_table(path.join(self.data_client.cache_location, pq_hash)).to_pandas()

    def check_data_is_valid(self, resqml_data: npt.NDArray, go_data: DataFrame) -> bool:
        flattened_values = resqml_data.flatten()
        resqml_data_as_df = pd.DataFrame(flattened_values, columns=["data"])
        self.assertEqual(resqml_data_as_df.size, go_data.size)
        for resqml, go in zip(resqml_data_as_df, go_data):
            self.assertEqual(resqml, go)
        return True

    def check_lookup_table_is_valid(self, resqml_lookup_df: DataFrame, go_lookup_df: DataFrame) -> bool:
        self.assertEqual(resqml_lookup_df.size, go_lookup_df.size)
        self.assertTrue(np.all(resqml_lookup_df == go_lookup_df))
        return True

    def test_convert_discrete_property(self) -> None:
        go = convert_discrete_property(self.discrete_property, self.data_client)
        self.assertIsInstance(go, IntegerAttribute)
        self.assertEqual(go.name, self.discrete_property.title)
        self.check_data_is_valid(self.discrete_property.array_ref(), self.get_data_from_parquet_file(go.values.data))

    def test_convert_discrete_property_null_values(self) -> None:
        self.discrete_property.array_ref()[1][1][1] = self.DISCRETE_NULL_VALUE
        go = convert_discrete_property(self.discrete_property, self.data_client)
        self.assertIsInstance(go, IntegerAttribute)
        self.assertEqual(go.name, self.discrete_property.title)
        self.check_data_is_valid(self.discrete_property.array_ref(), self.get_data_from_parquet_file(go.values.data))

    def test_convert_discrete_property_with_masked_data(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        self.assertLess(
            self.discrete_property.array_ref(masked=True)[idx_valid].size,
            self.discrete_property.array_ref().size,
        )
        go = convert_discrete_property(self.discrete_property, self.data_client, idx_valid)
        self.assertIsInstance(go, IntegerAttribute)
        self.assertEqual(go.name, self.discrete_property.title)
        self.check_data_is_valid(
            self.discrete_property.array_ref(masked=True)[idx_valid],
            self.get_data_from_parquet_file(go.values.data),
        )

    def test_convert_discrete_property_with_masked_data_and_null_values(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        self.discrete_property.array_ref()[1] = self.DISCRETE_NULL_VALUE
        self.discrete_property.array_ref()[0][0][0] = self.DISCRETE_NULL_VALUE
        idx_valid[1] = True
        self.assertLess(
            self.discrete_property.array_ref(masked=True)[idx_valid].size,
            self.discrete_property.array_ref().size,
        )
        go = convert_discrete_property(self.discrete_property, self.data_client, idx_valid)
        self.assertIsInstance(go, IntegerAttribute)
        self.assertEqual(go.name, self.discrete_property.title)
        self.check_data_is_valid(
            self.discrete_property.array_ref(masked=True)[idx_valid],
            self.get_data_from_parquet_file(go.values.data),
        )
        null_value = self.discrete_property.array_ref()[0][0][0]
        self.assertEqual(self.DISCRETE_NULL_VALUE, null_value)
        self.assertEqual(self.DISCRETE_NULL_VALUE, go.nan_description.values[0])

    def test_convert_continuous_property(self) -> None:
        go = convert_continuous_property(self.continuous_property, self.data_client)
        self.assertIsInstance(go, ContinuousAttribute)
        self.assertEqual(go.name, self.continuous_property.title)
        self.check_data_is_valid(self.continuous_property.array_ref(), self.get_data_from_parquet_file(go.values.data))

    def test_convert_continuous_property_with_null_value(self) -> None:
        self.continuous_property.array_ref()[1][1][1] = np.NaN
        go = convert_continuous_property(self.continuous_property, self.data_client)
        self.assertIsInstance(go, ContinuousAttribute)
        self.assertEqual(go.name, self.continuous_property.title)
        self.check_data_is_valid(self.continuous_property.array_ref(), self.get_data_from_parquet_file(go.values.data))

    def test_convert_continuous_property_with_masked_data(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        self.assertLess(
            self.continuous_property.array_ref(masked=True)[idx_valid].size,
            self.continuous_property.array_ref().size,
        )
        go = convert_continuous_property(self.continuous_property, self.data_client, idx_valid)
        self.assertIsInstance(go, ContinuousAttribute)
        self.assertEqual(go.name, self.continuous_property.title)
        self.check_data_is_valid(
            self.continuous_property.array_ref(masked=True, exclude_null=True)[idx_valid],
            self.get_data_from_parquet_file(go.values.data),
        )

    def test_convert_continuous_property_with_masked_data_and_null_value(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        idx_valid[1] = True
        self.continuous_property.array_ref()[0][0][0] = np.NaN
        self.assertLess(
            self.continuous_property.array_ref(masked=True)[idx_valid].size,
            self.continuous_property.array_ref().size,
        )
        go = convert_continuous_property(self.continuous_property, self.data_client, idx_valid)
        self.assertIsInstance(go, ContinuousAttribute)
        self.assertEqual(go.name, self.continuous_property.title)
        self.check_data_is_valid(
            self.continuous_property.array_ref(masked=True, exclude_null=True)[idx_valid],
            self.get_data_from_parquet_file(go.values.data),
        )
        self.assertTrue(np.isnan(self.continuous_property.array_ref()[0][0][0]))
        self.assertEqual(0, len(go.nan_description.values))

    def test_categorical_property(self) -> None:
        go = convert_categorical_property(self.model, self.categorical_property, self.data_client)
        self.assertIsInstance(go, CategoryAttribute)
        self.assertEqual(go.name, self.categorical_property.title)
        self.check_data_is_valid(self.categorical_property.array_ref(), self.get_data_from_parquet_file(go.values.data))
        self.check_lookup_table_is_valid(
            self.categorical_property_lookup_df, self.get_data_from_parquet_file(go.table.data)
        )

    def test_categorical_property_with_null_values(self) -> None:
        self.discrete_property.array_ref()[1][1][1] = self.CATEGORICAL_NULL_VALUE
        go = convert_categorical_property(self.model, self.categorical_property, self.data_client)
        self.assertIsInstance(go, CategoryAttribute)
        self.assertEqual(go.name, self.categorical_property.title)
        self.check_data_is_valid(self.categorical_property.array_ref(), self.get_data_from_parquet_file(go.values.data))
        self.check_lookup_table_is_valid(
            self.categorical_property_lookup_df, self.get_data_from_parquet_file(go.table.data)
        )

    def test_categorical_property_with_masked_data(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        self.assertLess(
            self.categorical_property.array_ref(masked=True)[idx_valid].size,
            self.categorical_property.array_ref().size,
        )
        go = convert_categorical_property(self.model, self.categorical_property, self.data_client, idx_valid)
        self.assertIsInstance(go, CategoryAttribute)
        self.assertEqual(go.name, self.categorical_property.title)
        self.check_data_is_valid(
            self.categorical_property.array_ref(masked=True)[idx_valid],
            self.get_data_from_parquet_file(go.values.data),
        )
        self.check_lookup_table_is_valid(
            self.categorical_property_lookup_df, self.get_data_from_parquet_file(go.table.data)
        )

    def test_categorical_property_with_masked_data_and_null_values(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        idx_valid[1] = True
        self.categorical_property.array_ref()[0][0][0] = self.CATEGORICAL_NULL_VALUE
        self.assertLess(
            self.categorical_property.array_ref(masked=True)[idx_valid].size,
            self.categorical_property.array_ref().size,
        )
        go = convert_categorical_property(self.model, self.categorical_property, self.data_client, idx_valid)
        self.assertIsInstance(go, CategoryAttribute)
        self.assertEqual(go.name, self.categorical_property.title)
        self.check_data_is_valid(
            self.categorical_property.array_ref(masked=True)[idx_valid],
            self.get_data_from_parquet_file(go.values.data),
        )
        self.check_lookup_table_is_valid(
            self.categorical_property_lookup_df, self.get_data_from_parquet_file(go.table.data)
        )
        null_value = self.categorical_property.array_ref()[0][0][0]
        self.assertEqual(self.CATEGORICAL_NULL_VALUE, null_value)
        self.assertEqual(self.CATEGORICAL_NULL_VALUE, go.nan_description.values[0])

    def test_convert_points_property(self) -> None:
        go = convert_points_property(self.points_property, self.data_client)
        self.assertIsInstance(go, VectorAttribute)
        self.assertEqual(go.name, self.points_property.title)
        prop_data = self.points_property.array_ref().reshape(-1, 3)
        go_data = self.get_data_from_parquet_file(go.values.data).to_numpy()
        self.assertEqual(prop_data.all(), go_data.all())

    def test_convert_points_property_with_null_value(self) -> None:
        self.points_property.array_ref()[1][1][1][1] = np.NaN
        go = convert_points_property(self.points_property, self.data_client)
        self.assertIsInstance(go, VectorAttribute)
        self.assertEqual(go.name, self.points_property.title)
        prop_data = self.points_property.array_ref().reshape(-1, 3)
        go_data = self.get_data_from_parquet_file(go.values.data).to_numpy()
        self.assertEqual(prop_data.all(), go_data.all())

    def test_convert_points_property_with_masked_data(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        self.assertLess(
            self.points_property.array_ref(masked=True)[idx_valid].size,
            self.points_property.array_ref().size,
        )
        go = convert_points_property(self.points_property, self.data_client, idx_valid)
        self.assertIsInstance(go, VectorAttribute)
        self.assertEqual(go.name, self.points_property.title)
        prop_data = self.points_property.array_ref(masked=True, exclude_null=True)[idx_valid].reshape(-1, 3)
        go_data = self.get_data_from_parquet_file(go.values.data).to_numpy()
        self.assertEqual(prop_data.all(), go_data.all())

    def test_convert_points_property_with_masked_data_and_null_values(self) -> None:
        idx_valid = np.random.choice([True, False], self.grid.extent_kji)
        idx_valid[1, 1, 1] = True
        self.points_property.array_ref()[0][0][0] = (np.NaN, np.NaN, np.NaN)
        self.assertLess(
            self.points_property.array_ref(masked=True)[idx_valid].size,
            self.points_property.array_ref().size,
        )
        go = convert_points_property(self.points_property, self.data_client, idx_valid)
        self.assertIsInstance(go, VectorAttribute)
        self.assertEqual(go.name, self.points_property.title)
        prop_data = self.points_property.array_ref(masked=True, exclude_null=True)[idx_valid].reshape(-1, 3)
        go_data = self.get_data_from_parquet_file(go.values.data).to_numpy()
        self.assertEqual(prop_data.all(), go_data.all())
