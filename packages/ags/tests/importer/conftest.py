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
from pathlib import Path
import pandas as pd
from unittest.mock import Mock
from evo.data_converters.ags.common import AgsContext
import pytest

from evo.data_converters.common import (
    create_evo_object_service_and_data_client,
    EvoWorkspaceMetadata,
)


@pytest.fixture(scope="session")
def evo_metadata():
    cache_root_dir = tempfile.TemporaryDirectory()
    return EvoWorkspaceMetadata(
        workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae",
        cache_root=cache_root_dir.name,
    )


@pytest.fixture(scope="session")
def evo_metadata_with_hub():
    cache_root_dir = tempfile.TemporaryDirectory()
    return EvoWorkspaceMetadata(
        workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae",
        cache_root=cache_root_dir.name,
        hub_url="https://test.hub.url",
    )


@pytest.fixture(scope="session")
def data_client(evo_metadata):
    _, data_client = create_evo_object_service_and_data_client(evo_metadata)
    return data_client


@pytest.fixture(scope="session")
def valid_ags_path():
    """Path to a valid AGS file with proper structure."""
    return str((Path(__file__).parent / "data" / "valid_ags.ags").resolve())


@pytest.fixture(scope="session")
def valid_ags_1a_path():
    """Path to a valid AGS file with proper structure in PROJ_ID EXAMPLE-1"""
    return str((Path(__file__).parent / "data" / "valid_ags_1a.ags").resolve())


@pytest.fixture(scope="session")
def valid_ags_1b_path():
    """Path to a valid AGS file in PROJ_ID EXAMPLE-1.
    Contains different LOCA_ID to valid_ags_1a.ags"""
    return str((Path(__file__).parent / "data" / "valid_ags_1b.ags").resolve())


@pytest.fixture(scope="session")
def valid_ags_2a_path():
    """Path to a valid AGS file in PROJ_ID EXAMPLE-2"""
    return str((Path(__file__).parent / "data" / "valid_ags_2a.ags").resolve())


@pytest.fixture(scope="session")
def invalid_ags_2b_path():
    """Path to an invalid AGS file in PROJ_ID EXAMPLE-2.
    Contains a duplicate LOCA_ID, present in valid_ags_2a.ags."""
    return str((Path(__file__).parent / "data" / "invalid_ags_2b.ags").resolve())


@pytest.fixture(scope="session")
def valid_ags_2c_path():
    """Path to a valid AGS file in PROJ_ID EXAMPLE-2.
    Contains non-identical PROJ table entry, raising warning only."""
    return str((Path(__file__).parent / "data" / "valid_ags_2c.ags").resolve())


@pytest.fixture(scope="session")
def invalid_ags_2d_path():
    """Path to an invalid AGS file in PROJ_ID EXAMPLE-2.
    Incompatible CRS information."""
    return str((Path(__file__).parent / "data" / "invalid_ags_2d.ags").resolve())


@pytest.fixture(scope="session")
def valid_ags_no_cpt_path():
    """Path to a valid AGS file without CPT data."""
    return str((Path(__file__).parent / "data" / "valid_ags_no_cpt.ags").resolve())


@pytest.fixture(scope="session")
def not_ags_path():
    """Path to an invalid AGS file."""
    return str((Path(__file__).parent / "data" / "not_ags.ags").resolve())


@pytest.fixture(scope="session")
def empty_ags_path():
    """Path to an empty AGS file."""
    return str((Path(__file__).parent / "data" / "empty.ags").resolve())


@pytest.fixture(scope="session")
def test_datetime_formats_ags_path():
    """Path to an AGS file for testing datetime format parsing."""
    return str((Path(__file__).parent / "data" / "test_datetime_formats.ags").resolve())


@pytest.fixture(scope="session")
def test_timedelta_ags_path():
    """Path to an AGS file for testing timedelta type conversion."""
    return str((Path(__file__).parent / "data" / "test_timedelta.ags").resolve())


@pytest.fixture
def mock_ags_context():
    """Create a mock AgsContext with sample data."""
    context = Mock(spec=AgsContext)
    context.filename = "test_file.ags"
    context.coordinate_reference_system = "EPSG:4326"

    # LOCA table
    loca_df = pd.DataFrame(
        {
            "LOCA_ID": ["BH01", "BH02", "BH03"],
            "LOCA_NATE": [100.0, 200.0, 300.0],
            "LOCA_NATN": [1000.0, 2000.0, 3000.0],
        }
    )

    scpg_df = pd.DataFrame(
        {
            "LOCA_ID": ["BH01", "BH02", "BH03", "BH03"],
            "SCPG_TESN": ["T01", "T01", "T01", "T02"],
            "SCPG_TYPE": ["PC", "PC", "PC", "PC"],
        }
    )

    scpt_df = pd.DataFrame(
        {
            "LOCA_ID": ["BH01", "BH01", "BH02", "BH02", "BH03", "BH03"],
            "SCPG_TESN": ["T01", "T01", "T01", "T01", "T01", "T02"],
            "SCPT_DPTH": [5.1, 5.2, 6.1, 6.2, 7.1, 7.2],
        }
    )

    scpp_df = pd.DataFrame(
        {
            "LOCA_ID": ["BH01", "BH01", "BH02"],
            "SCPG_TESN": ["T01", "T01", "T01"],
            "SCPG_REF": ["T01", "T01", "T01"],
            "SCPP_TOP": [5.0, 10.0, 15.0],
            "SCPP_BASE": [10.0, 15.0, 20.0],
            "SCPP_CIC": [1.5, 2.3, 1.8],
        }
    )

    geol_df = pd.DataFrame(
        {
            "LOCA_ID": ["BH01", "BH02"],
            "GEOL_TOP": [0.0, 0.0],
            "GEOL_BASE": [5.0, 10.0],
            "GEOL_DESC": ["Clay", "Sand"],
        }
    )

    scdg_df = pd.DataFrame(
        {
            "LOCA_ID": ["BH01", "BH03"],
            "SCPG_TESN": ["T01", "T01"],
            "SCDG_DPTH": [7.5, 11.0],
            "SCDG_T": [100, 150],
        }
    )

    def get_table_side_effect(table_name):
        if table_name == "LOCA":
            return loca_df.copy()
        elif table_name == "SCPT":
            return scpt_df.copy()
        elif table_name == "SCPG":
            return scpg_df.copy()
        elif table_name == "SCPP":
            return scpp_df.copy()
        elif table_name == "GEOL":
            return geol_df.copy()
        elif table_name == "SCDG":
            return scdg_df.copy()
        return pd.DataFrame()

    def get_tables_side_effect(groups=None):
        tables = []
        if groups:
            if "SCPT" in groups:
                tables.append(scpt_df.copy())
            if "SCPP" in groups:
                tables.append(scpp_df.copy())
            if "GEOL" in groups:
                tables.append(geol_df.copy())
            if "SCDG" in groups:
                tables.append(scdg_df.copy())
        return tables

    context.get_table.side_effect = get_table_side_effect
    context.get_tables.side_effect = get_tables_side_effect

    return context
