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
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import MagicMock, patch

import numpy as np
import omf2
import pandas as pd
import pyarrow as pa
import pytest
import requests_mock

from evo.data_converters.common import BlockSyncClient, EvoWorkspaceMetadata
from evo.data_converters.omf import OmfReaderContext
from evo.data_converters.omf.importer import convert_omf
from evo.data_converters.omf.importer.blockmodel import (
    convert_omf_regular_block_model,
    convert_omf_regular_subblock_model,
    convert_omf_tensor_grid_model,
)
from evo.data_converters.omf.importer.blockmodel.omf_blockmodel_to_blocksync import (
    extract_regular_block_model_columns,
    extract_variable_octree_block_model_columns,
)


class TestBlockModelConverter(TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.epsg_code = 32650

    def test_should_convert_regular_block_model(self) -> None:
        parent = Path(path.dirname(__file__)).parent.absolute()
        omf_file = path.join(parent, "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        regular_block_model = project.elements()[4]

        block_model_uuid, body, table = convert_omf_regular_block_model(
            regular_block_model, self.client, reader, self.epsg_code
        )

        self.assertIsInstance(table, pa.Table)
        self.assertIsInstance(table.schema, pa.Schema)
        self.assertIn("i", table.column_names)
        self.assertIn("j", table.column_names)
        self.assertIn("k", table.column_names)

        expected_body: dict[str, Any] = {
            "name": "test_blockmodel",  # Name can't be checked for equality
            "model_origin": {"x": -1, "y": -1, "z": -1},
            "block_rotation": [{"axis": "z", "angle": 0}, {"axis": "x", "angle": 0}, {"axis": "z", "angle": 0}],
            "size_options": {
                "model_type": "regular",
                "n_blocks": {"nx": 2, "ny": 2, "nz": 2},
                "block_size": {"x": 1, "y": 1, "z": 1},
            },
            "coordinate_reference_system": "EPSG:32650",
        }

        self.assertDictEqual(body["model_origin"], expected_body["model_origin"])
        self.assertListEqual(body["block_rotation"], expected_body["block_rotation"])
        self.assertDictEqual(body["size_options"], expected_body["size_options"])
        self.assertEqual(body["coordinate_reference_system"], expected_body["coordinate_reference_system"])

    def test_should_convert_subblock_octree_model(self) -> None:
        parent = Path(path.dirname(__file__)).parent.absolute()
        omf_file = path.join(parent, "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        regular_subblock_model = project.elements()[6]

        block_model_uuid, body, table = convert_omf_regular_subblock_model(
            regular_subblock_model, self.client, reader, self.epsg_code
        )

        self.assertIsInstance(table, pa.Table)
        self.assertIsInstance(table.schema, pa.Schema)
        self.assertIn("i", table.column_names)
        self.assertIn("j", table.column_names)
        self.assertIn("k", table.column_names)
        self.assertIn("sidx", table.column_names)

        expected_body: dict[str, Any] = {
            "name": "test_blockmodel",  # Name can't be checked for equality
            "model_origin": {"x": -1, "y": -1, "z": -1},
            "block_rotation": [{"axis": "z", "angle": 0}, {"axis": "x", "angle": 0}, {"axis": "z", "angle": 0}],
            "size_options": {
                "model_type": "variable-octree",
                "n_parent_blocks": {"nx": 2, "ny": 2, "nz": 2},
                "n_subblocks_per_parent": {"nx": 4, "ny": 4, "nz": 4},
                "parent_block_size": {"x": 1, "y": 1, "z": 1},
            },
            "coordinate_reference_system": "EPSG:32650",
        }

        self.assertDictEqual(body["model_origin"], expected_body["model_origin"])
        self.assertListEqual(body["block_rotation"], expected_body["block_rotation"])
        self.assertDictEqual(body["size_options"], expected_body["size_options"])
        self.assertEqual(body["coordinate_reference_system"], expected_body["coordinate_reference_system"])

    def test_should_convert_tensor_to_regular_grid(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/rotated_block_model.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        regular_block_model = project.elements()[0]

        block_model_uuid, body, table = convert_omf_tensor_grid_model(
            regular_block_model, self.client, reader, self.epsg_code
        )

        self.assertIsInstance(table, pa.Table)
        self.assertIsInstance(table.schema, pa.Schema)
        self.assertIn("i", table.column_names)
        self.assertIn("j", table.column_names)
        self.assertIn("k", table.column_names)

    def test_extract_columns_octree(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/bunny_blocks.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        octree_block_model = project.elements()[0]
        subblocks = octree_block_model.geometry().subblocks

        subblock_parent_array, subblock_corner_array = reader.array_regular_subblocks(subblocks.subblocks)
        self.assertTrue(np.array_equal(subblock_parent_array[0], [0, 0, 0]))
        # self.assertTrue(np.array_equal(subblock_parent_array[1], [0, 0, 1]))
        self.assertEqual(subblock_corner_array.shape, (5123, 6))
        self.assertEqual(subblock_parent_array.shape, (5123, 3))

        table = extract_variable_octree_block_model_columns(octree_block_model, reader, subblocks)
        table_df = table.to_pandas()

        test_row_1 = pd.Series({"i": 5, "j": 3, "k": 2, "sidx": 0, "Bunny": "Body"})
        self.assertTrue((table_df == test_row_1).all(1).any())
        test_row_2 = pd.Series({"i": 6, "j": 3, "k": 2, "sidx": 0, "Bunny": "Body"})
        self.assertTrue((table_df == test_row_2).all(1).any())
        test_row_3 = pd.Series({"i": 7, "j": 3, "k": 2, "sidx": 10, "Bunny": "Air"})
        self.assertTrue((table_df == test_row_3).all(1).any())
        test_row_4 = pd.Series({"i": 6, "j": 4, "k": 2, "sidx": 28, "Bunny": "Air"})
        self.assertTrue((table_df == test_row_4).all(1).any())
        test_row_5 = pd.Series({"i": 5, "j": 5, "k": 2, "sidx": 38, "Bunny": "Body"})
        self.assertTrue((table_df == test_row_5).all(1).any())

    def test_convert_regular_block_model(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/rotated_block_model_ijk.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()

        block_model = project.elements()[0]
        attr = block_model.attributes()[0]
        self.assertIsInstance(attr.get_data(), omf2.AttributeDataNumber)

        table = extract_regular_block_model_columns(block_model, reader)
        self.assertIsInstance(table, pa.Table)

        expected_columns = ["i", "j", "k", "data_i", "data_j", "data_k", "index"]
        self.assertEqual(expected_columns, table.column_names)

        expected_schema = pa.schema(
            [
                ("i", pa.uint32()),
                ("j", pa.uint32()),
                ("k", pa.uint32()),
                ("data_i", pa.float64()),
                ("data_j", pa.float64()),
                ("data_k", pa.float64()),
                ("index", pa.float64()),
            ]
        )
        self.assertEqual(expected_schema, table.schema)

        self.assertEqual(len(table), 24)
        self.assertListEqual(table["i"].to_pylist()[:10], [0, 0, 0, 0, 0, 0, 1, 1, 1, 1])
        self.assertListEqual(table["j"].to_pylist()[:10], [0, 0, 1, 1, 2, 2, 0, 0, 1, 1])
        self.assertListEqual(table["k"].to_pylist()[:10], [0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
        self.assertListEqual(table["data_i"].to_pylist()[:10], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        self.assertListEqual(table["data_j"].to_pylist()[:10], [0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 0.0, 0.0, 1.0, 1.0])
        self.assertListEqual(table["data_k"].to_pylist()[:10], [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
        self.assertListEqual(table["index"].to_pylist()[:10], [0.0, 12.0, 4.0, 16.0, 8.0, 20.0, 1.0, 13.0, 5.0, 17.0])


@pytest.mark.usefixtures("caplog")
class TestBlockModelConverterWarnings:
    def test_should_not_convert_tensor_grid(self, caplog: Any) -> None:
        client = MagicMock()
        epsg_code = 32650
        parent = Path(path.dirname(__file__)).parent.absolute()
        omf_file = path.join(parent, "data/one_of_everything.omf")
        context = OmfReaderContext(omf_file)
        reader = context.reader()
        project, _ = reader.project()
        tensor_block_model = project.elements()[5]

        convert_omf_tensor_grid_model(tensor_block_model, client, reader, epsg_code)
        expected_log_msg = "BlockSync does not support tensor grid block models where each row, column, and layer can have a different size."
        assert expected_log_msg in caplog.text


class TestOmfToBlockSyncConverter(TestCase):
    def setUp(self) -> None:
        self.cache_root_dir = tempfile.TemporaryDirectory()
        self.metadata = EvoWorkspaceMetadata(
            workspace_id="860be2f5-fe06-4c1b-ac8b-7d34d2b6d2ef",
            hub_url="mock://localhost",
            cache_root=self.cache_root_dir.name,
            org_id="bf1a040c-8c58-4bc2-bec2-c5ae7de8bd84",
        )

    @patch("evo.data_converters.omf.importer.omf_to_evo.publish_geoscience_objects")
    @patch.object(BlockSyncClient, "get_auth_header")
    def test_should_convert_blockmodels(
        self, mock_publish_geoscience_objects: MagicMock, mock_get_auth_header: MagicMock
    ) -> None:
        omf_file = path.join(path.dirname(__file__), "data/bunny_blocks.omf")

        mock_publish_geoscience_objects.return_value = None
        mock_get_auth_header.return_value = {}

        with requests_mock.Mocker() as mock:
            # Note the JSON argument is the response output
            test_blockmodel_id = "testdummy"
            job_status_test_url = "mock://localhost/job-status-url"
            create_req_url = f"{self.metadata.hub_url}/blockmodel/orgs/{self.metadata.org_id}/workspaces/{self.metadata.workspace_id}/block-models"
            add_cols_url = f"{self.metadata.hub_url}/blockmodel/orgs/{self.metadata.org_id}/workspaces/{self.metadata.workspace_id}/block-models/{test_blockmodel_id}/blocks"
            upload_url = "mock://localhost/job-status-url/uploaded"

            # create block model request
            mock.register_uri(
                method="POST",
                url=create_req_url,
                headers={"Authorisation": "token"},
                json={"bm_uuid": test_blockmodel_id, "job_url": job_status_test_url},
                status_code=201,
            )

            # add columns to block model request
            mock.register_uri(
                method="PATCH",
                url=add_cols_url,
                headers={"Authorisation": "token"},
                json={"upload_url": job_status_test_url, "job_url": job_status_test_url},
                status_code=202,
            )

            # complete blockmodel upload
            # "/uploaded" is appended to the job_status_test_url in the complete upload function
            mock.register_uri(
                method="POST",
                url=upload_url,
                headers={"Authorisation": "token"},
                json={"job_url": job_status_test_url},
                status_code=201,
            )

            # upload parquet
            mock.register_uri(
                method="PUT",
                url=job_status_test_url,
                headers={"Content-Type": "application/binary", "x-ms-blob-type": "BlockBlob"},
                status_code=201,
            )

            # check job status
            mock.get(
                url=job_status_test_url,
                headers={"Authorisation": "token"},
                json={"status_code": 200, "job_status": "COMPLETE"},
            )

            go_objects = convert_omf(filepath=omf_file, evo_workspace_metadata=self.metadata, epsg_code=32650)
            self.assertListEqual([], go_objects)

            history = mock.request_history
            self.assertEqual(mock.call_count, 6)
            self.assertEqual(history[0].method, "POST")  # create
            self.assertEqual(history[0].url, create_req_url)
            self.assertEqual(history[1].method, "GET")  # check
            self.assertEqual(history[1].url, job_status_test_url)
            self.assertEqual(history[2].method, "PATCH")  # add
            self.assertEqual(history[2].url, add_cols_url)
            self.assertEqual(history[3].method, "PUT")  # upload
            self.assertEqual(history[3].url, job_status_test_url)
            self.assertEqual(history[4].method, "POST")  # complete
            self.assertEqual(history[4].url, upload_url)
            self.assertEqual(history[5].method, "GET")  # check
            self.assertEqual(history[5].url, job_status_test_url)
