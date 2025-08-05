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

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import evo.logging
from evo.aio import AioTransport
from evo.common import APIConnector, Environment, NoAuth
from evo.common.interfaces import ITransport
from evo.common.utils.cache import Cache
from evo.data_converters.common.exceptions import ConflictingConnectionDetailsError, MissingConnectionDetailsError
from evo.oauth import AuthorizationCodeAuthorizer, ClientCredentialsAuthorizer, OAuthScopes, OAuthConnector
from evo.objects import ObjectAPIClient
from evo.objects.utils.data import ObjectDataClient

if TYPE_CHECKING:
    from evo.notebooks import ServiceManagerWidget

logger = evo.logging.getLogger("data_converters")


@dataclass
class EvoWorkspaceMetadata:
    org_id: str = ""
    workspace_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    user_id: str = ""
    hub_url: str = ""
    redirect_url: str = "http://localhost:3000/signin-callback"
    cache_root: str = "./data/cache"

    def has_authentication_code_params(self) -> bool:
        return bool(self.client_id and self.hub_url and self.redirect_url)

    def has_client_credentials_params(self) -> bool:
        return bool(self.client_id and self.client_secret and self.user_id)


@dataclass
class EvoObjectMetadata:
    object_id: UUID
    version_id: Optional[str] = None


async def _authorization_code_authorizer(
    transport: ITransport, metadata: EvoWorkspaceMetadata
) -> AuthorizationCodeAuthorizer:
    authorizer = AuthorizationCodeAuthorizer(
        redirect_url=metadata.redirect_url,
        scopes=OAuthScopes.evo_discovery | OAuthScopes.evo_object,
        oauth_connector=OAuthConnector(
            transport=transport,
            client_id=metadata.client_id,
        ),
    )
    await authorizer.login()

    return authorizer


async def client_credentials_authorizer(
    transport: ITransport, metadata: EvoWorkspaceMetadata
) -> ClientCredentialsAuthorizer:
    authorizer = ClientCredentialsAuthorizer(
        oauth_connector=OAuthConnector(
            transport=transport,
            client_id=metadata.client_id,
            client_secret=metadata.client_secret,
        ),
        scopes=OAuthScopes.evo_discovery | OAuthScopes.evo_workspace | OAuthScopes.evo_object | OAuthScopes.evo_file,
    )
    await authorizer.authorize()

    return authorizer


def create_evo_object_service_and_data_client(
    evo_workspace_metadata: Optional[EvoWorkspaceMetadata] = None,
    service_manager_widget: Optional["ServiceManagerWidget"] = None,
) -> tuple[ObjectAPIClient, ObjectDataClient]:
    if evo_workspace_metadata and service_manager_widget:
        raise ConflictingConnectionDetailsError(
            "Please provide only one of EvoWorkspaceMetadata or ServiceManagerWidget."
        )
    elif evo_workspace_metadata:
        return create_service_and_data_client_from_metadata(evo_workspace_metadata)
    elif service_manager_widget:
        return create_service_and_data_client_from_manager(service_manager_widget)
    raise MissingConnectionDetailsError(
        "Missing one of EvoWorkspaceMetadata or ServiceManagerWidget needed to construct an ObjectAPIClient."
    )


def create_service_and_data_client_from_manager(
    service_manager_widget: "ServiceManagerWidget",
) -> tuple[ObjectAPIClient, ObjectDataClient]:
    logger.debug("Creating ObjectAPIClient from ServiceManagerWidget")
    environment = service_manager_widget.get_environment()
    connector = service_manager_widget.get_connector()
    service_client = ObjectAPIClient(environment, connector)
    data_client = service_client.get_data_client(service_manager_widget.cache)

    return service_client, data_client


def create_service_and_data_client_from_metadata(
    metadata: EvoWorkspaceMetadata,
) -> tuple[ObjectAPIClient, ObjectDataClient]:
    logger.debug(
        "Creating evo.objects.ObjectAPIClient and evo.objects.utils.data.ObjectDataClient with "
        f"EvoWorkspaceMetadata={metadata}"
    )

    cache = Cache(root=metadata.cache_root, mkdir=True)
    transport = AioTransport(user_agent="evo-data-converters")
    authorizer = NoAuth

    org_uuid = UUID(metadata.org_id) if metadata.org_id else metadata.org_id
    if metadata.has_client_credentials_params():
        authorizer = asyncio.run(client_credentials_authorizer(transport, metadata))
        hub_connector = APIConnector(
            base_url=metadata.hub_url,
            transport=transport,
            authorizer=authorizer,
            additional_headers={"s2s-org-info": metadata.org_id, "s2s-user-info": metadata.user_id},
        )
    else:
        if metadata.has_authentication_code_params():
            authorizer = asyncio.run(_authorization_code_authorizer(transport, metadata))
        else:
            logger.debug("Skipping authentication due to missing required parameters.")

        hub_connector = APIConnector(base_url=metadata.hub_url, transport=transport, authorizer=authorizer)

    workspace_uuid = UUID(metadata.workspace_id) if metadata.workspace_id else metadata.workspace_id

    environment = Environment(
        hub_url=metadata.hub_url,
        org_id=org_uuid,
        workspace_id=workspace_uuid,
    )
    service_client = ObjectAPIClient(environment, hub_connector)
    data_client = service_client.get_data_client(cache)

    return service_client, data_client
