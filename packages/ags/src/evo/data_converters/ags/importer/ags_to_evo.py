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


from pathlib import Path
from typing import TYPE_CHECKING

import evo.logging
from evo.common import IContext
from evo.data_converters.ags.common import AgsContext, AgsFileInvalidException
from evo.data_converters.ags.diagnostics import AgsDiagnostic, AgsParsingError, AgsSource
from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.common.exceptions import ConflictingConnectionDetailsError
from evo.data_converters.common.generate_paths import generate_paths
from evo.data_converters.common.utils import get_object_tags
from evo.objects import ObjectReference
from evo.objects.data import ObjectMetadata
from evo.objects.typed import DownholeCollection, DownholeCollectionData

from .ags_to_downhole_collection import create_from_parsed_ags
from .parse_ags_files import diagnostics_for_exception, parse_ags_files

logger = evo.logging.getLogger("data_converters")

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget


async def convert_ags(
    filepaths: list[str],
    evo_workspace_metadata: EvoWorkspaceMetadata | None = None,
    service_manager_widget: "ServiceManagerWidget | None" = None,
    tags: dict[str, str] | None = None,
    upload_path: str = "",
    publish_objects: bool = True,
    overwrite_existing_objects: bool = False,
    merge_files: bool = True,
    *,
    diagnostics: list[AgsDiagnostic] | None = None,
) -> list[DownholeCollectionData] | list[ObjectMetadata]:
    """Converts one or more AGS files into a list of Downhole Collections.

    One of evo_workspace_metadata or service_manager_widget is required.

    Converted objects will be published if either of the following is true:

    - evo_workspace_metadata.hub_url is present, or
    - service_manager_widget was passed to this function.

    Invalid files and incompatible merges are skipped when other inputs convert successfully. Diagnostics for skipped
    inputs, dropped holes, coordinate references and defaulted ground levels can be collected with the keyword-only
    ``diagnostics`` parameter. If no input produces a collection, this raises :class:`AgsParsingError`.

    :param filepaths: List of paths to one or more AGS files.
    :param evo_workspace_metadata: Evo workspace metadata (optional).
    :param service_manager_widget: Service Manager Widget for use in jupyter notebooks (optional).
    :param tags: Dict of tags to add to the Geoscience Object(s) (optional).
    :param upload_path: Path objects will be published under (optional).
    :param publish_objects: Set False to return rather than publish objects (optional, default True).
    :param overwrite_existing_objects: Whether existing objects will be overwritten with a new version
        (optional, default False).
    :param merge_files: Whether to merge files with the same PROJ_ID into a single DownholeCollection
        (optional, default True). If False, each file will produce a separate DownholeCollection.
    :param diagnostics: Optional list extended with structured warnings and errors after successful conversion.
        It is left unchanged when conversion fails.
    :return: The data of the converted Downhole Collections, or the metadata of the published objects if published.
    :rtype: list[DownholeCollectionData] | list[ObjectMetadata]
    :raises MissingConnectionDetailsError: If no connection details could be derived.
    :raises ConflictingConnectionDetailsError: If both evo_workspace_metadata and service_manager_widget
        were provided, or if evo_workspace_metadata was provided without hub_url when publishing.
    :raises AgsParsingError: If no input files are provided or none of the inputs produces a collection.
    :raises ObjectAlreadyExistsError: If an object already exists at a path being published to,
        and overwrite_existing_objects is False.
    """
    if not filepaths:
        raise AgsParsingError(
            [
                AgsDiagnostic(
                    code="no_input_files",
                    severity="error",
                    sources=(),
                    reason="Select at least one AGS file.",
                )
            ]
        )

    invocation_diagnostics: list[AgsDiagnostic] = []
    _, data_client = await create_evo_object_service_and_data_client(
        evo_workspace_metadata=evo_workspace_metadata,
        service_manager_widget=service_manager_widget,
    )
    if publish_objects and evo_workspace_metadata and not evo_workspace_metadata.hub_url:
        raise ConflictingConnectionDetailsError(
            "evo_workspace_metadata provided without hub_url, cannot publish objects."
        )

    ags_contexts: list[AgsContext] = parse_ags_files(
        filepaths, merge_files=merge_files, diagnostics=invocation_diagnostics
    )

    downhole_collections: list[DownholeCollectionData] = []
    for context in ags_contexts:
        object_tags = get_object_tags(path=context.filename, input_type="AGS", extra_tags=tags or {})
        conversion_diagnostics: list[AgsDiagnostic] = []
        try:
            converted = create_from_parsed_ags(context, object_tags, diagnostics=conversion_diagnostics)
        except AgsFileInvalidException as e:
            logger.error("Failed to convert AGS file '%s': %s", context.filename, e)
            invocation_diagnostics.extend(diagnostics_for_exception(e, context.sources))
        else:
            downhole_collections.append(converted)
            invocation_diagnostics.extend(conversion_diagnostics)

    if not downhole_collections:
        if not invocation_diagnostics:
            invocation_diagnostics.append(
                AgsDiagnostic(
                    code="no_collections",
                    severity="error",
                    sources=tuple(AgsSource(index, Path(filepath).name) for index, filepath in enumerate(filepaths)),
                    reason=(
                        "No Downhole Collections were produced. "
                        "Check that the input files contain usable location and measurement data."
                    ),
                )
            )
        raise AgsParsingError(order_diagnostics(invocation_diagnostics))

    result: list[DownholeCollectionData] | list[ObjectMetadata] = downhole_collections
    if publish_objects:
        logger.debug("Publishing Downhole Collection(s)")
        result = await publish_downhole_collections(
            downhole_collections,
            context=data_client.get_static_context(),
            path_prefix=upload_path,
            overwrite_existing_objects=overwrite_existing_objects,
        )
    if diagnostics is not None:
        diagnostics.extend(order_diagnostics(invocation_diagnostics))
    return result


def order_diagnostics(diagnostics: list[AgsDiagnostic]) -> list[AgsDiagnostic]:
    """Order invocation diagnostics by their earliest input position, keeping diagnostics without sources first."""
    return sorted(
        diagnostics,
        key=lambda issue: min((source.input_index for source in issue.sources), default=-1),
    )


async def publish_downhole_collections(
    downhole_collections: list[DownholeCollectionData],
    context: IContext,
    path_prefix: str = "",
    overwrite_existing_objects: bool = False,
) -> list[ObjectMetadata]:
    """Publishes Downhole Collections to Evo, one object per collection.

    Objects are published to "<path_prefix>/<name>.json", with a numeric suffix added to make duplicate names unique.

    :param downhole_collections: The data of the Downhole Collections to publish.
    :param context: The Evo context to publish with.
    :param path_prefix: Path objects will be published under (optional).
    :param overwrite_existing_objects: Whether existing objects will be replaced with a new version, otherwise
        publishing to the path of an existing object raises an error (optional, default False).
    :return: The metadata of the published objects.
    """
    paths = generate_paths(downhole_collections, path_prefix)
    logger.debug(f"Preparing to publish {len(downhole_collections)} objects to paths: {paths}")

    objects_metadata: list[ObjectMetadata] = []
    for data, path in zip(downhole_collections, paths):
        if overwrite_existing_objects:
            reference = ObjectReference.new(environment=context.get_environment(), object_path=path)
            downhole_collection = await DownholeCollection.create_or_replace(context, reference, data)
        else:
            downhole_collection = await DownholeCollection.create(context, data, path=path)

        logger.debug(f"Got object metadata: {downhole_collection.metadata}")
        objects_metadata.append(downhole_collection.metadata)

    return objects_metadata
