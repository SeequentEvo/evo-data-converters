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
import errno
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from python_ags4.AGS4 import AGS4Error

from evo.data_converters.ags import AgsDiagnostic, AgsParsingError, AgsSource
from evo.data_converters.ags.common import AgsContext
from evo.data_converters.ags.importer import AgsParsingError as ImporterAgsParsingError
from evo.data_converters.ags.importer.ags_to_downhole_collection import create_from_parsed_ags
from evo.data_converters.ags.importer.ags_to_evo import convert_ags, order_diagnostics, publish_downhole_collections
from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.common.exceptions import ConflictingConnectionDetailsError
from evo.objects.data import ObjectMetadata
from evo.objects.typed import DownholeCollectionData, EpsgCode


def test_convert_ags_saves_elevation_from_selected_coordinate_family(
    evo_metadata: EvoWorkspaceMetadata, test_elevations_ags_path: str
) -> None:
    result = asyncio.run(
        convert_ags(filepaths=[test_elevations_ags_path], evo_workspace_metadata=evo_metadata, publish_objects=False)
    )

    assert len(result) == 1
    collection = result[0]
    assert isinstance(collection, DownholeCollectionData)
    assert collection.properties["hole_id"].tolist() == ["BH01", "BH02", "BH03", "BH04", "BH05"]
    assert collection.properties["z"].tolist() == [-4.78, 16.48, 0.0, 0.0, 0.0]


def test_should_convert_ags_file_without_publish(evo_metadata, valid_ags_1a_path):
    result = asyncio.run(
        convert_ags(filepaths=[valid_ags_1a_path], evo_workspace_metadata=evo_metadata, publish_objects=False)
    )

    assert len(result) == 1
    data = result[0]
    assert isinstance(data, DownholeCollectionData)
    assert data.tags is not None
    assert data.tags["Source"] == "valid_ags_1a (via Evo Data Converters)"
    assert data.tags["Stage"] == "Experimental"
    assert data.tags["InputType"] == "AGS"


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
@patch("evo.data_converters.ags.importer.ags_to_evo.DownholeCollection")
def test_should_publish_with_hub_url(mock_collection, mock_clients, evo_metadata_with_hub, valid_ags_1a_path):
    metadata = Mock(spec=ObjectMetadata)
    mock_collection.create = AsyncMock(return_value=SimpleNamespace(metadata=metadata))
    data_client = Mock()
    context = Mock()
    data_client.get_static_context.return_value = context
    mock_clients.return_value = (Mock(), data_client)

    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path],
            evo_workspace_metadata=evo_metadata_with_hub,
            publish_objects=True,
            upload_path="prefix",
        )
    )

    assert result == [metadata]
    mock_collection.create.assert_awaited_once()
    call = mock_collection.create.await_args
    assert call.args[0] == context
    assert call.kwargs["path"] == "prefix/valid_ags_1a.json"
    data = call.args[1]
    assert data.tags is not None
    assert data.tags["Source"] == "valid_ags_1a (via Evo Data Converters)"
    assert data.tags["Stage"] == "Experimental"
    assert data.tags["InputType"] == "AGS"


def test_should_add_custom_tags(evo_metadata, valid_ags_1a_path):
    custom_tags = {"CustomTag": "CustomValue", "AnotherTag": "AnotherValue"}
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path],
            evo_workspace_metadata=evo_metadata,
            tags=custom_tags,
            publish_objects=False,
        )
    )

    assert len(result) == 1
    assert result[0].tags is not None
    assert result[0].tags["CustomTag"] == "CustomValue"
    assert result[0].tags["AnotherTag"] == "AnotherValue"
    assert result[0].tags["InputType"] == "AGS"


