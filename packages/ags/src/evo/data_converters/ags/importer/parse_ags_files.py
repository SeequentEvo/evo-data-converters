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


def parse_ags_files(filepaths: list[str], merge_files: bool = True) -> list[AgsContext]:
    """Parse one or more AGS files and group results by PROJ_ID.

    Major errors will fail to create a downhole collection,
    while warnings will be logged. Execution does not break
    early if a failure occurs, and a list of failed files is
    logged.

    .. todo:: Parallelise parsing of multiple files if necessary.

    :param filepaths: List of paths to AGS files.
    :param merge_files: Whether to merge files with the same PROJ_ID into a single AgsContext
        (optional, default True).
    :return: List of ``AgsContext`` objects containing parsed tables.
    """
    ags_contexts: dict[str, AgsContext] = {}
    parse_failed_files: list[str] = []
    for filepath in filepaths:
        try:
            ags_context: AgsContext = parse_ags_file(filepath)
        except AgsFileInvalidException:
            parse_failed_files.append(filepath)
            continue

        if merge_files and ags_context.proj_id in ags_contexts:
            logger.info(f"Merging AGS file '{filepath}' into existing PROJ_ID '{ags_context.proj_id}'.")
            try:
                ags_contexts[ags_context.proj_id].merge(ags_context)
            except ValueError as e:
                logger.error(f"Failed to merge AGS file '{filepath}': {e}")
                parse_failed_files.append(filepath)
                continue
        else:
            # When merge_files=False, use filepath as key to ensure uniqueness
            key = ags_context.proj_id if merge_files else filepath
            ags_contexts[key] = ags_context

    if parse_failed_files:
        logger.error(f"Failed to parse the following AGS files: {', '.join(parse_failed_files)}")

    return list(ags_contexts.values())


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
