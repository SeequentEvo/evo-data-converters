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

import pytest
import polars as pl
from pathlib import Path
from pygef.cpt import CPTData
from evo.data_converters.gef.converter.parse_gef_files import parse_gef_files


class TestParseGefFiles:
    """Test the parse_gef_files function behaves as intended."""

    test_data_dir = Path(__file__).parent / "data"

    def test_parse_valid_cpt_gef_file(self) -> None:
        cpt_file = self.test_data_dir / "gef-cpt/cpt.gef"
        result = parse_gef_files([cpt_file])
        assert isinstance(result, dict)
        assert len(result) == 1
        for v in result.values():
            assert isinstance(v, CPTData)

    def test_parse_multiple_valid_cpt_files(self) -> None:
        files = [
            self.test_data_dir / "gef-cpt/cpt.gef",
            self.test_data_dir / "gef-cpt/cpt2.gef",
            self.test_data_dir / "gef-xml/cpt.xml",
        ]
        result = parse_gef_files(files)
        assert isinstance(result, dict)

        assert len(result) == 3
        for v in result.values():
            assert isinstance(v, CPTData)

    def test_parse_valid_cpt_xml_file(self) -> None:
        cpt_file = self.test_data_dir / "gef-xml/cpt.xml"
        result = parse_gef_files([cpt_file])
        assert isinstance(result, dict)
        assert len(result) == 1
        for v in result.values():
            assert isinstance(v, CPTData)

    def test_parse_cpt_xml_with_multiple_entries(self) -> None:
        cpt_file = self.test_data_dir / "gef-xml/cpt_multiple.xml"
        result = parse_gef_files([cpt_file])
        assert isinstance(result, dict)
        assert len(result) == 2  # Expecting 2 CPT entries in the XML
        for v in result.values():
            assert isinstance(v, CPTData)

    def test_file_not_found(self) -> None:
        missing_file = "/does_not_exist.gef"
        with pytest.raises(FileNotFoundError) as exc:
            parse_gef_files([missing_file])
        assert "File not found" in str(exc.value)

    def test_not_cpt_type(self) -> None:
        bore_file = self.test_data_dir / "gef-bore/bore.gef"
        with pytest.raises(ValueError) as exc:
            parse_gef_files([bore_file])
        assert "gef file is not a cpt" in str(exc.value)

    def test_unrecognized_type(self) -> None:
        bore_file = self.test_data_dir / "../../README.md"
        with pytest.raises(ValueError) as exc:
            parse_gef_files([bore_file])
        assert "has extension '.md', expected .xml or .gef" in str(exc.value)

    def test_overlapping_hole_ids(self):
        """Test that parse_gef_files raises an error for duplicate hole_ids (from test_id or filename)."""
        file1 = self.test_data_dir / "gef-cpt/cpt.gef"
        file2 = self.test_data_dir / "gef-cpt/cpt_duplicate_test_id.gef"

        with pytest.raises(ValueError) as exc:
            parse_gef_files([file1, file2])
        assert "Duplicate ID" in str(exc.value)

    def test_parse_cpt_gef_files_with_replace_column_voids_enabled(self) -> None:
        cpt_file = self.test_data_dir / "gef-cpt/cpt_voids.gef"
        result = parse_gef_files([cpt_file], replace_column_voids=True)
        cpt_data = next(iter(result.values()))
        assert cpt_data.data.shape == (4, 4)

        df = pl.DataFrame(
            {
                "penetrationLength": [0.01, 0.03, 0.05, 0.07],
                "coneResistance": [0.013, 1.253, 2.493, 14.766],
                "correctedConeResistance": [0.013, 0.696, 2.496, 14.808],
                "depthOffset": [-0.10, -0.12, -0.14, -0.16],
            }
        )

        for column in df.columns:
            assert cpt_data.data[column].round(4).equals(df[column].round(4), null_equal=True)

    def test_parse_cpt_gef_files_with_replace_column_voids_disabled(self) -> None:
        cpt_file = self.test_data_dir / "gef-cpt/cpt_voids.gef"
        result = parse_gef_files([cpt_file], replace_column_voids=False)
        cpt_data = next(iter(result.values()))
        assert cpt_data.data.shape == (6, 4)

        df = pl.DataFrame(
            {
                "penetrationLength": [0.00, 0.01, 0.03, 0.05, 0.07, 0.09],
                "coneResistance": [-999999.0, 0.013, -999999.0, 2.493, 14.766, -999999.0],
                "correctedConeResistance": [
                    -999999.0,
                    0.013,
                    0.696,
                    2.496,
                    14.808,
                    -999999.0,
                ],
                "depthOffset": [-0.09, -0.10, -0.12, -0.14, -0.16, -0.18],
            }
        )

        for column in df.columns:
            assert cpt_data.data[column].round(4).equals(df[column].round(4), null_equal=True)
