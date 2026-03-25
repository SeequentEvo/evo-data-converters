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


import argparse
import asyncio
import logging
import tempfile
import uuid

import nest_asyncio

from evo.data_converters.common import EvoObjectMetadata, EvoWorkspaceMetadata
from evo.data_converters.obj.exporter import export_obj

parser = argparse.ArgumentParser(description="Export Evo Object(s) to an OBJ file")

parser.add_argument("filename", help="Path of the OBJ file to create.")

parser.add_argument(
    "--object",
    action="append",
    help="UUID of an Evo object to export, with an optional colon-separated version of the object. "
    "Defaults to the latest version. Supply multiple --object arguments to export multiple "
    "objects to the OBJ file.",
    required=True,
    default=[],
)

parser.add_argument("--workspace-id", help="Workspace UUID of the workspace the object belongs to.", required=True)
parser.add_argument("--org-id", help="UUID of the organization the workspace belongs to.", required=True)
parser.add_argument("--hub-url", help="URL of the hub the workspace resides in.", required=True)

parser.add_argument("--client-id", help="OAuth client ID as registered with the OAuth provider.", required=True)
parser.add_argument(
    "--redirect-url",
    help="Local URL to redirect the user back to after authorisation if a specific URL must be used.",
    default="",
)

parser.add_argument(
    "--cache-dir",
    help="Local directory to store downloaded files. If it doesn't exist it will be created. "
    "Defaults to a temporary directory if not provided.",
)

parser.add_argument(
    "--log-level", default=logging.INFO, help="Configure the logging level.", type=lambda x: getattr(logging, x)
)

args = parser.parse_args()

# Configure our desired logging configuration
logging.basicConfig(level=args.log_level)
logger = logging.getLogger(__name__)

# Create temporary cache dir if needed
if args.cache_dir is None:
    tmp_cache_dir = tempfile.TemporaryDirectory()
    args.cache_dir = tmp_cache_dir.name

logger.debug(f"Using cache directory: {args.cache_dir}")

workspace_metadata = EvoWorkspaceMetadata(
    client_id=args.client_id,
    hub_url=args.hub_url,
    org_id=args.org_id,
    workspace_id=args.workspace_id,
    cache_root=args.cache_dir,
)

# Override default redirect URL if needed
if args.redirect_url:
    workspace_metadata.redirect_url = args.redirect_url

objects = []

for obj_str in args.object:
    try:
        object_id, version_id = obj_str.split(":")
        object_metadata = EvoObjectMetadata(object_id=uuid.UUID(object_id), version_id=version_id)
    except ValueError:
        object_metadata = EvoObjectMetadata(object_id=uuid.UUID(obj_str))

    objects.append(object_metadata)
    logger.debug(f"Exporting Evo object '{object_metadata.object_id}' to OBJ file '{args.filename}'")

# NOTE: nest_asyncio is currently required as some code in evo.data_converters.common still uses asyncio.run()
nest_asyncio.apply()

asyncio.run(
    export_obj(
        args.filename,
        objects=objects,
        evo_workspace_metadata=workspace_metadata,
    )
)
