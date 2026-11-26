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

import asyncio
import csv
from pathlib import Path

import pytest

from evo.data_converters.ags import AgsDiagnostic, AgsParsingError, AgsSource, convert_ags
from evo.data_converters.ags.common import AgsContext
from evo.data_converters.ags.importer import create_from_parsed_ags
from evo.data_converters.common import EvoWorkspaceMetadata
from evo.objects.typed import DownholeCollectionData


def with_units(source: str, destination: Path, **units: str) -> Path:
    """Copy a fixture, changing only the specified headings' UNIT entries."""
    with Path(source).open(newline="") as src, destination.open("w", newline="") as dst:
        writer = csv.writer(dst, quoting=csv.QUOTE_ALL)
        headings: list[str] = []
        for row in csv.reader(src):
            if row and row[0] == "HEADING":
                headings = row
            elif row and row[0] == "UNIT":
                row = [units.get(heading, value) for heading, value in zip(headings, row, strict=True)]
            writer.writerow(row)
    return destination


def set_loca_reference(filepath: Path, column: str, value: str) -> None:
    """Set one LOCA reference and clear the reference for the other horizontal family."""
    with filepath.open(newline="") as src:
        rows = list(csv.reader(src))

    group = ""
    loca_headings: list[str] = []
    for row in rows:
        if not row:
            continue
        if row[0] == "GROUP":
            group = row[1]
        elif group == "LOCA" and row[0] == "HEADING":
            loca_headings = row
        elif group == "LOCA" and row[0] == "DATA":
            row[loca_headings.index("LOCA_GREF")] = "" if column == "LOCA_LLZ" else value
            row[loca_headings.index("LOCA_LLZ")] = value if column == "LOCA_LLZ" else ""

    with filepath.open("w", newline="") as dst:
        csv.writer(dst, quoting=csv.QUOTE_ALL).writerows(rows)


def test_local_xyz_uses_each_columns_unit_without_mutating_the_source(test_coordinate_columns_ags_path: str) -> None:
    ctx = AgsContext()
    ctx.parse_ags(test_coordinate_columns_ags_path)
    loca = ctx.get_table("LOCA")
    loca["LOCA_LREF"] = "SITE"
    loca[["LOCA_NATE", "LOCA_NATN", "LOCA_LON", "LOCA_LAT"]] = None
    ctx.set_units("LOCA", {**ctx.get_units("LOCA"), "LOCA_LOCX": "ft", "LOCA_LOCY": "cm", "LOCA_LOCZ": "mm"})

    dhc = create_from_parsed_ags(ctx)

    assert dhc.properties["hole_id"].tolist() == ["BH02", "BH04"]
    assert dhc.distance_unit == "ft"
    assert dhc.properties["x"].tolist() == [300.0, 700.0]
    assert dhc.properties["y"].tolist() == pytest.approx([4.0 / 0.3048, 8.0 / 0.3048])
    assert dhc.properties["z"].tolist() == pytest.approx([0.010 / 0.3048, 0.015 / 0.3048])
    assert dhc.attributes is not None
    assert dhc.attributes["LOCA_LOCY"].tolist() == [400.0, 800.0]
    assert dhc.attributes.attrs["attribute_descriptions"]["LOCA_LOCY"].unit == "cm"
    assert ctx.get_units("LOCA")["LOCA_LOCZ"] == "mm"
    assert ctx.get_table("LOCA")["LOCA_LOCZ"].dropna().tolist() == [10.0, 15.0]