def test_should_handle_parse_error(
    evo_metadata: EvoWorkspaceMetadata, not_ags_path: str, caplog: pytest.LogCaptureFixture
) -> None:
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(convert_ags(filepaths=[not_ags_path], evo_workspace_metadata=evo_metadata, publish_objects=False))

    issue = error.value.diagnostics[0]
    assert issue.code == "invalid_file_format"
    assert issue.sources[0].filename == "not_ags.ags"
    assert issue.rule == "AGS Format Rule 3"
    assert "valid AGS data descriptor" in issue.reason


def test_should_skip_collection_without_locatable_holes(
    evo_metadata: EvoWorkspaceMetadata, test_no_coordinates_ags_path: str, caplog: pytest.LogCaptureFixture
) -> None:
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(
            convert_ags(
                filepaths=[test_no_coordinates_ags_path], evo_workspace_metadata=evo_metadata, publish_objects=False
            )
        )

    issue = error.value.diagnostics[0]
    assert issue.code == "invalid_coordinates"
    assert issue.sources[0].filename == "test_no_coordinates.ags"
    assert "LOCA_NATE/LOCA_NATN" in issue.reason


def test_empty_file_is_not_reported_as_an_empty_input(evo_metadata: EvoWorkspaceMetadata, empty_ags_path: str) -> None:
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(convert_ags(filepaths=[empty_ags_path], evo_workspace_metadata=evo_metadata, publish_objects=False))

    issue = error.value.diagnostics[0]
    assert issue.code != "no_input_files"
    assert issue.sources == (AgsSource(0, "empty.ags"),)


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
@patch("evo.data_converters.ags.importer.ags_to_evo.DownholeCollection")
def test_coordinate_crs_mismatch_is_not_published(
    mock_collection: Mock,
    mock_clients: Mock,
    evo_metadata_with_hub: EvoWorkspaceMetadata,
    valid_ags_1a_path: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    filepath = tmp_path / "mismatched_crs.ags"
    filepath.write_text(Path(valid_ags_1a_path).read_text().replace('"OSGB"', '"WGS84"'))
    mock_clients.return_value = (Mock(), Mock())

    with pytest.raises(AgsParsingError) as error:
        asyncio.run(convert_ags(filepaths=[str(filepath)], evo_workspace_metadata=evo_metadata_with_hub))

    issue = error.value.diagnostics[0]
    assert issue.code == "invalid_coordinates"
    assert issue.sources[0].filename == "mismatched_crs.ags"
    assert "WGS84" not in issue.reason
    assert "OSGB" not in issue.reason
    mock_collection.create.assert_not_called()


@pytest.mark.parametrize("merge_files", [True, False])
def test_coordinate_crs_mismatch_file_is_skipped(
    evo_metadata: EvoWorkspaceMetadata,
    test_elevations_ags_path: str,
    valid_ags_1a_path: str,
    tmp_path: Path,
    merge_files: bool,
) -> None:
    filepath = tmp_path / "mismatched_crs.ags"
    filepath.write_text(Path(valid_ags_1a_path).read_text().replace('"OSGB"', '"WGS84"'))

    result = asyncio.run(
        convert_ags(
            filepaths=[str(filepath), test_elevations_ags_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=merge_files,
        )
    )

    assert [collection.name for collection in result] == ["test_elevations"]


@pytest.mark.parametrize("merge_files", [True, False])
def test_conflicting_crs_file_is_skipped(
    evo_metadata: EvoWorkspaceMetadata,
    test_elevations_ags_path: str,
    conflicting_crs_ags_path: str,
    merge_files: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = asyncio.run(
        convert_ags(
            filepaths=[test_elevations_ags_path, conflicting_crs_ags_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=merge_files,
        )
    )

    assert len(result) == 1
    assert result[0].name == "test_elevations"
    assert "LOCA rows declare different coordinate reference systems" in caplog.text


def test_duplicate_loca_id_across_files_raises_warning(evo_metadata, valid_ags_2a_path, invalid_ags_2b_path, caplog):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_2a_path, invalid_ags_2b_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
        )
    )

    assert len(result) == 1
    for message in (
        "Found 1 duplicate LOCA_ID values when merging contexts.",
        "Duplicate IDs: ['EXAMPLE-2-CPT1']",
        "Found 1 duplicate (LOCA_ID, SCPG_TESN) pairs when merging contexts.",
    ):
        assert message in caplog.text


def test_convert_ags_with_multiple_files_from_different_projects(evo_metadata, valid_ags_1a_path, valid_ags_2a_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_2a_path], evo_workspace_metadata=evo_metadata, publish_objects=False
        )
    )

    assert len(result) == 2
    assert all(isinstance(item, DownholeCollectionData) for item in result)


