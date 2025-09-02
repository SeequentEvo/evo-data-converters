import asyncio
import os
import shutil
from typing import Optional

from evo.notebooks import ServiceManagerWidget
from evo.objects import ObjectMetadata, ObjectAPIClient
from evo.objects.utils import ObjectDataClient

from evo.data_converters.common import (
    EvoObjectMetadata,
    create_evo_object_service_and_data_client,
    EvoWorkspaceMetadata,
)
from evo.data_converters.duf.common import deswik_types as dw
from evo.data_converters.duf.common.conversions import EvoDufWriter
from evo.data_converters.duf.common.types import FetchedLines, FetchedTriangleMesh
from evo.data_converters.duf.fetch import Fetch, FetchStatus

_EvoMetadata = ObjectMetadata | EvoObjectMetadata


async def _evo_objects_to_duf_async(
    duf_file: str,
    evo_objects: list[_EvoMetadata],
    api_client: ObjectAPIClient,
    data_client: ObjectDataClient,
):
    # TODO It would be nice if `EvoObjectMetadata` had an `id` field instead of `object_id`, so they would be duck type
    #  equivalent.
    evo_objects: list[EvoObjectMetadata] = [
        (obj if isinstance(obj, EvoObjectMetadata) else EvoObjectMetadata(object_id=obj.id, version_id=obj.version_id))
        for obj in evo_objects
    ]

    # I was having trouble creating a file from scratch. Newly created files have a bunch of objects that I didn't know
    # how to make. So start with an empty file made from the Deswik Cad
    duf_file_empty = os.path.join(os.path.dirname(__file__), "duf_files", "empty.duf")
    shutil.copy(duf_file_empty, duf_file)

    # Kick off the evo downloads
    async_fetch_futures = Fetch.download_all(evo_objects, api_client, data_client)

    # While the evo downloads are going, do some file IO stuff

    duf = dw.Duf(duf_file)
    duf_writer = EvoDufWriter(duf)

    failures = []

    # Go ahead and wait for the next download
    async for fetched_object_result in async_fetch_futures:
        fetched_object = fetched_object_result.result
        if fetched_object_result.status == FetchStatus.failed:
            failures.append(fetched_object_result.status_message)
        elif isinstance(fetched_object, FetchedLines):
            # Process this polyline while we wait for the others to fetch
            duf_writer.write_lines(fetched_object)
        elif isinstance(fetched_object, FetchedTriangleMesh):
            duf_writer.write_mesh_triangles(fetched_object)
        else:
            raise NotImplementedError(f"Unhandled object type: {type(fetched_object)}")

    if failures:
        # TODO Need to test that this actually gets hit
        print("Failed to convert some objects:")
        print("\n".join(failures))

    duf.Save()
    duf.Dispose()



def export_duf(
    filepath,
    objects: list[_EvoMetadata],
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
):
    api_client, data_client = create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )

    asyncio.run(_evo_objects_to_duf_async(filepath, objects, api_client, data_client))