def test_collections_keep_source_units_while_path_and_final_depths_use_the_crs_unit(
    evo_metadata: EvoWorkspaceMetadata, multiple_pushes_ags_path: str, tmp_path: Path
) -> None:
    path = with_units(
        multiple_pushes_ags_path,
        tmp_path / "mixed.ags",
        LOCA_NATE="cm",
        LOCA_NATN="mm",
        LOCA_FDEP="ft",
        SCPT_DPTH="cm",
        SCPP_TOP="mm",
        SCPP_BASE="cm",
        GEOL_TOP="mm",
        GEOL_BASE="cm",
    )
    with path.open("a") as out:
        out.write(
            '\n"GROUP","HORN"\n"HEADING","LOCA_ID","HORN_TOP","HORN_BASE","HORN_ORNT","HORN_INCL"\n'
            '"UNIT","","mm","cm","deg","deg"\n"TYPE","ID","2DP","2DP","0DP","0DP"\n'
            '"DATA","CPT-14","10.00","2.00","135","45"\n'
        )
    (dhc,) = asyncio.run(convert_ags([str(path)], evo_workspace_metadata=evo_metadata, publish_objects=False))
    assert isinstance(dhc, DownholeCollectionData)
    assert dhc.distance_unit == "m"
    assert dhc.properties[["x", "y"]].values.tolist() == [[1.0, 1.0], [2.0, 2.0]]
    assert dhc.attributes is not None
    assert dhc.attributes["LOCA_FDEP"].tolist() == [3.5, 1.0]
    assert dhc.attributes.attrs["attribute_descriptions"]["LOCA_FDEP"].unit == "ft"
    assert dhc.attributes["LOCA_NATE"].tolist() == [100.0, 200.0]
    assert dhc.attributes.attrs["attribute_descriptions"]["LOCA_NATE"].unit == "cm"
    assert dhc.properties["final"].tolist() == pytest.approx([0.03, 0.01])
    assert dhc.properties["target"].equals(dhc.properties["final"])
    assert dhc.properties["current"].equals(dhc.properties["final"])

    scpt, scpp, geol = dhc.collections
    assert [scpt.unit, scpp.unit, geol.unit] == ["cm", "mm", "mm"]
    assert scpt.table["distance"].tolist() == [0, 1, 2, 0, 1]
    assert scpt.table["SCPT_RES"].iloc[1] == 0.020  # Pressure readings are not scaled.
    assert scpp.table["from"].tolist() == [0, 1]
    assert scpp.table["to"].tolist() == pytest.approx([10, 20])
    assert geol.table["from"].tolist() == [0, 1.5]
    assert geol.table["to"].tolist() == pytest.approx([15, 30])
    assert dhc.path["distance"].tolist() == pytest.approx([0, 0.01, 0.02, 0, 0.01])
    assert dhc.path["dip"].tolist() == [90, 45, 90, 90, 90]
    assert dhc.path["azimuth"].tolist() == [0, 135, 0, 0, 0]


def test_centimetre_collars_and_metre_readings_keep_their_units(
    evo_metadata: EvoWorkspaceMetadata, valid_ags_1b_path: str, tmp_path: Path
) -> None:
    cm = with_units(valid_ags_1b_path, tmp_path / "cm.ags", LOCA_NATE="cm", LOCA_NATN="cm", LOCA_GL="cm")
    cm.write_text(cm.read_text().replace('"575784.00","5807006.00","OSGB",""', '"569311","5784327","","-478"'))
    (dhc,) = asyncio.run(convert_ags([str(cm)], evo_workspace_metadata=evo_metadata, publish_objects=False))
    assert isinstance(dhc, DownholeCollectionData)
    assert dhc.distance_unit == "cm"
    assert dhc.properties[["x", "y", "z"]].to_numpy().tolist() == [[569311, 5784327, -478]]
    assert dhc.properties[["final", "target", "current"]].to_numpy().tolist() == [[12, 12, 12]]
    assert dhc.path["distance"].tolist() == pytest.approx([0, 2, 4, 6, 8, 10, 12])
    assert dhc.compute_bounding_box().min_z == pytest.approx(-490)
    (scpt,) = dhc.collections
    assert scpt.unit == "m"
    assert scpt.table["distance"].tolist() == [0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12]


@pytest.mark.parametrize(("group", "column"), [("LOCA", "LOCA_NATE"), ("SCPT", "SCPT_DPTH")])
def test_merge_rejects_different_source_units_even_if_convertible(
    evo_metadata: EvoWorkspaceMetadata,
    valid_ags_1a_path: str,
    valid_ags_1b_path: str,
    tmp_path: Path,
    group: str,
    column: str,
) -> None:
    cm = with_units(valid_ags_1b_path, tmp_path / "cm.ags", **{column: "cm"})
    inputs = [valid_ags_1a_path, str(cm)]
    issues: list[AgsDiagnostic] = []
    (first,) = asyncio.run(
        convert_ags(inputs, evo_workspace_metadata=evo_metadata, publish_objects=False, diagnostics=issues)
    )
    assert isinstance(first, DownholeCollectionData)
    assert first.properties["hole_id"].tolist() == ["EXAMPLE-1-CPT1"]
    (issue,) = issues
    assert (issue.code, issue.severity, issue.group, issue.sources) == (
        "incompatible_merge",
        "error",
        group,
        (AgsSource(1, cm.name),),
    )
    assert column in issue.reason and "'m'" in issue.reason and "'cm'" in issue.reason

    separate = asyncio.run(
        convert_ags(inputs, evo_workspace_metadata=evo_metadata, publish_objects=False, merge_files=False)
    )
    assert [obj.name for obj in separate] == ["valid_ags_1a", "cm"]