def test_convert_ags_with_multiple_files_same_project(evo_metadata, valid_ags_1a_path, valid_ags_1b_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_1b_path], evo_workspace_metadata=evo_metadata, publish_objects=False
        )
    )

    assert len(result) == 1
    data = result[0]
    assert isinstance(data, DownholeCollectionData)
    assert data.name == "valid_ags_1a"
    assert data.tags is not None
    assert data.tags["InputType"] == "AGS"
    assert data.tags["Source"] == "valid_ags_1a (via Evo Data Converters)"
    assert data.coordinate_reference_system == 27700


def test_convert_ags_with_multiple_files_same_project_no_merge(evo_metadata, valid_ags_1a_path, valid_ags_1b_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_1b_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=False,
        )
    )

    assert len(result) == 2
    assert {item.name for item in result} == {"valid_ags_1a", "valid_ags_1b"}
    assert all(item.tags is not None and item.tags["InputType"] == "AGS" for item in result)


def test_same_file_twice_without_merge_converts_each_input(
    evo_metadata: EvoWorkspaceMetadata, valid_ags_1a_path: str
) -> None:
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_1a_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=False,
        )
    )

    assert [item.name for item in result] == ["valid_ags_1a", "valid_ags_1a"]


def test_convert_ags_with_mixed_projects(evo_metadata, valid_ags_1a_path, valid_ags_1b_path, valid_ags_2a_path):
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, valid_ags_1b_path, valid_ags_2a_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
        )
    )

    assert len(result) == 2
    assert all(item.tags is not None and item.tags["InputType"] == "AGS" for item in result)


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
def test_convert_ags_with_empty_file_list(mock_clients, evo_metadata):
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(convert_ags(filepaths=[], evo_workspace_metadata=evo_metadata, publish_objects=False))

    issue = error.value.diagnostics[0]
    assert issue.code == "no_input_files"
    assert issue.sources == ()
    assert issue.reason == "Select at least one AGS file."
    mock_clients.assert_not_called()


@pytest.mark.parametrize("merge_files", [True, False])
def test_partial_success_reports_bad_file_with_original_input_index(
    evo_metadata: EvoWorkspaceMetadata,
    valid_ags_1a_path: str,
    not_ags_path: str,
    merge_files: bool,
) -> None:
    issues: list[AgsDiagnostic] = []
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, not_ags_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=merge_files,
            diagnostics=issues,
        )
    )

    assert len(result) == 1
    warning, *errors = issues
    assert (warning.code, warning.sources) == ("ground_level_defaulted", (AgsSource(0, "valid_ags_1a.ags"),))
    assert all(issue.code == "invalid_file_format" for issue in errors)
    assert all(issue.sources == (AgsSource(1, "not_ags.ags"),) for issue in errors)
    assert errors[0].rule == "AGS Format Rule 3"
    json.dumps([asdict(issue) for issue in issues])


def test_preexisting_diagnostics_are_preserved_on_success(
    evo_metadata: EvoWorkspaceMetadata, valid_ags_1a_path: str
) -> None:
    existing = AgsDiagnostic("hole_dropped", "warning", (AgsSource(42, "prior.ags"),), "Prior warning", "BH0")
    issues = [existing]
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            diagnostics=issues,
        )
    )

    assert len(result) == 1
    assert issues[0] == existing
    assert [issue.code for issue in issues[1:]] == ["ground_level_defaulted"]


