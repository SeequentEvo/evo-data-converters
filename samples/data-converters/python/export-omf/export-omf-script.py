import argparse
import logging
import tempfile
import uuid

from evo.data_converters.common import EvoObjectMetadata, EvoWorkspaceMetadata
from evo.data_converters.omf import OMFMetadata
from evo.data_converters.omf.exporter import export_omf

parser = argparse.ArgumentParser(description="Export Evo Object(s) to an OMF v1 file")

parser.add_argument("filename", help="Path of the OMF file to create.")

parser.add_argument(
    "--object",
    action="append",
    help="UUID of an Evo object to export, with an optional colon-separated version of the object. "
    "Defaults to the latest version. Supply multiple --object arguments to export multiple "
    "objects to the OMF file.",
    required=True,
    default=[],
)

parser.add_argument("--workspace-id", help="Workspace UUID of the workspace the object belongs to.", required=True)
parser.add_argument("--org-id", help="UUID of the organization the workspace belongs to.", required=True)
parser.add_argument("--hub-url", help="URL of the hub the workspace resides in.", required=True)

parser.add_argument("--client-id", help="OAuth client ID as registered with the OAuth provider.", required=True)
parser.add_argument("--oidc-issuer", help="OpenID Connect issuer URL.", default="")
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

# OMF metadata
parser.add_argument("--name", help="Name to embed in the OMF project.", default="")
parser.add_argument("--revision", help="Revision or version to embed in the OMF project.", default="")
parser.add_argument("--description", help="Description of the object data to embed in the OMF project.", default="")

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
    oidc_issuer=args.oidc_issuer,
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
    logger.debug(f"Exporting Evo object '{object_metadata.object_id}' to OMF file '{args.filename}'")

omf_metadata = OMFMetadata(name=args.name, revision=args.revision, description=args.description)

export_omf(
    args.filename,
    objects=objects,
    omf_metadata=omf_metadata,
    evo_workspace_metadata=workspace_metadata,
)
