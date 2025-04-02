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

from typing import Any, Optional
from uuid import uuid4

import omf2
import pandas as pd
import pyarrow as pa

import evo.logging
from evo.data_converters.common import BlockSyncClient
from evo.data_converters.omf.importer.blockmodel.omf_attributes_to_blocksync import (
    convert_omf_blockmodel_attributes_to_columns,
)
from evo.data_converters.omf.importer.blockmodel.utils import (
    IndexToSidx,
    calc_level,
    check_all_same,
    convert_orient_to_angle,
    get_max_depth,
    schema_type_to_blocksync,
)

logger = evo.logging.getLogger("data_converters")


def create_req_body(
    orient: omf2.Orient3, grid: omf2.Grid3Regular, size_options: dict[str, Any], epsg_code: int
) -> dict[str, Any]:
    """Create the body for the create block model API request.

    :param orient: The orientation of the block model.
    :param grid: The block model grid.
    :param size_options: The dictionary containing metadata about the block model blocks.
    :param epsg_code: The EPSG code for the coordinate reference system.

    :return: The body of the API request.
    """
    angles = convert_orient_to_angle([orient.u, orient.v, orient.w])
    body = {
        "name": str(uuid4()),  # Block model name MUST be unique within a workspace
        "model_origin": {"x": orient.origin[0], "y": orient.origin[1], "z": orient.origin[2]},
        "block_rotation": [
            {
                "axis": "z",
                "angle": angles[0],
            },
            {
                "axis": "x",
                "angle": angles[1],
            },
            {
                "axis": "z",
                "angle": angles[2],
            },
        ],
        "size_options": size_options,
        "coordinate_reference_system": f"EPSG:{epsg_code}",
    }
    return body


def extract_regular_block_model_columns(blockmodel: omf2.Element, reader: omf2.Reader) -> pa.Table:
    grid_count = blockmodel.geometry().grid.count()

    nx = grid_count[0]
    ny = grid_count[1]
    nz = grid_count[2]

    df = pd.DataFrame()

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                df = pd.concat([df, pd.DataFrame({"i": [i], "j": [j], "k": [k]})], ignore_index=True)

    return add_attribute_columns(blockmodel, reader, df)


def extract_variable_octree_block_model_columns(
    blockmodel: omf2.Element,
    reader: omf2.Reader,
    subblocks: omf2.RegularSubblocks,
) -> pa.Table:
    subblock_parent_array, subblock_corner_array = reader.array_regular_subblocks(subblocks.subblocks)

    max_depth = get_max_depth(subblocks.count)
    i2s = IndexToSidx(max_depth).create()

    df = pd.DataFrame()

    for idx in range(len(subblock_corner_array)):
        parent_indices = subblock_parent_array[idx]
        subblock_corners = subblock_corner_array[idx]

        i = parent_indices[0]
        j = parent_indices[1]
        k = parent_indices[2]

        i_min = subblock_corners[0]
        j_min = subblock_corners[1]
        k_min = subblock_corners[2]
        i_max = subblock_corners[3]
        j_max = subblock_corners[4]
        k_max = subblock_corners[5]

        # Calculate sidx
        lvl = calc_level(subblocks.count, i_min, i_max, j_min, j_max, k_min, k_max)
        i_lvl = int(i_min / (i_max - i_min))
        j_lvl = int(j_min / (j_max - j_min))
        k_lvl = int(k_min / (k_max - k_min))

        if (
            i_min == 0
            and i_max == subblocks.count[0]
            and j_min == 0
            and j_max == subblocks.count[1]
            and k_min == 0
            and k_max == subblocks.count[2]
        ):
            sidx = 0  # parent block
        else:
            sidx = i2s[lvl][i_lvl, j_lvl, k_lvl]

        df = pd.concat([df, pd.DataFrame({"i": [i], "j": [j], "k": [k], "sidx": [sidx]})], ignore_index=True)

    return add_attribute_columns(blockmodel, reader, df, subblocks)


def extract_flexible_block_model_columns(
    blockmodel: omf2.Element,
    reader: omf2.Reader,
    subblocks: omf2.RegularSubblocks,
) -> pa.Table:
    subblock_parent_array, subblock_corner_array = reader.array_regular_subblocks(subblocks.subblocks)

    df = pd.DataFrame()

    for idx in range(len(subblock_corner_array)):
        parent_indices = subblock_parent_array[idx]
        subblock_corners = subblock_corner_array[idx]

        i = parent_indices[0]
        j = parent_indices[1]
        k = parent_indices[2]

        i_min = subblock_corners[0]
        j_min = subblock_corners[1]
        k_min = subblock_corners[2]
        i_max = subblock_corners[3]
        j_max = subblock_corners[4]
        k_max = subblock_corners[5]

        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    {
                        "i": [i],
                        "j": [j],
                        "k": [k],
                        "start_si": [i_min],
                        "start_sj": [j_min],
                        "start_sk": [k_min],
                        "end_si": [i_max],
                        "end_sj": [j_max],
                        "end_sk": [k_max],
                    }
                ),
            ],
            ignore_index=True,
        )

    return add_attribute_columns(blockmodel, reader, df, subblocks)


