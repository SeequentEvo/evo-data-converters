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
import pyarrow.parquet as pq
import resqpy.crs as rpc
import resqpy.grid as rqg
import resqpy.model as rqm
import resqpy.property as rqp
from evo_schemas.components import CategoryAttribute_V1_0_1 as CategoryAttribute
from evo_schemas.components import ContinuousAttribute_V1_0_1 as ContinuousAttribute
from evo_schemas.components import IntegerAttribute_V1_0_1 as IntegerAttribute
from evo_schemas.components import VectorAttribute_V1_0_0 as VectorAttribute
from numpy.typing import DTypeLike
from resqpy.time_series import TimeSeries

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.resqml.importer._attribute_converters import create_category_lookup_and_data
from evo.data_converters.resqml.importer._grid_converter import (
    _build_actnum,
    _convert_attributes,
    _get_crs,
    _get_grid_name,
    _get_metadata,
    _is_discrete,
)
from evo.data_converters.resqml.importer.conversion_options import ResqmlConversionOptions


class TestGridConverter(TestCase):
    """
    Tests for grid_converter
    """

    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        meta_data = EvoWorkspaceMetadata(
            org_id="8ac3f041-b186-41f9-84ba-43d60f8683be",
            workspace_id="2cf1697f-2771-485e-848d-e6674d2ac63f",
            cache_root=self.cache_root_dir.name,
        )
        _, data_client = create_evo_object_service_and_data_client(meta_data)
        self.data_dir = tempfile.TemporaryDirectory()
        model_file = path.join(self.data_dir.name, "new_file.epc")
        model = rqm.new_model(model_file)

        self.data_client = data_client
        self.model = model
        self.model_file = model_file

    def test_get_grid_name_citation_title_present(self) -> None:
        # Given a grid with a citation title
        EXPECTED = "A test grid"
        grid = rqg.RegularGrid(
            self.model,
            title=EXPECTED,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
        )

        # Then the grid name will be the grid citation title
        name = _get_grid_name(grid)
        self.assertEqual(EXPECTED, name)

    def test_get_grid_name_citation_title_None(self) -> None:
        # Given a grid without a citation title
        grid = rqg.RegularGrid(
            self.model,
            title=None,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
        )
        grid.title = None
        EXPECTED = "Grid-" + str(grid.uuid)

        # Then the grid name will be the default name
        name = _get_grid_name(grid)
        self.assertEqual(EXPECTED, name)

    def test_get_crs_no_crs_on_grid(self) -> None:
        # Given a grid without a coordinate reference system.
        grid = rqg.RegularGrid(
            self.model,
            title=None,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
        )

        # Then the default code is used
        crs = _get_crs(self.model, grid, 5519)
        self.assertEqual(5519, crs.epsg_code)

    def test_get_crs_crs_on_grid(self) -> None:
        # Given a grid with a CRS
        rp_crs = rpc.Crs(self.model, epsg_code="3788")
        rp_crs.create_xml()
        grid = rqg.RegularGrid(
            self.model, title=None, extent_kji=(10, 20, 25), dxyz=(100.0, 125.0, 10.0), crs_uuid=rp_crs.uuid
        )
        grid.crs = rp_crs

        # Then the grid crs EPSG code is used
        crs = _get_crs(self.model, grid, 5519)
        self.assertEqual(3788, crs.epsg_code)

    def test_get_crs_crs_on_grid_with_no_epsg_code_and_no_root_crs(self) -> None:
        # Given a model without a root CRS
        model_file = path.join(self.data_dir.name, "another_new_file.epc")
        model = rqm.new_model(model_file)
        # and Given a grid with a CRS without an EPSG code
        rp_crs = rpc.Crs(model, epsg_code="3788")
        rp_crs.epsg_code = None
        rp_crs.create_xml()
        grid = rqg.RegularGrid(
            model, title=None, extent_kji=(10, 20, 25), dxyz=(100.0, 125.0, 10.0), crs_uuid=rp_crs.uuid
        )
        grid.crs = rp_crs

        # Then the default EPSG code is used
        crs = _get_crs(model, grid, 5519)
        self.assertEqual(5519, crs.epsg_code)

    def test_get_crs_crs_on_grid_with_no_epsg_code_and_with_root_crs(self) -> None:
        # Given a model with a root CRS
        model_file = path.join(self.data_dir.name, "another_new_file.epc")
        model = rqm.new_model(model_file)
        crs = rpc.Crs(model, epsg_code="23304")
        crs.create_xml()
        model.crs_uuid = crs.uuid  # pyright: ignore
        # and Given a grid with a CRS without an EPSG code
        rp_crs = rpc.Crs(model, epsg_code="3788")
        rp_crs.epsg_code = None
        rp_crs.create_xml()
        grid = rqg.RegularGrid(
            model, title=None, extent_kji=(10, 20, 25), dxyz=(100.0, 125.0, 10.0), crs_uuid=rp_crs.uuid
        )
        grid.crs = rp_crs

        # Then the default EPSG code is used
        crs = _get_crs(model, grid, 5519)
        self.assertEqual(23304, crs.epsg_code)

    def test_get_crs_crs_on_grid_with_no_crs(self) -> None:
        # Given a grid without a CRS
        grid = rqg.RegularGrid(
            self.model,
            title=None,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        grid.crs = None  # pyright: ignore

        # Then the grid default EPSG code is used
        crs = _get_crs(self.model, grid, 5519)
        self.assertEqual(5519, crs.epsg_code)

    def test_build_actnum(self) -> None:
        grid = rqg.RegularGrid(
            self.model,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
            crs_uuid=self.model.uuid(obj_type="Local3dDepthCrs"),
            title="BLOCK GRID",
        )

        grid.inactive = np.full((grid.nk, grid.nj, grid.ni), False)  # pyright: ignore
        grid.inactive[4, 5, 6] = True  # pyright: ignore

        actnum = _build_actnum(grid, self.data_client)

        parquet_file = path.join(str(self.data_client.cache_location), actnum.values.data)  # pyright: ignore

        # ACTNUM is saved as a single dimension representation of a 3D array in row major order
        # so lets calculate the index of (4, 5, 6) in that array
        #       i   ni    j    nj   k
        index = 6 + 25 * (5 + (20 * 4))

        active = pq.read_table(parquet_file)
        # Ensure all points except (4, 5, 6) are active
        for i in range(0, len(active)):
            if i != index:
                self.assertEqual("1", str(active[0][i]))
        # And ensure that (4, 5, 6) is tagged as inactive
        self.assertEqual("0", str(active[0][index]))

    def test_convert_attributes_grid_with_no_properties(self) -> None:
        # Given a grid with no properties
        grid = rqg.RegularGrid(
            self.model,
            title=None,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        grid.property_collection = None  # pyright: ignore

        # Then _convert_attributes returns an empty list
        attributes = _convert_attributes(self.model, grid, self.data_client, None)  # pyright: ignore
        self.assertEqual(0, len(attributes))

    def test_get_metadata_no_title_uuid_originator_default_options(self) -> None:
        # Given a grid with no title or uuid or originator
        grid = rqg.RegularGrid(
            self.model,
            title=None,
            uuid=None,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        # Suppress the default of "ROOT"
        grid.title = None  # pyright: ignore
        # Suppress the generation of a UUID
        grid.uuid = None  # pyright: ignore

        # and default options
        options = ResqmlConversionOptions()

        # Then _get_metadata returns
        metadata = _get_metadata(grid, options)
        self.assertEqual("", metadata["resqml"]["name"])
        self.assertEqual("", metadata["resqml"]["uuid"])
        self.assertEqual("", metadata["resqml"]["originator"])
        self.assertEqual("True", metadata["resqml"]["options"]["active_cells_only"])  # pyright: ignore

    def test_get_metadata(self) -> None:
        # Given a grid
        TITLE = "The grid title"
        ORIGINATOR = "The grid originator"
        grid = rqg.RegularGrid(
            self.model,
            title=TITLE,
            originator=ORIGINATOR,
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        # and active_cells_only set false
        options = ResqmlConversionOptions(active_cells_only=False)

        # Then _get_metadata returns
        metadata = _get_metadata(grid, options)
        self.assertEqual(TITLE, metadata["resqml"]["name"])
        self.assertEqual(ORIGINATOR, metadata["resqml"]["originator"])
        self.assertEqual(str(grid.uuid), metadata["resqml"]["uuid"])
        self.assertEqual("new_file.epc", metadata["resqml"]["epc_filename"])
        self.assertEqual("False", metadata["resqml"]["options"]["active_cells_only"])  # pyright: ignore

    def test_is_discrete_empty_property(self) -> None:
        # Given a property with no data
        property = rqp.Property(self.model)
        # It should not be discrete
        self.assertFalse(_is_discrete(property))

    def test_is_discrete_signed_discrete_property(self) -> None:
        # Given a grid
        grid = rqg.RegularGrid(
            self.model,
            title="test_grid",
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        grid.write_hdf5()
        grid.create_xml(
            add_relationships=False, write_active=False, write_geometry=False, add_cell_length_properties=False
        )
        # And a discrete property, with signed integer values
        property = self.discrete_property(grid, "Signed", np.int32)

        # Then
        self.assertTrue(_is_discrete(property))

    def test_is_discrete_unsigned_discrete_property(self) -> None:
        # Given a grid
        grid = rqg.RegularGrid(
            self.model,
            title="test_grid",
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        grid.write_hdf5()
        grid.create_xml(
            add_relationships=False, write_active=False, write_geometry=False, add_cell_length_properties=False
        )
        # And a discrete property, with an unsigned integer type
        property = self.discrete_property(grid, "Unsigned", np.uint32)
        # Then
        self.assertTrue(_is_discrete(property))

    def test_is_discrete_continuous_property(self) -> None:
        # Given a grid
        grid = rqg.RegularGrid(
            self.model,
            title="test_grid",
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        grid.write_hdf5()
        grid.create_xml(
            add_relationships=False, write_active=False, write_geometry=False, add_cell_length_properties=False
        )
        # And a continuous property
        property = self.continuous_property(grid, "Continuous Property")
        # Then
        self.assertFalse(_is_discrete(property))

    def test_is_discrete_categorical_property(self) -> None:
        # Given a grid
        grid = rqg.RegularGrid(
            self.model,
            title="test_grid",
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        grid.write_hdf5()
        grid.create_xml(
            add_relationships=False, write_active=False, write_geometry=False, add_cell_length_properties=False
        )

        # And a categorical property
        property = self.categorical_property(grid, "A property")
        # Then
        self.assertFalse(_is_discrete(property))

    def test_convert_properties(self) -> None:
        # Given a grid
        grid = rqg.RegularGrid(
            self.model,
            title="test_grid",
            extent_kji=(10, 20, 25),
            dxyz=(100.0, 125.0, 10.0),
        )
        grid.write_hdf5()
        grid.create_xml(
            add_relationships=False, write_active=False, write_geometry=False, add_cell_length_properties=False
        )
        # Given an unknown property with no data
        rqp.Property(self.model)
        # And a discrete property
        DISCRETE_NAME = "Discrete Property Name"
        self.discrete_property(grid, DISCRETE_NAME)
        # And a points property
        POINTS_NAME = "Points Property Name"
        self.points_property(grid, POINTS_NAME)
        # And a continuous property
        CONTINUOUS_NAME = "Continuous Property Name"
        self.continuous_property(grid, CONTINUOUS_NAME)
        # And a categorical property
        CATEGORICAL_NAME = "Categorical Property Name"
        self.categorical_property(grid, CATEGORICAL_NAME)
        # And a continuous property indexable by node
        CONTINUOUS_NODE_NAME = "Continuous Node Property Name"
        self.continuous_property(grid, CONTINUOUS_NODE_NAME, indexable="nodes")
        # And a continuous time series property, which should not get converted
        TIME_SERIES_NAME = "Time Series Property Name"
        self.continuous_time_series_property(grid, TIME_SERIES_NAME)

        # Added to the grid
        grid.extract_property_collection()

        # When the properties are converted
        attributes = _convert_attributes(self.model, grid, None, self.data_client)  # pyright: ignore

        # There should be 4 attributes, the unknown and node properties
        # should not have been converted
        self.assertEqual(4, len(attributes))

        # And there is an IntegerAttribute, a ContinuousAttribute
        #     and a CategoricalAttribute with the expected names
        matched = set()
        for a in attributes:
            # Should only see one instance of each name
            self.assertFalse(a.name in matched)
            matched.add(a.name)
            match a:
                case IntegerAttribute():
                    self.assertEqual(DISCRETE_NAME, a.name)
                case ContinuousAttribute():
                    self.assertEqual(CONTINUOUS_NAME, a.name)
                case CategoryAttribute():
                    self.assertEqual(CATEGORICAL_NAME, a.name)
                case VectorAttribute():
                    self.assertEqual(POINTS_NAME, a.name)
                case _:
                    self.fail(f"Unexpected attribute type {type(a).__name__} for attribute {a}")
        # We should have seen all the expected attributes
        self.assertEqual(4, len(matched))

    def categorical_property(self, grid: rqg.RegularGrid, name: str, indexable: str = "cells") -> rqp.Property:
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
        categorical_property_lookup_df, _ = create_category_lookup_and_data(df)

        # randomly assign a category to each cell
        property = rqp.Property.from_array(
            self.model,
            np.random.randint(0, 3, size=grid.extent_kji),
            discrete=True,
            source_info="test data",
            property_kind="CategoricalProperty",
            indexable_element=indexable,
            keyword=name,
            support_uuid=grid.uuid,
            string_lookup_uuid=string_lookup.uuid,
            uom="m",
        )
        self.assertTrue(property.is_categorical())
        return property

    def continuous_property(self, grid: rqg.RegularGrid, name: str, indexable: str = "cells") -> rqp.Property:
        """build a continuous property"""
        if indexable == "nodes":
            (x, y, z, _) = np.shape(grid.points_ref())
            values = np.random.random((x, y, z)).astype(np.float64)
        else:
            values = np.random.random(grid.extent_kji).astype(np.float64)
        property = rqp.Property.from_array(
            self.model,
            values,
            source_info="test data",
            property_kind="ContinuousProperty",
            discrete=False,
            indexable_element=indexable,
            keyword=name,
            support_uuid=grid.uuid,
            uom="m",
        )
        self.assertTrue(property.is_continuous())
        return property

    def points_property(self, grid: rqg.RegularGrid, name: str, indexable: str = "cells") -> rqp.Property:
        """create a points property"""
        property = rqp.Property.from_array(
            self.model,
            np.random.randn(grid.nk, grid.nj, grid.ni, 3),
            points=True,
            source_info="test data",
            property_kind="PointsProperty",
            indexable_element=indexable,
            keyword=name,
            support_uuid=grid.uuid,
            uom="m",
        )
        self.assertTrue(property.is_points())
        return property

    def discrete_property(
        self, grid: rqg.RegularGrid, name: str, type: DTypeLike = np.int64, indexable: str = "cells"
    ) -> rqp.Property:
        """Create a discrete property"""
        property = rqp.Property.from_array(
            self.model,
            np.random.random(grid.extent_kji).astype(type),
            discrete=True,
            source_info="test data",
            property_kind="DiscreteProperty",
            indexable_element=indexable,
            keyword=name,
            support_uuid=grid.uuid,
            uom="m",
        )
        self.assertFalse(property.is_points() or property.is_categorical() or property.is_continuous())
        return property

    def continuous_time_series_property(self, grid: rqg.RegularGrid, name: str) -> rqp.Property:
        """build a continuous time series property"""

        # First construct the time series
        ts = TimeSeries(self.model, first_timestamp="2000-01-01T00:00:00Z", daily=30)
        ts.create_xml()
        self.assertIsNotNone(ts.uuid)
        property = rqp.Property.from_array(
            self.model,
            np.random.random(grid.extent_kji).astype(np.float64),
            source_info="test data",
            property_kind="ContinuousProperty",
            discrete=False,
            indexable_element="cells",
            keyword=name,
            support_uuid=grid.uuid,
            time_series_uuid=ts.uuid,
            time_index=0,
            uom="m",
        )
        property.create_xml()
        self.assertTrue(property.is_continuous())
        self.assertIsNotNone(property.time_series_uuid())
        return property
