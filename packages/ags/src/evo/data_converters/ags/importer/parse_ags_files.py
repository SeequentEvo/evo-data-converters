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

import evo.logging
from evo.data_converters.ags.common.ags_context import AgsContext, AgsFileInvalidException

logger = evo.logging.getLogger("data_converters")


def parse_ags_files(filepaths: list[str]) -> dict[str, AgsContext]:
    """Parse one or more AGS files and group results by PROJ_ID.

    :param filepaths: List of paths to AGS files.
    :return: Mapping of ``PROJ_ID`` to an ``AgsContext`` containing parsed tables.
    """
    ags_contexts: dict[str, AgsContext] = {}
    for filepath in filepaths:
        # TODO: Handle exceptions for individual files (log and continue, or fail the whole operation?)
        # TODO: Parallelize parsing if needed (IO bound)
        try:
            ags_context = parse_ags_file(filepath)
        except AgsFileInvalidException:
            continue

        if ags_context.proj_id in ags_contexts:
            logger.info(f"Merging AGS file '{filepath}' into existing PROJ_ID '{ags_context.proj_id}'.")
            ags_contexts[ags_context.proj_id].merge(ags_context)
        else:
            ags_contexts[ags_context.proj_id] = ags_context

        del ags_context

    return ags_contexts


def parse_ags_file(filepath: str) -> AgsContext:
    """Parses a single AGS file into an AgsContext object.

    :param filepath: Path to the AGS file.
    :return: AgsContext with parsed dataframes.
    :raises AgsFileInvalidException: If the AGS file is invalid.
    """
    try:
        ags_context = AgsContext()
        ags_context.parse_ags(filepath)
        logger.info(f"Loaded AGS file '{filepath}' with PROJ_ID '{ags_context.proj_id}'.")
        return ags_context

    except (FileNotFoundError, AgsFileInvalidException) as e:
        logger.error(f"Failed to parse AGS file '{filepath}': {e}")
        raise AgsFileInvalidException(f"Failed to parse AGS file '{filepath}': {e}") from e
