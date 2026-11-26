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

from dataclasses import dataclass
from typing import Literal

AgsCode = Literal[
    "no_input_files",
    "file_not_found",
    "invalid_file_format",
    "incompatible_merge",
    "invalid_coordinates",
    "unresolved_crs",
    "coordinates_ignored",
    "missing_crs",
    "ground_level_defaulted",
    "hole_dropped",
    "no_collections",
]

MAX_SUMMARY_LENGTH = 320
_MAX_DISPLAY_FILENAME_LENGTH = 60


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."


@dataclass(frozen=True)
class AgsSource:
    """An input of a conversion, identified by its position in the submitted file list and its file name."""

    input_index: int
    filename: str


@dataclass(frozen=True)
class AgsDiagnostic:
    """A structured problem found while importing AGS inputs.

    ``code`` and the optional location fields are the consumer contract; ``reason`` is a short English remedy.
    An ``error`` rejects the affected file or merged group. A ``warning`` reports data that was imported without some
    of its content, such as a dropped hole or an unrecognised coordinate reference system.
    ``sources`` lists every input of the affected file or merged group, and is empty for request-level problems.
    """

    code: AgsCode
    severity: Literal["error", "warning"]
    sources: tuple[AgsSource, ...]
    reason: str
    hole_id: str | None = None
    rule: str | None = None
    group: str | None = None
    line: int | None = None


class AgsParsingError(Exception):
    """Raised when an AGS conversion produces no collections.

    ``diagnostics`` holds every problem found, in input order. The message is a bounded summary for display.
    """

    def __init__(self, diagnostics: tuple[AgsDiagnostic, ...] | list[AgsDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        if not self.diagnostics:
            raise ValueError("AgsParsingError requires at least one diagnostic.")
        super().__init__(self._display_summary())

    def _display_summary(self) -> str:
        filenames = list(
            dict.fromkeys(
                source.filename.replace("`", "'").replace("\r", " ").replace("\n", " ")
                for issue in self.diagnostics
                for source in issue.sources
            )
        )
        if not filenames:
            prefix = "Could not import AGS input"
        else:
            prefix = "Could not import " + ", ".join(
                f"`{_truncate(filename, _MAX_DISPLAY_FILENAME_LENGTH)}`" for filename in filenames[:2]
            )
            if len(filenames) > 2:
                prefix += f" and {len(filenames) - 2} more files"

        reason = self.diagnostics[0].reason.replace("\r", " ").replace("\n", " ").strip()
        remaining = len(self.diagnostics) - 1
        suffix = f" ({remaining} more issue{'s' if remaining != 1 else ''})" if remaining else ""
        reason_limit = MAX_SUMMARY_LENGTH - len(prefix) - len(suffix) - 2
        return f"{prefix}: {_truncate(reason, reason_limit)}{suffix}"
