#  Copyright © 2026 Bentley Systems, Incorporated
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
import pprint
import tempfile
import uuid

from evo.data_converters.las.importer import convert_las
from evo.data_converters.common import EvoWorkspaceMetadata

parser = argparse.ArgumentParser(description="Publish a downhole collection from LAS 2.0 files to Evo")

parser.add_argument("filenames", nargs="+", help="Paths to one or more LAS 2.0 files to process.")
parser.add_argument(
    "--deviation-files",
    nargs="+",
    help="Petrel deviation (.dev) files, or a directory of them, giving each hole's collar and survey. "
    "Matched to LAS files by well name.",
)
parser.add_argument(
    "--allow-missing-deviation",
    action="store_true",
    help="Use a (0, 0, 0) collar and vertical path for holes without a matching deviation file.",
)

parser.add_argument(
    "--epsg-code",
    help="Optional EPSG code for the Coordinate Reference System. Omit for a local/unspecified CRS.",
    type=int,
)
parser.add_argument("--collection-name", help="Name of the downhole collection.")
parser.add_argument("--upload-path", help="Path to upload objects to.")

parser.add_argument(
    "--overwrite-existing-objects", action="store_true", default=False, help="Overwrite existing objects"
)

parser.add_argument(
    "--no-publish",
    action="store_false",
    dest="publish",
    default=True,
    help="Build the Geoscience object(s) locally without publishing them to Evo. "
    "Useful for trying the converter without credentials.",
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

logger.debug(f"Convert and publish elements from LAS files: {args.filenames}")

# Create temporary cache dir if needed
if args.cache_dir is None:
    tmp_cache_dir = tempfile.TemporaryDirectory()
    args.cache_dir = tmp_cache_dir.name

logger.debug(f"Using cache directory: {args.cache_dir}")

# This allows you to convert an LAS file without needing to fill out any credentials required for publishing
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

# Convert LAS file. If --no-publish is not set and a hub_url is available, the objects will be published.
results = asyncio.run(
    convert_las(
        filepath=args.filenames,
        deviation_files=args.deviation_files[0]
        if args.deviation_files and len(args.deviation_files) == 1
        else args.deviation_files,
        allow_missing_deviation=args.allow_missing_deviation,
        collection_name=args.collection_name,
        evo_workspace_metadata=workspace_metadata,
        coordinate_reference_system=args.epsg_code,
        tags=tags,
        upload_path=args.upload_path,
        overwrite_existing_objects=args.overwrite_existing_objects,
        publish_objects=args.publish,
    )
)

# Results will either be a list of BaseSpatialDataProperties_V1_0_1 if not published, or a list of ObjectMetadata if they were published
for result in results:
    pprint.pp(result, indent=1)