def test_failure_does_not_modify_diagnostics(evo_metadata: EvoWorkspaceMetadata, not_ags_path: str) -> None:
    existing = AgsDiagnostic("hole_dropped", "warning", (AgsSource(42, "prior.ags"),), "Prior warning", "BH0")
    issues = [existing]
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(
            convert_ags(
                filepaths=[not_ags_path],
                evo_workspace_metadata=evo_metadata,
                publish_objects=False,
                diagnostics=issues,
            )
        )

    assert issues == [existing]
    assert error.value.diagnostics[0].sources[0].filename == "not_ags.ags"


def test_diagnostic_types_are_exported_from_both_public_surfaces() -> None:
    from evo.data_converters.ags import AgsCode as PackageCode
    from evo.data_converters.ags import AgsDiagnostic as PackageDiagnostic
    from evo.data_converters.ags import AgsSource as PackageSource
    from evo.data_converters.ags.common import AgsIncompatibleMergeError
    from evo.data_converters.ags.common.ags_context import AgsIncompatibleMergeError as ContextMergeError
    from evo.data_converters.ags.importer import AgsCode as ImporterCode
    from evo.data_converters.ags.importer import AgsDiagnostic as ImporterDiagnostic
    from evo.data_converters.ags.importer import AgsSource as ImporterSource

    assert PackageCode is ImporterCode
    assert PackageDiagnostic is ImporterDiagnostic is AgsDiagnostic
    assert PackageSource is ImporterSource is AgsSource
    assert ImporterAgsParsingError is AgsParsingError
    assert AgsIncompatibleMergeError is ContextMergeError


def _invalid_file(*sources: AgsSource) -> AgsDiagnostic:
    return AgsDiagnostic("invalid_file_format", "error", sources, "Fix it.")


@pytest.mark.parametrize(
    ("issues", "expected"),
    [
        ([_invalid_file()], "Could not import AGS input: Fix it."),
        ([_invalid_file(AgsSource(0, "a.ags"))], "Could not import `a.ags`: Fix it."),
        (
            [_invalid_file(AgsSource(0, "a.ags")), _invalid_file(AgsSource(0, "a.ags"))],
            "Could not import `a.ags`: Fix it. (1 more issue)",
        ),
        (
            [_invalid_file(AgsSource(0, "a.ags"), AgsSource(1, "b.ags"))],
            "Could not import `a.ags`, `b.ags`: Fix it.",
        ),
        (
            [_invalid_file(AgsSource(index, f"{name}.ags")) for index, name in enumerate("abcd")],
            "Could not import `a.ags`, `b.ags` and 2 more files: Fix it. (3 more issues)",
        ),
        ([_invalid_file(AgsSource(0, "a`b\r\nc.ags"))], "Could not import `a'b  c.ags`: Fix it."),
    ],
    ids=["no_sources", "one_file", "repeated_file", "two_files", "more_files", "escaped_filename"],
)
def test_parsing_error_summary(issues: list[AgsDiagnostic], expected: str) -> None:
    assert str(AgsParsingError(issues)) == expected


def test_parsing_error_requires_a_diagnostic() -> None:
    with pytest.raises(ValueError, match="at least one diagnostic"):
        AgsParsingError(())


def test_order_diagnostics_puts_request_level_issues_first_then_input_order() -> None:
    late = _invalid_file(AgsSource(2, "c.ags"))
    merged = _invalid_file(AgsSource(3, "d.ags"), AgsSource(0, "a.ags"))
    request = _invalid_file()

    assert order_diagnostics([late, merged, request]) == [request, merged, late]


