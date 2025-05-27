from pathlib import Path

import pytest

from evo.data_converters.common import create_evo_object_service_and_data_client, EvoWorkspaceMetadata
from evo.data_converters.duf import DufCollectorContext


@pytest.fixture(scope="session")
def evo_metadata(tmp_path_factory):
    cache_root_dir = tmp_path_factory.mktemp("duf-attr-tests")
    return EvoWorkspaceMetadata(workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=cache_root_dir.name)


@pytest.fixture(scope="session")
def data_client(evo_metadata):
    _, data_client = create_evo_object_service_and_data_client(evo_metadata)
    return data_client


@pytest.fixture(scope="session")
def simple_objects_path():
    return str((Path(__file__).parent.parent / "data" / "simple_objects.duf").resolve())


@pytest.fixture(scope="session")
def simple_objects(simple_objects_path):
    with DufCollectorContext(simple_objects_path) as context:
        yield context.collector
