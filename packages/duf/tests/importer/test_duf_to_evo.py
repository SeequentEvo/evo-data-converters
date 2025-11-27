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

import os
import re

import numpy
import pytest
from evo_schemas.objects import LineSegments_V2_1_0, TriangleMesh_V2_1_0

from evo.data_converters.duf.importer import convert_duf


def test_should_log_warnings(evo_metadata, simple_objects_path, caplog: pytest.LogCaptureFixture) -> None:
    convert_duf(filepath=simple_objects_path, evo_workspace_metadata=evo_metadata, epsg_code=32650)

    expected_log_message = r"Unsupported DUF object type: Circle, ignoring 1 object."
    assert any(re.search(expected_log_message, line) for line in caplog.messages)


def test_should_add_expected_tags(evo_metadata, simple_objects_path) -> None:
    tags = {"First tag": "first tag value", "Second tag": "second tag value"}

    go_objects = convert_duf(
        filepath=simple_objects_path, evo_workspace_metadata=evo_metadata, epsg_code=32650, tags=tags
    )

    expected_tags = {
        "Source": f"{os.path.basename(simple_objects_path)} (via Evo Data Converters)",
        "InputType": "DUF",
        "Category": "ModelEntities",
        **tags,
    }
    assert go_objects[0].tags == expected_tags


def test_should_convert_expected_geometry_types(evo_metadata, simple_objects_path) -> None:
    go_objects = convert_duf(filepath=simple_objects_path, evo_workspace_metadata=evo_metadata, epsg_code=32650)

    expected_go_object_types = [LineSegments_V2_1_0, TriangleMesh_V2_1_0]
    assert [type(obj) for obj in go_objects] == expected_go_object_types


def test_import_category_with_missing_attrs(
    evo_metadata, data_client, polyline_empty_category_and_nan_attrs_path
) -> None:
    go_objects = convert_duf(
        filepath=polyline_empty_category_and_nan_attrs_path,
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        combine_objects_in_layers=True,
    )
    imported_line_segments = go_objects[0]
    category_go = next(attr for attr in imported_line_segments.parts.attributes if attr.attribute_type == "category")
    table = data_client.load_table(category_go.table)
    categories = table["value"].to_numpy()

    # The test DUF file has a category attribute with an empty string as a category. All we really care about is testing
    # that the empty string has been removed from categories on import.
    assert "" not in categories
    assert len(categories) > 0


def test_import_object_with_missing_attrs(evo_metadata, data_client, missing_attr_and_missing_xprops_path) -> None:
    go_objects = convert_duf(
        filepath=missing_attr_and_missing_xprops_path,
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        combine_objects_in_layers=True,
    )
    imported_line_segments = go_objects[0]

    attr1_go, attr2_go = imported_line_segments.parts.attributes

    def check_attr_values(attr_go):
        attr = data_client.load_table(attr1_go.values)
        attr_values = attr.column(0).to_numpy()

        # All of the missing values should have been imported as NaN
        assert 0 in attr_go.nan_description.values
        assert numpy.array_equal(attr_values, [0, 0])

    check_attr_values(attr1_go)
    check_attr_values(attr2_go)


def test_combined_import_with_different_entity_types_in_layer(
    evo_metadata, data_client, layer_with_2polylines_2meshes_2points_2texts_1face_path
) -> None:
    """
    The polylines and points should get combined into one object. The meshes should get combined into another. The text and face objects should be ignored.
    """
    go_objects = convert_duf(
        filepath=layer_with_2polylines_2meshes_2points_2texts_1face_path,
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        combine_objects_in_layers=True,
    )

    assert len(go_objects) == 2

    go_objects.sort(key=str)
    line_segments, mesh_triangles = go_objects

    assert "line-segments" in line_segments.schema
    assert line_segments.parts.attributes[0].values.length == 4  # polylines + points
    assert "triangle-mesh" in mesh_triangles.schema
    assert mesh_triangles.parts.attributes[0].values.length == 2


def test_import_attribute_named_id(evo_metadata, data_client, id_attribute_path) -> None:
    go_objects = convert_duf(
        filepath=id_attribute_path,
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
    )

    assert len(go_objects) == 2
    line_segments, mesh_triangles = sorted(go_objects, key=str)

    assert (line_segments_attr := line_segments.parts.attributes[0]).name == "external_id"
    assert numpy.array_equal(["id polyline 1"], data_client.load_category(line_segments_attr))

    assert (mesh_tri_attr := mesh_triangles.parts.attributes[0]).name == "external_id"
    assert numpy.array_equal(["id polyface 1"], data_client.load_category(mesh_tri_attr))


def test_int_column_with_missing_values_gets_published_as_double(evo_metadata, data_client, missing_ints_path) -> None:
    go_objects = convert_duf(
        filepath=missing_ints_path,
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        combine_objects_in_layers=True,
    )

    # The Deswik entities are named "MISSING INTS" and "NO_MISSING_INTS"
    go_objects.sort(key=lambda go: go.name)
    missing_ints_go, no_missing_ints_go = go_objects

    missing_ints_attr = missing_ints_go.parts.attributes[0]
    # The layer that has entities with missing ints has been converted to double
    assert missing_ints_attr.attribute_type == "scalar"  # double
    [missing_ints_column] = data_client.load_columns(missing_ints_attr.values)
    assert numpy.isnan(missing_ints_column[0])
    assert not numpy.isnan(missing_ints_column[1])

    no_missing_ints_go = no_missing_ints_go.parts.attributes[0]
    assert no_missing_ints_go.attribute_type == "integer"
    [no_missing_ints_column] = data_client.load_columns(no_missing_ints_go.values)
    assert not numpy.isnan(no_missing_ints_column).any()


def test_mismatch_of_attribute_type_spec_and_value(
    evo_metadata, data_client, mismatching_type_desc_and_values_path
) -> None:
    go_objects = convert_duf(
        filepath=mismatching_type_desc_and_values_path,
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        combine_objects_in_layers=True,
    )

    assert len(go_objects) == 1
    mesh_go = go_objects[0]

    def check_attr_values(attr_go):
        table = data_client.load_table(attr_go.values).to_pandas()
        column = table[table.columns[0]].to_numpy()
        assert numpy.isnan(column).all()

    check_attr_values(mesh_go.parts.attributes[0])
    check_attr_values(mesh_go.parts.attributes[1])