def test_parsing_error_summary_is_bounded_and_keeps_structured_records() -> None:
    issues = [
        AgsDiagnostic(
            "invalid_file_format",
            "error",
            (AgsSource(index, f"survey-{index}.ags"),),
            "An actionable reason. " + ("x" * 500),
            rule="AGS Format Rule 3",
        )
        for index in range(8)
    ]
    error = AgsParsingError(issues)

    assert len(str(error)) <= 320
    assert str(error).endswith("... (7 more issues)")
    assert "and 6 more files" in str(error)
    assert error.diagnostics == tuple(issues)
    assert "survey-0.ags" in str(error)
    assert "Traceback" not in str(error)


@pytest.mark.parametrize("source_count", [1, 2, 8])
def test_parsing_error_summary_reserves_space_for_the_reason_with_long_filenames(source_count: int) -> None:
    reason = "No holes have a complete coordinate pair. Fill in LOCA_NATE and LOCA_NATN."
    sources = tuple(AgsSource(index, f"{index}-{'x' * 190}.ags") for index in range(source_count))
    issue = AgsDiagnostic("invalid_coordinates", "error", sources, reason)

    error = AgsParsingError([issue])
    summary = str(error)

    assert len(summary) <= 320
    assert reason in summary
    assert summary.count("`") == 2 * min(source_count, 2)
    assert "...`" in summary
    if source_count > 2:
        assert f"and {source_count - 2} more files" in summary
    assert error.diagnostics == (issue,)


@pytest.mark.parametrize("merge_files", [True, False])
def test_public_conversion_reports_dropped_hole(
    evo_metadata: EvoWorkspaceMetadata,
    test_elevations_ags_path: str,
    tmp_path: Path,
    merge_files: bool,
) -> None:
    content = Path(test_elevations_ags_path).read_text()
    content = content.replace('"BH02","200.00","2000.00","OSGB"', '"BH02","","","OSGB"')
    filepath = tmp_path / "partial_coordinates.ags"
    filepath.write_text(content)
    issues: list[AgsDiagnostic] = []

    result = asyncio.run(
        convert_ags(
            filepaths=[str(filepath)],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=merge_files,
            diagnostics=issues,
        )
    )

    assert len(result) == 1
    assert result[0].properties["hole_id"].tolist() == ["BH01", "BH03", "BH04", "BH05"]
    assert [(issue.code, issue.hole_id) for issue in issues] == [
        ("hole_dropped", "BH02"),
        ("ground_level_defaulted", "BH04"),
        ("ground_level_defaulted", "BH05"),
    ]
    assert all(issue.sources == (AgsSource(0, filepath.name),) and issue.severity == "warning" for issue in issues)


@pytest.mark.parametrize(
    ("grid", "expected_crs", "codes"),
    [("NZTM 2000", EpsgCode(2193), []), ("NOT A GRID", None, ["unresolved_crs"]), ("", None, ["missing_crs"])],
)
def test_public_conversion_resolves_grid_names(
    evo_metadata: EvoWorkspaceMetadata,
    test_elevations_ags_path: str,
    tmp_path: Path,
    grid: str,
    expected_crs: EpsgCode | None,
    codes: list[str],
) -> None:
    filepath = tmp_path / "grid.ags"
    filepath.write_text(Path(test_elevations_ags_path).read_text().replace('"OSGB"', f'"{grid}"'))
    issues: list[AgsDiagnostic] = []

    result = asyncio.run(
        convert_ags(
            filepaths=[str(filepath)],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            diagnostics=issues,
        )
    )

    assert len(result) == 1
    assert result[0].coordinate_reference_system == expected_crs
    assert [issue.code for issue in issues] == [*codes, "ground_level_defaulted", "ground_level_defaulted"]
    assert all(issue.hole_id is None for issue in issues[: len(codes)])
    assert all(issue.severity == "warning" and issue.group == "LOCA" for issue in issues)
    assert all(issue.sources == (AgsSource(0, "grid.ags"),) for issue in issues)


