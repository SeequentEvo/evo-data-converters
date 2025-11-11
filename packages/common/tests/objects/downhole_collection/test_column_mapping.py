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

from evo.data_converters.common.objects.downhole_collection.column_mapping import ColumnMapping


class TestColumnMapping:
    """Tests for ColumnMapping dataclass"""

    def test_default_initialization(self):
        """Test that ColumnMapping initializes with correct default values"""
        mapping = ColumnMapping()

        assert mapping.HOLE_INDEX_COLUMNS == ["hole_index"]
        assert mapping.DEPTH_COLUMNS == []
        assert mapping.FROM_COLUMNS == []
        assert mapping.TO_COLUMNS == []

    def test_custom_initialization(self):
        """Test that custom column mappings can be provided"""
        custom_mapping = ColumnMapping(
            HOLE_INDEX_COLUMNS=["custom_hole_id"],
            DEPTH_COLUMNS=["custom_depth"],
            FROM_COLUMNS=["custom_from"],
            TO_COLUMNS=["custom_to"],
        )

        assert custom_mapping.HOLE_INDEX_COLUMNS == ["custom_hole_id"]
        assert custom_mapping.DEPTH_COLUMNS == ["custom_depth"]
        assert custom_mapping.FROM_COLUMNS == ["custom_from"]
        assert custom_mapping.TO_COLUMNS == ["custom_to"]

    def test_partial_custom_initialization(self):
        """Test that only some fields can be customized while others use defaults"""
        mapping = ColumnMapping(DEPTH_COLUMNS=["my_depth"])

        assert mapping.HOLE_INDEX_COLUMNS == ["hole_index"]
        assert mapping.DEPTH_COLUMNS == ["my_depth"]
        assert mapping.FROM_COLUMNS == []
        assert mapping.TO_COLUMNS == []

    def test_multiple_instances_independent(self):
        """Test that multiple instances don't share list references"""
        mapping1 = ColumnMapping()
        mapping2 = ColumnMapping()

        # Modify one instance
        mapping1.DEPTH_COLUMNS.append("new_depth")

        # Verify the other instance is unaffected
        assert "new_depth" in mapping1.DEPTH_COLUMNS
        assert "new_depth" not in mapping2.DEPTH_COLUMNS

    def test_mutability(self):
        """Test that ColumnMapping fields can be modified after creation"""
        mapping = ColumnMapping()

        mapping.HOLE_INDEX_COLUMNS = ["new_hole_index"]
        assert mapping.HOLE_INDEX_COLUMNS == ["new_hole_index"]

        mapping.DEPTH_COLUMNS.append("additional_depth")
        assert "additional_depth" in mapping.DEPTH_COLUMNS

    def test_empty_lists_allowed(self):
        """Test that empty lists can be provided"""
        mapping = ColumnMapping(HOLE_INDEX_COLUMNS=[], DEPTH_COLUMNS=[], FROM_COLUMNS=[], TO_COLUMNS=[])

        assert mapping.HOLE_INDEX_COLUMNS == []
        assert mapping.DEPTH_COLUMNS == []
        assert mapping.FROM_COLUMNS == []
        assert mapping.TO_COLUMNS == []

    def test_multiple_column_names_in_lists(self):
        """Test that multiple alternative column names can be specified"""
        mapping = ColumnMapping(DEPTH_COLUMNS=["depth", "depth_m", "depth_ft", "penetration"])

        assert len(mapping.DEPTH_COLUMNS) == 4
        assert "depth" in mapping.DEPTH_COLUMNS
        assert "penetration" in mapping.DEPTH_COLUMNS
