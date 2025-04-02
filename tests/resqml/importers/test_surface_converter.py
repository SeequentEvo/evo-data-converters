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

import tempfile
from os import path
from unittest import TestCase

import numpy as np
import pandas as pd
import resqpy.model as rqm
import resqpy.property as rqp
from evo_schemas.components import CategoryAttribute_V1_0_1 as CategoryAttribute
from evo_schemas.components import ContinuousAttribute_V1_0_1 as ContinuousAttribute
from evo_schemas.components import IntegerAttribute_V1_0_1 as IntegerAttribute
from numpy.typing import DTypeLike
from resqpy.crs import Crs
from resqpy.surface import PointSet, Surface

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.resqml.importer._attribute_converters import create_category_lookup_and_data
from evo.data_converters.resqml.importer._surface_converter import (
    _convert_attributes,
    _get_crs,
    _get_surface_name,
)
from evo.data_converters.resqml.importer._utils import get_metadata
from evo.data_converters.resqml.importer.conversion_options import ResqmlConversionOptions


class TestSurfaceConverter(TestCase):
    """
    Tests for grid_converter
    """

    MODEL_FILE_NAME = "new_file.epc"

    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        meta_data = EvoWorkspaceMetadata(
            org_id="8ac3f041-b186-41f9-84ba-43d60f8683be",
            workspace_id="2cf1697f-2771-485e-848d-e6674d2ac63f",
            cache_root=self.cache_root_dir.name,
        )
        _, data_client = create_evo_object_service_and_data_client(meta_data)  # pyright: ignore

        self.data_dir = tempfile.TemporaryDirectory()
        model_file = path.join(self.data_dir.name, self.MODEL_FILE_NAME)
        model = rqm.new_model(model_file)

        self.data_client = data_client
        self.model = model
        self.model_file = model_file

    def test_get_surface_name_citation_title_present(self) -> None:
        # Given a surface with a citation title
        EXPECTED = "A test grid"
        grid = Surface(
            self.model,
            title=EXPECTED,
        )

        # Then the surface name will be the grid citation title
        name = _get_surface_name(grid)
        self.assertEqual(EXPECTED, name)

    def test_get_surface_name_citation_title_not_present(self) -> None:
        # Given a surface without a citation title
        surface = Surface(
            self.model,
        )
        EXPECTED = f"Surface-{surface.uuid}"

        # Then the surface name will be "Surface-<uuid>"
        name = _get_surface_name(surface)
        self.assertEqual(EXPECTED, name)

    def test_get_crs_no_model_CRS_and_no_surface_CRS(self) -> None:
        # Given a surface and a model without an epsg_code on the root CRS
        surface = Surface(
            self.model,
        )
        self.model.crs_uuid = None
        surface.crs_uuid = None

        # Then the CRS will be none
        crs = _get_crs(self.model, surface)
        self.assertIsNone(crs)

    def test_get_crs_surface_has_crs(self) -> None:
        # Given a surface with a CRS
        surface_crs = Crs(self.model, epsg_code="3788")
        surface_crs.create_xml()
        surface = Surface(
            self.model,
            crs_uuid=surface_crs.uuid,
        )
        surface.create_xml()

        # Then the surface CRS will be returned
        crs = _get_crs(self.model, surface)
        self.assertEqual(surface_crs, crs)

    def test_get_crs_surface_has_no_crs(self) -> None:
        # Given a surface with no CRS
        surface = Surface(
            self.model,
        )
        surface.crs_uuid = None
        # Don't call create_xml, otherwise an empty CRS will be created

        # And a ROOT CRS
        root_crs = Crs(self.model, epsg_code="2345")
        root_crs.create_xml()  # This assigns the UUID to the CRS
        self.model.crs_uuid = root_crs.uuid  # pyright: ignore

        # Then the ROOT CRS will be returned
        crs = _get_crs(self.model, surface)
        self.assertEqual(root_crs, crs)

    def test_get_metadata(self) -> None:
        # Given a surface with a citation title and an originator
        TITLE = "A test surface"
        ORIGINATOR = "The source of the information"
        surface = Surface(
            self.model,
            title=TITLE,
            originator=ORIGINATOR,
        )
        ResqmlConversionOptions(active_cells_only=True)

        # Then get_metadata returns
        metadata = get_metadata(surface)
        self.assertEqual(TITLE, metadata["resqml"]["name"])
        self.assertEqual(str(surface.uuid), metadata["resqml"]["uuid"])
        self.assertEqual(ORIGINATOR, metadata["resqml"]["originator"])
        self.assertEqual(self.MODEL_FILE_NAME, metadata["resqml"]["epc_filename"])
        # There should be no options
        self.assertNotIn("options", metadata["resqml"])

    def test_get_metadata_empty_values(self) -> None:
        # Given a surface with NO citation title and NO originator
        surface = Surface(
            self.model,
        )
        ResqmlConversionOptions(active_cells_only=True)

        # Then get_metadata returns
        metadata = get_metadata(surface)
        self.assertEqual("", metadata["resqml"]["name"])
        self.assertEqual(str(surface.uuid), metadata["resqml"]["uuid"])
        self.assertEqual("", metadata["resqml"]["originator"])
        self.assertEqual(self.MODEL_FILE_NAME, metadata["resqml"]["epc_filename"])

    def test_convert_properties(self) -> None:
        # Given a Surface created from a random point set
        crs = Crs(self.model, epsg_code="3788")
        crs.create_xml()
        point_set = PointSet(self.model, crs_uuid=crs.uuid, points_array=np.random.rand(90, 3).astype(np.float64))
        surface = Surface(self.model, crs_uuid=crs.uuid, point_set=point_set)
        self.assertTrue(surface.triangle_count() > 0)
        surface.create_xml()

        # And an unknown property with no data
        rqp.Property(self.model)
        # And a discrete node property
        DISCRETE_NAME = "Discrete Property Name"
        self.discrete_property(surface, "triangles", DISCRETE_NAME)
        # And a points node property
        POINTS_NAME = "Points Property Name"
        self.points_property(surface, "triangles", POINTS_NAME)
        # And a continuous node property
        CONTINUOUS_NAME = "Continuous Property Name"
        self.continuous_property(surface, "triangles", CONTINUOUS_NAME)
        # And a categorical node property
        CATEGORICAL_NAME = "Categorical Property Name"
        self.categorical_property(surface, "triangles", CATEGORICAL_NAME)
        # And a categorical triangle property
        NODES_CATEGORICAL_NAME = "Categorical Nodes Property Name"
        self.categorical_property(surface, "nodes", NODES_CATEGORICAL_NAME)

        # When the properties are converted
        (node_attributes, face_attributes, triangle_attributes) = _convert_attributes(
            self.model, surface, self.data_client
        )  # pyright: ignore

        # There should be 3 triangle attributes,
        # There should be 1 node attribute,
        # the unknown and points attributes and edge property
        # should not have been converted
        self.assertEqual(3, len(triangle_attributes))

        # And there is an IntegerAttribute, a ContinuousAttribute
        #     and a CategoricalAttribute with the expected names
        # for the node attributes
        matched = set()
        for a in triangle_attributes:
            # Should only see one instance of each name in the triangle attributes
            self.assertFalse(a.name in matched)  # pyright: ignore
            matched.add(a.name)  # pyright: ignore
            match a:
                case IntegerAttribute():
                    self.assertEqual(DISCRETE_NAME, a.name)
                case ContinuousAttribute():
                    self.assertEqual(CONTINUOUS_NAME, a.name)
                case CategoryAttribute():
                    self.assertEqual(CATEGORICAL_NAME, a.name)
                case _:
                    self.fail(f"Unexpected attribute type {type(a).__name__} for attribute {a}")
        # We should have seen all the expected attributes
        self.assertEqual(3, len(matched))

        # And there is a CategoricalAttribute with the expected name
        # for the node attributes
        matched = set()
        for a in node_attributes:
            # Should only see one instance of each name
            self.assertFalse(a.name in matched)  # pyright: ignore
            matched.add(a.name)  # pyright: ignore
            match a:
                case CategoryAttribute():
                    self.assertEqual(NODES_CATEGORICAL_NAME, a.name)
                case _:
                    self.fail(f"Unexpected attribute type {type(a).__name__} for attribute {a}")
        # We should have seen all the expected attributes
        self.assertEqual(1, len(matched))

    def categorical_property(self, surface: Surface, indexable: str, name: str) -> rqp.Property:
        """Build a categorical property"""

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
        create_category_lookup_and_data(df)

        # randomly assign a category to each indexable element
        if indexable == "nodes":
            array_values = np.random.randint(0, 3, surface.node_count())
        else:
            array_values = np.random.randint(0, 3, surface.triangle_count())
        property = rqp.Property.from_array(
            parent_model=self.model,
            cached_array=array_values,
            discrete=True,
            source_info="test data",
            property_kind="CategoricalProperty",
            indexable_element=indexable,
            keyword=name,
            support_uuid=surface.uuid,
            string_lookup_uuid=string_lookup.uuid,
            uom="m",
        )
        self.assertTrue(property.is_categorical())
        return property

    def continuous_property(self, surface: Surface, indexable: str, name: str) -> rqp.Property:
        """Build a continuous property"""
        property = rqp.Property.from_array(
            parent_model=self.model,
            cached_array=np.random.random(surface.triangle_count()).astype(np.float64),
            source_info="test data",
            property_kind="ContinuousProperty",
            discrete=False,
            indexable_element=indexable,
            keyword=name,
            support_uuid=surface.uuid,
            uom="m",
        )
        self.assertTrue(property.is_continuous())
        return property

    def points_property(self, surface: Surface, indexable: str, name: str) -> rqp.Property:
        """Create a points property"""
        property = rqp.Property.from_array(
            parent_model=self.model,
            cached_array=np.random.randn(surface.triangle_count(), 3),
            points=True,
            source_info="test data",
            property_kind="PointsProperty",
            indexable_element=indexable,
            keyword=name,
            support_uuid=surface.uuid,
            uom="m",
        )
        self.assertTrue(property.is_points())
        return property

    def discrete_property(
        self, surface: Surface, indexable: str, name: str, type: DTypeLike = np.int64
    ) -> rqp.Property:
        """Create a discrete property"""
        property = rqp.Property.from_array(
            parent_model=self.model,
            cached_array=np.random.random(surface.triangle_count()).astype(type),
            discrete=True,
            source_info="test data",
            property_kind="DiscreteProperty",
            indexable_element=indexable,
            keyword=name,
            support_uuid=surface.uuid,
            uom="m",
        )
        self.assertFalse(property.is_points() or property.is_categorical() or property.is_continuous())
        return property
