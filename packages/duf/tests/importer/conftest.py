import pytest

from evo.data_converters.common import create_evo_object_service_and_data_client, EvoWorkspaceMetadata


@pytest.fixture(scope="session")
def data_client(tmp_path_factory):
    cache_root_dir = tmp_path_factory.mktemp("duf-attr-tests")
    metadata = EvoWorkspaceMetadata(workspace_id="9c86938d-a40f-491a-a3e2-e823ca53c9ae", cache_root=cache_root_dir.name)
    _, data_client = create_evo_object_service_and_data_client(metadata)
    return data_client
