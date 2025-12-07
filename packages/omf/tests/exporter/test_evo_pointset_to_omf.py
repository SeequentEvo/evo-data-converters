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

from os import path
from uuid import uuid4

import omf
from evo_schemas.components import CategoryAttribute_V1_0_1, CategoryAttribute_V1_1_0
from evo_schemas.objects import Pointset_V1_1_0, Pointset_V1_1_0_Locations, Pointset_V1_2_0

from evo.data_converters.common import create_evo_object_service_and_data_client
from evo.data_converters.omf.exporter import export_omf_pointset
from evo.data_converters.omf.importer import convert_omf
from evo.data_converters.common.test_tools import EvoDataConvertersTestCase


class TestExportOMFPointSet(EvoDataConvertersTestCase):
    def setUp(self) -> None:
        EvoDataConvertersTestCase.setUp(self)

        _, self.data_client = create_evo_object_service_and_data_client(self.workspace_metadata)

        # Convert an OMF file to Evo and use the generated Parquet files to test the exporter
        omf_file = path.join(path.dirname(__file__), "../data/one_of_everything.omf")
        self.evo_object = convert_omf(
            filepath=omf_file, evo_workspace_metadata=self.workspace_metadata, epsg_code=32650, publish_objects=False
        )[1]
        self.evo_object.description = "any description"
        self.assertIsInstance(self.evo_object, Pointset_V1_2_0)

    def test_should_create_expected_omf_pointset_element(self) -> None:
        element = export_omf_pointset(uuid4(), None, self.evo_object, self.data_client)

        self.assertEqual(element.name, self.evo_object.name)
        self.assertEqual(element.description, self.evo_object.description)

        self.assertIsInstance(element.geometry, omf.PointSetGeometry)

        self.assertEqual(len(element.geometry.vertices), 5)

        vertex = element.geometry.vertices[0]
        self.assertAlmostEqual(vertex[0], -1.0)
        self.assertAlmostEqual(vertex[1], -1.0)
        self.assertAlmostEqual(vertex[2], 0.0)

    def test_should_create_expected_omf_vertex_attributes(self) -> None:
        element = export_omf_pointset(uuid4(), None, self.evo_object, self.data_client)

        self.assertEqual(len(element.data), 3)

        mapped_data = element.data[0]
        self.assertIsInstance(mapped_data, omf.MappedData)
        self.assertEqual(mapped_data.location, "vertices")
        self.assertEqual(mapped_data.name, "Categories")

        # Should have the expected indices
        self.assertEqual(len(mapped_data.array), 5)
        self.assertAlmostEqual(mapped_data.array[0], 0)
        self.assertAlmostEqual(mapped_data.array[1], 0)
        self.assertAlmostEqual(mapped_data.array[2], 0)
        self.assertAlmostEqual(mapped_data.array[3], 0)
        self.assertAlmostEqual(mapped_data.array[4], 1)

        # Should have the expected legend
        self.assertEqual(len(mapped_data.legends), 1)
        legend = mapped_data.legends[0]
        self.assertIsInstance(legend, omf.Legend)
        self.assertEqual(len(legend.values), 2)
        self.assertEqual(legend.values[0], "Base")
        self.assertEqual(legend.values[1], "Top")

        vector2_data = element.data[1]
        self.assertIsInstance(vector2_data, omf.Vector2Data)
        self.assertEqual(len(vector2_data.array), 5)
        self.assertAlmostEqual(vector2_data.array[0][0], 1.0)
        self.assertAlmostEqual(vector2_data.array[0][1], 0.0)

        vector3_data = element.data[2]
        self.assertIsInstance(vector3_data, omf.Vector3Data)
        self.assertEqual(len(vector3_data.array), 5)
        self.assertAlmostEqual(vector3_data.array[4][0], 0)
        self.assertAlmostEqual(vector3_data.array[4][1], 0)
        self.assertAlmostEqual(vector3_data.array[4][2], 1.0)

    def test_should_create_expected_omf_pointset_element_from_old_object_schema(self) -> None:
        self.assertIsInstance(self.evo_object.locations.attributes[0], CategoryAttribute_V1_1_0)

        category_attribute = self.evo_object.locations.attributes[0]

        old_category_attribute = CategoryAttribute_V1_0_1(
            name=category_attribute.name,
            table=category_attribute.table,
            values=category_attribute.values,
            nan_description=category_attribute.nan_description,
        )

        evo_object = Pointset_V1_1_0(
            name=self.evo_object.name,
            description=self.evo_object.description,
            uuid=None,
            bounding_box=self.evo_object.bounding_box,
            coordinate_reference_system=self.evo_object.coordinate_reference_system,
            locations=Pointset_V1_1_0_Locations(
                coordinates=self.evo_object.locations.coordinates, attributes=[old_category_attribute]
            ),
        )

        element = export_omf_pointset(uuid4(), None, evo_object, self.data_client)

        self.assertEqual(element.name, evo_object.name)
        self.assertEqual(element.description, evo_object.description)

        self.assertIsInstance(element.geometry, omf.PointSetGeometry)

        self.assertEqual(len(element.geometry.vertices), 5)
        self.assertEqual(len(element.data), 1)

        mapped_data = element.data[0]
        self.assertIsInstance(mapped_data, omf.MappedData)
        self.assertEqual(mapped_data.location, "vertices")
        self.assertEqual(mapped_data.name, "Categories")
        self.assertEqual(len(mapped_data.legends), 1)
        self.assertEqual(len(mapped_data.legends[0].values), 2)
