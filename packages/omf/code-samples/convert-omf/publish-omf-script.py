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
import logging
import pprint
import tempfile
import uuid

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.omf.importer import convert_omf

parser = argparse.ArgumentParser(description="Publish elements from an OMF file to Evo")

parser.add_argument("filename", help="Provide a path to an OMF file you want to process, OMF v1 or v2 is supported.")

parser.add_argument(
    "--epsg-code", help="EPSG code to use for the Coordinate Reference System.", required=True, type=int
)
parser.add_argument("--upload-path", help="Path to upload objects to.")

parser.add_argument(
    "--overwrite-existing-objects", action="store_true", default=False, help="Overwrite existing objects"
)

parser.add_argument(
    "--cache-dir",
    help="Local directory to store processed files. If it doesn't exist it will be created. Defaults to a temporary directory if not provided.",
)

parser.add_argument("--hub-url", help="The URL of the hub the workspace resides in.", default="")
parser.add_argument("--org-id", help="UUID of the organization the workspace belongs to.", default="")
parser.add_argument("--workspace-id", help="The workspace UUID.")

parser.add_argument("--client-id", help="The OAuth client ID, as registered with the OAuth provider.", default="")
parser.add_argument("--redirect-url", help="The local URL to redirect the user back to after authorisation", default="")

parser.add_argument(
    "--tag",
    action="append",
    help="A colon separated tag name/value pair to add to the created Evo object(s). "
    "Specify multiple times to add multiple tags. ",
    default=[],
)

parser.add_argument(
    "--log-level", default=logging.INFO, help="Configure the logging level.", type=lambda x: getattr(logging, x)
)

args = parser.parse_args()

# Parse tags
tags = {}
for tag_pair in args.tag:
    try:
        tag_name, tag_value = tag_pair.split(":")
    except ValueError:
        parser.error(f"Invalid --tag argument '{tag_pair}'. Tag name and value must be separated by a colon.")
    tags[tag_name] = tag_value

# Configure our desired logging configuration
logging.basicConfig(level=args.log_level)
logger = logging.getLogger(__name__)

logger.debug(f"Convert and publish elements from OMF file: {args.filename}")

# Create temporary cache dir if needed
if args.cache_dir is None:
    tmp_cache_dir = tempfile.TemporaryDirectory()
    args.cache_dir = tmp_cache_dir.name

logger.debug(f"Using cache directory: {args.cache_dir}")

# This allows you to convert an OMF file without needing to fill out any credentials required for publishing
if args.workspace_id is None:
    args.workspace_id = str(uuid.uuid4())
    logger.debug(f"Using randomly generated workspace id: {args.workspace_id}")

# Group workspace metadata together
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

logger.debug(f"Using Evo Workspace Metadata: {workspace_metadata}")

# Convert OMF file, if a hub_url was provided above the objects will be published
results = convert_omf(
    filepath=args.filename,
    evo_workspace_metadata=workspace_metadata,
    epsg_code=args.epsg_code,
    tags=tags,
    upload_path=args.upload_path,
    overwrite_existing_objects=args.overwrite_existing_objects,
)

# Results will either be a list of BaseSpatialDataProperties_V1_0_1 if not published, or a list of ObjectMetadata if they were published
for result in results:
    pprint.pp(result, indent=1)