def extract_fully_sub_blocked_block_model_columns(
    blockmodel: omf2.Element,
    reader: omf2.Reader,
    subblocks: omf2.RegularSubblocks,
) -> pa.Table:
    grid_count = blockmodel.geometry().grid.count()

    nx = grid_count[0]
    ny = grid_count[1]
    nz = grid_count[2]

    subblock_parent_array, subblock_corner_array = reader.array_regular_subblocks(subblocks.subblocks)

    df = pd.DataFrame()

    for idx in range(len(subblock_corner_array)):
        parent_indices = subblock_parent_array[idx]
        subblock_corners = subblock_corner_array[idx]

        i = parent_indices[0]
        j = parent_indices[1]
        k = parent_indices[2]

        i_min = subblock_corners[0]
        j_min = subblock_corners[1]
        k_min = subblock_corners[2]
        i_max = subblock_corners[3]
        j_max = subblock_corners[4]
        k_max = subblock_corners[5]

        if (
            i_min == 0
            and i_max == subblocks.count[0]
            and j_min == 0
            and j_max == subblocks.count[1]
            and k_min == 0
            and k_max == subblocks.count[2]
        ):
            sidx = 0  # parent block
        else:
            sidx = 1 + i_min * nx * ny + j_min * nz + k_min

        df = pd.concat([df, pd.DataFrame({"i": [i], "j": [j], "k": [k], "sidx": [sidx]})], ignore_index=True)

    return add_attribute_columns(blockmodel, reader, df, subblocks)


def add_attribute_columns(
    blockmodel: omf2.Element,
    reader: omf2.Reader,
    df: pd.DataFrame,
    subblocks: Optional[omf2.RegularSubblocks] = None,
) -> pa.Table:
    # Evo expects block model indices to be uint32 data type, unless they are the flexible subblock columns
    schema_list = []
    for column in df.columns:
        if column in ["start_si", "start_sj", "start_sk", "end_si", "end_sj", "end_sk"]:
            schema_dtype = pa.uint8()
        else:
            schema_dtype = pa.uint32()
        schema_list.append((column, schema_dtype))
    schema = pa.schema(schema_list)

    table = pa.Table.from_pandas(df, schema)
    location = omf2.Location.Subblocks if subblocks else omf2.Location.Primitives

    return convert_omf_blockmodel_attributes_to_columns(blockmodel, reader, table, location)


def convert_omf_regular_block_model(
    blockmodel: omf2.Element, client: BlockSyncClient, reader: omf2.Reader, epsg_code: int
) -> tuple[str, dict[str, Any], pa.Table]:
    """Convert an OMF regular block model to a BlockSync block model.

    :param blockmodel: The blockmodel element.
    :param client: The BlockSync API client.
    :param reader: The OMF file reader.
    :param epsg_code: The EPSG code for the coordinate reference system.

    :return: The block model ID, the block model creation request, the block model in tabular form.
    """
    geometry = blockmodel.geometry()
    orient = geometry.orient
    grid = geometry.grid

    if isinstance(grid, omf2.Grid3Tensor):
        u = reader.array_scalars(grid.u)
        v = reader.array_scalars(grid.v)
        w = reader.array_scalars(grid.w)
        block_size = {"x": u[0], "y": v[0], "z": w[0]}
    else:
        block_size = {"x": grid.size[0], "y": grid.size[1], "z": grid.size[2]}

    model_type = "regular"
    size_options = {
        "model_type": model_type,
        "n_blocks": {"nx": grid.count()[0], "ny": grid.count()[1], "nz": grid.count()[2]},
        "block_size": block_size,
    }

    body = create_req_body(orient, grid, size_options, epsg_code)
    block_model_uuid = client.create_request(body=body)
    table = extract_regular_block_model_columns(blockmodel, reader)
    return block_model_uuid, body, table