def test_merge_failure_reports_incoming_file_and_keeps_accepted_collection(
    evo_metadata: EvoWorkspaceMetadata, valid_ags_2a_path: str, invalid_ags_2d_path: str
) -> None:
    issues: list[AgsDiagnostic] = []
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_2a_path, invalid_ags_2d_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            diagnostics=issues,
        )
    )

    assert len(result) == 1
    assert result[0].name == "valid_ags_2a"
    assert [(issue.code, issue.sources) for issue in issues] == [
        ("ground_level_defaulted", (AgsSource(0, "valid_ags_2a.ags"),)),
        ("incompatible_merge", (AgsSource(1, "invalid_ags_2d.ags"),)),
    ]


def test_unexpected_merge_error_propagates_unchanged(
    evo_metadata: EvoWorkspaceMetadata, valid_ags_1a_path: str, valid_ags_1b_path: str
) -> None:
    sentinel = ValueError("unexpected merge failure")
    with patch.object(AgsContext, "merge", side_effect=sentinel):
        with pytest.raises(ValueError) as error:
            asyncio.run(
                convert_ags(
                    filepaths=[valid_ags_1a_path, valid_ags_1b_path],
                    evo_workspace_metadata=evo_metadata,
                    publish_objects=False,
                )
            )

    assert error.value is sentinel


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
@patch("evo.data_converters.ags.importer.ags_to_evo.DownholeCollection")
def test_partial_publish_publishes_only_surviving_collections(
    mock_collection: Mock,
    mock_clients: Mock,
    evo_metadata_with_hub: EvoWorkspaceMetadata,
    valid_ags_1a_path: str,
    not_ags_path: str,
) -> None:
    metadata = Mock(spec=ObjectMetadata)
    mock_collection.create = AsyncMock(return_value=SimpleNamespace(metadata=metadata))
    data_client = Mock()
    context = Mock()
    data_client.get_static_context.return_value = context
    mock_clients.return_value = (Mock(), data_client)
    issues: list[AgsDiagnostic] = []

    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, not_ags_path],
            evo_workspace_metadata=evo_metadata_with_hub,
            diagnostics=issues,
        )
    )

    assert result == [metadata]
    mock_collection.create.assert_awaited_once()
    assert issues[0].code == "ground_level_defaulted"
    assert any(issue.code == "invalid_file_format" for issue in issues[1:])
    assert all(issue.sources[0].input_index == 1 for issue in issues[1:])


def test_same_basename_failures_remain_distinguishable(evo_metadata: EvoWorkspaceMetadata, tmp_path: Path) -> None:
    source_paths = [tmp_path / "first" / "missing.ags", tmp_path / "second" / "missing.ags"]
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(
            convert_ags(
                filepaths=[str(path) for path in source_paths],
                evo_workspace_metadata=evo_metadata,
                publish_objects=False,
            )
        )

    assert [(issue.sources[0].input_index, issue.sources[0].filename) for issue in error.value.diagnostics] == [
        (0, "missing.ags"),
        (1, "missing.ags"),
    ]
    assert all(issue.code == "file_not_found" for issue in error.value.diagnostics)


