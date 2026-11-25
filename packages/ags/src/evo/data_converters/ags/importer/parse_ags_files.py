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

from dataclasses import replace
from pathlib import Path

import evo.logging
from evo.data_converters.ags.common.ags_context import AgsContext, AgsFileInvalidException, AgsIncompatibleMergeError
from evo.data_converters.ags.diagnostics import AgsDiagnostic, AgsSource

logger = evo.logging.getLogger("data_converters")


def parse_ags_files(
    filepaths: list[str],
    merge_files: bool = True,
    *,
    diagnostics: list[AgsDiagnostic] | None = None,
) -> list[AgsContext]:
    """Parse one or more AGS files and group results by PROJ_ID.

    Input failures are logged and accumulated in ``diagnostics`` without stopping later files.

    :param filepaths: List of paths to AGS files.
    :param merge_files: Whether to merge files with the same PROJ_ID into a single AgsContext
        (optional, default True).
    :param diagnostics: Optional list extended with structured input failures.
    :return: List of ``AgsContext`` objects containing parsed tables.
    """
    ags_contexts: dict[str | int, AgsContext] = {}
    issues: list[AgsDiagnostic] = []
    for input_index, filepath in enumerate(filepaths):
        source = AgsSource(input_index=input_index, filename=Path(filepath).name)
        try:
            ags_context: AgsContext = parse_ags_file(filepath)
        except AgsFileInvalidException as exc:
            logger.error(f"Failed to parse AGS file '{filepath}': {exc}")
            issues.extend(diagnostics_for_exception(exc, (source,)))
            continue
        ags_context.sources = (source,)

        if merge_files and ags_context.proj_id in ags_contexts:
            logger.info(f"Merging AGS file '{filepath}' into existing PROJ_ID '{ags_context.proj_id}'.")
            try:
                ags_contexts[ags_context.proj_id].merge(ags_context)
            except AgsIncompatibleMergeError as e:
                logger.error(f"Failed to merge AGS file '{filepath}': {e}")
                issues.append(
                    AgsDiagnostic(
                        code="incompatible_merge",
                        severity="error",
                        sources=(source,),
                        reason=(
                            "Files with the same PROJ_ID must have compatible coordinate reference systems, "
                            "project metadata and column units."
                        ),
                    )
                )
                continue
            existing = ags_contexts[ags_context.proj_id]
            existing.sources = (*existing.sources, source)
        else:
            # When merge_files=False, key by input position so repeated paths stay separate
            key = ags_context.proj_id if merge_files else input_index
            ags_contexts[key] = ags_context

    if diagnostics is not None:
        diagnostics.extend(issues)
    return list(ags_contexts.values())


def parse_ags_file(filepath: str) -> AgsContext:
    """Parses a single AGS file into an AgsContext object.

    :param filepath: Path to the AGS file.
    :return: AgsContext with parsed dataframes.
    :raises AgsFileInvalidException: If the AGS file is missing or invalid.
    """
    ags_context = AgsContext()
    try:
        ags_context.parse_ags(filepath)
    except FileNotFoundError as e:
        if not isinstance(e.filename, (str, Path)) or Path(e.filename).absolute() != Path(filepath).absolute():
            raise
        raise AgsFileInvalidException(
            "AGS input file was not found.",
            code="file_not_found",
            reason="Check that the AGS file exists and the path is correct.",
        ) from e

    logger.info(f"Loaded AGS file '{filepath}' with PROJ_ID '{ags_context.proj_id}'.")
    return ags_context


def diagnostics_for_exception(exc: AgsFileInvalidException, sources: tuple[AgsSource, ...]) -> list[AgsDiagnostic]:
    """Convert an input failure to error diagnostics attributed to ``sources``.

    Validator diagnostics carried by the exception are kept individually; otherwise its single cause is used.
    """
    if exc.diagnostics:
        return [replace(issue, sources=sources) for issue in exc.diagnostics]
    return [
        AgsDiagnostic(
            code=exc.code,
            severity="error",
            sources=sources,
            reason=exc.reason,
            rule=exc.rule,
            group=exc.group,
            line=exc.line,
        )
    ]