def convert_omf_regular_subblock_model(
    blockmodel: omf2.Element, client: BlockSyncClient, reader: omf2.Reader, epsg_code: int
) -> tuple[str, dict[str, Any], pa.Table]:
    """Convert an OMF regular subblock model to a BlockSync block model.

    :param blockmodel: The blockmodel element.
    :param client: The BlockSync API client.
    :param reader: The OMF file reader.
    :param epsg_code: The EPSG code for the coordinate reference system.

    :return: The block model ID, the block model creation request, the block model in tabular form.
    """
    geometry = blockmodel.geometry()
    orient = geometry.orient
    subblocks = geometry.subblocks

    if subblocks.count[0] == 1 and subblocks.count[1] == 1 and subblocks.count[2] == 1:
        raise ValueError("BMS does not support a subblocking count of 1 along 3 axes.")

    if subblocks.mode == omf2.SubblockMode.Octree:
        model_type = "variable-octree"
        table = extract_variable_octree_block_model_columns(blockmodel, reader, subblocks)
    elif subblocks.mode == omf2.SubblockMode.Full:
        model_type = "fully-sub-blocked"
        table = extract_fully_sub_blocked_block_model_columns(blockmodel, reader, subblocks)
    else:
        model_type = "flexible"
        table = extract_flexible_block_model_columns(blockmodel, reader, subblocks)

    grid = geometry.grid
    grid_count = grid.count()

    size_options = {
        "model_type": model_type,
        "n_parent_blocks": {"nx": grid_count[0], "ny": grid_count[1], "nz": grid_count[2]},
        "n_subblocks_per_parent": {"nx": subblocks.count[0], "ny": subblocks.count[1], "nz": subblocks.count[2]},
        "parent_block_size": {"x": grid.size[0], "y": grid.size[1], "z": grid.size[2]},
    }

    body = create_req_body(orient, grid, size_options, epsg_code)
    block_model_uuid = client.create_request(body=body)

    return block_model_uuid, body, table


def convert_omf_tensor_grid_model(
    blockmodel: omf2.Element, client: BlockSyncClient, reader: omf2.Reader, epsg_code: int
) -> Optional[tuple[str, dict[str, Any], Any]]:
    """Convert a tensor grid model to a Block Sync blockmodel if it is a regular grid.

    OMF V1 does not store regular and tensor grids separately, it instead stores regular
    grids as tensor grids where every value in u is the same, every value in v is the same
    and every value in w is the same.

    :param blockmodel: The block model to convert.
    :param client: The Block Model API client.
    :param reader: The OMF file reader.
    :param epsg_code: The EPSG code for the coordinate reference system.
    """
    geometry = blockmodel.geometry()
    grid = geometry.grid
    u = reader.array_scalars(grid.u)
    v = reader.array_scalars(grid.v)
    w = reader.array_scalars(grid.w)
    if check_all_same(u) and check_all_same(v) and check_all_same(w):
        return convert_omf_regular_block_model(blockmodel, client, reader, epsg_code)
    else:
        # TODO: Add support for uploading these to evo?
        logger.warning(
            "BlockSync does not support tensor grid block models where each row, column, and layer can have a different size."
        )
    return None


def add_blocks_and_columns(
    client: BlockSyncClient, block_model_uuid: str, table: pa.Table, is_octree: bool
) -> Optional[str]:
    """Create the request to add column data to the newly created block model.

    :param client: The BlockSync API client.
    :param block_model_uuid: The newly created block model ID.
    :param table: The block model column data in tabular form.
    :param is_octree: True if the block model has type octree, false otherwise.

    :return: The URL of the BlockSync job to add the new column data or None
    if there are no new columns.
    """
    # use schema from table to determine add col body
    new_cols = []
    for i, col in enumerate(table.column_names):
        if col not in ["i", "j", "k", "start_si", "start_sj", "start_sk", "end_si", "end_sj", "end_sk", "sidx"]:
            data_type = schema_type_to_blocksync(table.schema[i].type)
            new_cols.append({"title": col, "data_type": data_type})

    if len(new_cols) < 1:
        logger.warning(f"The block model {block_model_uuid} cannot be updated because it has no attributes.")
        return None

    if is_octree:
        add_col_body = {
            "columns": {
                "new": new_cols,
                "delete": [],
                "update": [],
                "rename": [],
            },
            "comment": "Added during OMF to BlockSync conversion.",
            "geometry_change": True,  # subblocks will be created
        }
    else:
        add_col_body = {
            "columns": {
                "new": new_cols,
                "delete": [],
                "update": [],
                "rename": [],
            },
            "comment": "Added during OMF to BlockSync conversion.",
        }

    job_url, upload_url = client.add_columns_request(block_model_uuid, add_col_body)
    client.upload_parquet(upload_url, table)

    return str(job_url)