@pytest.mark.parametrize("merge_files", [True, False])
@pytest.mark.parametrize("disappear_after_validation", [True, False])
def test_disappearing_input_does_not_cancel_surviving_files(
    evo_metadata: EvoWorkspaceMetadata,
    valid_ags_1a_path: str,
    valid_ags_2a_path: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    merge_files: bool,
    disappear_after_validation: bool,
) -> None:
    disappearing = tmp_path / "disappearing.ags"
    disappearing.write_text(Path(valid_ags_1a_path).read_text())
    check_ags_file = AgsContext.check_ags_file

    def check_with_removal(context: AgsContext, filepath: str) -> None:
        is_disappearing_input = filepath == str(disappearing)
        if is_disappearing_input and not disappear_after_validation:
            disappearing.unlink()
        check_ags_file(context, filepath)
        if is_disappearing_input and disappear_after_validation:
            disappearing.unlink()

    monkeypatch.setattr(AgsContext, "check_ags_file", check_with_removal)
    issues: list[AgsDiagnostic] = []
    result = asyncio.run(
        convert_ags(
            filepaths=[valid_ags_1a_path, str(disappearing), valid_ags_2a_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            merge_files=merge_files,
            diagnostics=issues,
        )
    )

    assert [collection.name for collection in result] == ["valid_ags_1a", "valid_ags_2a"]
    assert [(issue.code, issue.sources) for issue in issues] == [
        ("ground_level_defaulted", (AgsSource(0, "valid_ags_1a.ags"),)),
        ("file_not_found", (AgsSource(1, "disappearing.ags"),)),
        ("ground_level_defaulted", (AgsSource(2, "valid_ags_2a.ags"),)),
    ]


@pytest.mark.parametrize(
    "sentinel",
    [
        FileNotFoundError("missing parser dependency"),
        FileNotFoundError(errno.ENOENT, "missing parser dependency", "parser-data\\valid_ags_1a.ags"),
        PermissionError("unreadable input"),
        RuntimeError("unexpected parser failure"),
    ],
    ids=["unnamed-missing-dependency", "missing-dependency", "permission", "unexpected"],
)
def test_unrelated_read_errors_propagate_unchanged(
    sentinel: Exception, evo_metadata: EvoWorkspaceMetadata, valid_ags_1a_path: str
) -> None:
    existing = _invalid_file(AgsSource(42, "prior.ags"))
    issues = [existing]
    with patch.object(AgsContext, "parse_ags", side_effect=sentinel):
        with pytest.raises(type(sentinel)) as error:
            asyncio.run(
                convert_ags(
                    filepaths=[valid_ags_1a_path],
                    evo_workspace_metadata=evo_metadata,
                    publish_objects=False,
                    diagnostics=issues,
                )
            )

    assert error.value is sentinel
    assert issues == [existing]


def test_failures_from_parse_and_collection_stages_are_both_reported(
    evo_metadata: EvoWorkspaceMetadata, not_ags_path: str, test_no_coordinates_ags_path: str
) -> None:
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(
            convert_ags(
                filepaths=[not_ags_path, test_no_coordinates_ags_path],
                evo_workspace_metadata=evo_metadata,
                publish_objects=False,
                merge_files=False,
            )
        )

    assert {issue.code for issue in error.value.diagnostics} == {"invalid_file_format", "invalid_coordinates"}
    assert {source.input_index for issue in error.value.diagnostics for source in issue.sources} == {0, 1}


def test_merged_collection_failure_names_all_accepted_inputs(
    evo_metadata: EvoWorkspaceMetadata, test_no_coordinates_ags_path: str
) -> None:
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(
            convert_ags(
                filepaths=[test_no_coordinates_ags_path, test_no_coordinates_ags_path],
                evo_workspace_metadata=evo_metadata,
                publish_objects=False,
            )
        )

    assert len(error.value.diagnostics) == 1
    issue = error.value.diagnostics[0]
    assert issue.code == "invalid_coordinates"
    assert issue.sources == (AgsSource(0, "test_no_coordinates.ags"), AgsSource(1, "test_no_coordinates.ags"))


def test_raw_ags4_error_does_not_cancel_later_files(
    evo_metadata: EvoWorkspaceMetadata, not_ags_path: str, valid_ags_1a_path: str
) -> None:
    with patch.object(AgsContext, "check_ags_file", side_effect=[AGS4Error("validator error"), None]):
        issues: list[AgsDiagnostic] = []
        result = asyncio.run(
            convert_ags(
                filepaths=[not_ags_path, valid_ags_1a_path],
                evo_workspace_metadata=evo_metadata,
                publish_objects=False,
                diagnostics=issues,
            )
        )

    assert len(result) == 1
    assert [(issue.code, issue.sources) for issue in issues] == [
        ("invalid_file_format", (AgsSource(0, "not_ags.ags"),)),
        ("ground_level_defaulted", (AgsSource(1, "valid_ags_1a.ags"),)),
    ]


@patch("evo.data_converters.ags.importer.ags_to_evo.create_from_parsed_ags")
@patch("evo.data_converters.ags.importer.ags_to_evo.parse_ags_files", return_value=[])
def test_empty_lower_layer_result_uses_no_collections_fallback(
    mock_parse: Mock, mock_convert: Mock, evo_metadata: EvoWorkspaceMetadata, valid_ags_1a_path: str
) -> None:
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(
            convert_ags(
                filepaths=[valid_ags_1a_path],
                evo_workspace_metadata=evo_metadata,
                publish_objects=False,
            )
        )

    assert error.value.diagnostics[0].code == "no_collections"
    assert error.value.diagnostics[0].sources == (AgsSource(0, "valid_ags_1a.ags"),)
    mock_parse.assert_called_once()
    mock_convert.assert_not_called()


@patch("evo.data_converters.ags.importer.ags_to_evo.publish_downhole_collections", new_callable=AsyncMock)
def test_publish_failure_does_not_modify_diagnostics(
    mock_publish: AsyncMock,
    evo_metadata_with_hub: EvoWorkspaceMetadata,
    valid_ags_1a_path: str,
    not_ags_path: str,
) -> None:
    existing = AgsDiagnostic("hole_dropped", "warning", (AgsSource(42, "prior.ags"),), "Prior warning", "BH0")
    issues = [existing]
    publish_error = RuntimeError("publish sentinel")

    def fail_publication(*args: object, **kwargs: object) -> None:
        assert issues == [existing]
        raise publish_error

    mock_publish.side_effect = fail_publication

    with pytest.raises(RuntimeError) as error:
        asyncio.run(
            convert_ags(
                filepaths=[valid_ags_1a_path, not_ags_path],
                evo_workspace_metadata=evo_metadata_with_hub,
                diagnostics=issues,
            )
        )

    assert error.value is publish_error
    assert issues == [existing]
    mock_publish.assert_awaited_once()


@patch("evo.data_converters.ags.importer.ags_to_evo.create_evo_object_service_and_data_client")
def test_publish_requires_hub_url(mock_clients, evo_metadata, valid_ags_1a_path):
    mock_clients.return_value = (Mock(), Mock())
    with pytest.raises(ConflictingConnectionDetailsError, match="without hub_url"):
        asyncio.run(convert_ags(filepaths=[valid_ags_1a_path], evo_workspace_metadata=evo_metadata))
    mock_clients.assert_called_once()


@pytest.mark.parametrize("overwrite, method", [(False, "create"), (True, "create_or_replace")])
@patch("evo.data_converters.ags.importer.ags_to_evo.DownholeCollection")
def test_publish_downhole_collections(mock_collection, overwrite, method, mock_ags_context):
    mock_ags_context.filename = "test_file"
    data = create_from_parsed_ags(mock_ags_context)
    context = Mock()
    environment = Mock()
    environment.hub_url = "https://test.hub.url"
    environment.org_id = "00000000-0000-0000-0000-000000000001"
    environment.workspace_id = "00000000-0000-0000-0000-000000000002"
    context.get_environment.return_value = environment
    metadata = Mock(spec=ObjectMetadata)
    publish = AsyncMock(return_value=SimpleNamespace(metadata=metadata))
    setattr(mock_collection, method, publish)

    result = asyncio.run(
        publish_downhole_collections([data, data], context, "prefix", overwrite_existing_objects=overwrite)
    )

    assert result == [metadata, metadata]
    assert publish.await_count == 2
    if overwrite:
        assert [call.args[1].object_path for call in publish.await_args_list] == [
            "prefix/test_file_1.json",
            "prefix/test_file_2.json",
        ]
    else:
        assert [call.kwargs["path"] for call in publish.await_args_list] == [
            "prefix/test_file_1.json",
            "prefix/test_file_2.json",
        ]