def test_matching_source_units_can_merge_without_a_conversion_factor(
    evo_metadata: EvoWorkspaceMetadata, valid_ags_1a_path: str, valid_ags_1b_path: str, tmp_path: Path
) -> None:
    unit = "ft[Br65]"
    inputs = []
    for source in (valid_ags_1a_path, valid_ags_1b_path):
        path = with_units(source, tmp_path / Path(source).name, LOCA_NATE=unit, LOCA_NATN=unit, SCPT_DPTH=unit)
        path.write_text(path.read_text().replace('"OSGB"', '""'))
        inputs.append(str(path))

    (dhc,) = asyncio.run(convert_ags(inputs, evo_workspace_metadata=evo_metadata, publish_objects=False))
    assert isinstance(dhc, DownholeCollectionData)
    assert dhc.distance_unit == dhc.collections[0].unit == unit
    assert dhc.properties["hole_id"].tolist() == ["EXAMPLE-1-CPT1", "EXAMPLE-1-CPT2"]
    assert dhc.properties["final"].tolist() == [0.12, 0.12]
    assert dhc.path["distance"].tolist() == dhc.collections[0].table["distance"].tolist()

    mixed = with_units(inputs[0], tmp_path / "mixed.ags", SCPT_DPTH="m")
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(convert_ags([str(mixed)], evo_workspace_metadata=evo_metadata, publish_objects=False))
    (issue,) = error.value.diagnostics
    assert (issue.code, issue.group, issue.sources) == ("invalid_coordinates", "SCPT", (AgsSource(0, mixed.name),))
    assert "SCPT_DPTH" in issue.reason and unit in issue.reason


@pytest.mark.parametrize(
    ("group", "column", "unit"), [("LOCA", "LOCA_NATE", "dega"), ("SCPT", "SCPT_DPTH", ""), ("GEOL", "GEOL_BASE", "s")]
)
def test_unusable_linear_unit_rejects_only_its_source(
    evo_metadata: EvoWorkspaceMetadata,
    multiple_pushes_ags_path: str,
    tmp_path: Path,
    group: str,
    column: str,
    unit: str,
) -> None:
    bad = with_units(multiple_pushes_ags_path, tmp_path / "bad.ags", **{column: unit})
    issues: list[AgsDiagnostic] = []
    (dhc,) = asyncio.run(
        convert_ags(
            [str(bad), multiple_pushes_ags_path],
            evo_workspace_metadata=evo_metadata,
            publish_objects=False,
            diagnostics=issues,
        )
    )
    assert dhc.name == "multiple_pushes"
    (issue,) = issues
    assert (issue.code, issue.severity, issue.group) == ("invalid_coordinates", "error", group)
    assert issue.sources == (AgsSource(0, bad.name),)
    assert column in issue.reason
    assert (repr(unit) if unit else "no unit") in issue.reason


def test_dms_is_an_attribute_and_positions_holes_under_a_geographic_crs(
    evo_metadata: EvoWorkspaceMetadata, valid_ags_1a_path: str, tmp_path: Path
) -> None:
    path = tmp_path / "angular.ags"
    text = (
        Path(valid_ags_1a_path)
        .read_text()
        .replace(
            '"50.49","2025-06-17","","","","","","",""', '"50.49","2025-06-17","","","","","51:30:00N","0:15:00W",""'
        )
    )
    path.write_text(text)
    (dhc,) = asyncio.run(convert_ags([str(path)], evo_workspace_metadata=evo_metadata, publish_objects=False))
    assert isinstance(dhc, DownholeCollectionData)
    assert dhc.attributes is not None
    assert dhc.attributes[["LOCA_LON", "LOCA_LAT"]].to_numpy().tolist() == [[-0.25, 51.5]]
    assert dhc.attributes.attrs["attribute_descriptions"]["LOCA_LON"].unit == "dega"

    # Under a geographic CRS, longitude and latitude stay in degrees; only the depths share one linear unit.
    geographic = with_units(str(path), tmp_path / "geographic.ags", SCPT_DPTH="cm")
    set_loca_reference(geographic, "LOCA_LLZ", "WGS84")
    (dhc,) = asyncio.run(convert_ags([str(geographic)], evo_workspace_metadata=evo_metadata, publish_objects=False))
    assert isinstance(dhc, DownholeCollectionData)
    assert dhc.coordinate_reference_system == 4326
    assert dhc.distance_unit == "cm"
    assert dhc.properties[["x", "y"]].to_numpy().tolist() == [[-0.25, 51.5]]
    assert dhc.collections[0].unit == "cm"
    assert dhc.path["distance"].max() == pytest.approx(dhc.properties["final"].iloc[0])

    path.write_text(text)
    set_loca_reference(path, "LOCA_LLZ", "WGS84")
    conflict = with_units(str(path), tmp_path / "conflict.ags", LOCA_LAT="cm")
    with pytest.raises(AgsParsingError) as error:
        asyncio.run(convert_ags([str(conflict)], evo_workspace_metadata=evo_metadata, publish_objects=False))
    (issue,) = error.value.diagnostics
    assert (issue.code, issue.group, issue.sources) == ("invalid_coordinates", "LOCA", (AgsSource(0, conflict.name),))
    assert "LOCA_LAT" in issue.reason and "'cm'" in issue.reason
