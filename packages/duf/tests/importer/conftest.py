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

from pathlib import Path

import pytest

from evo.data_converters.duf import DUFCollectorContext


@pytest.fixture(scope="session")
def simple_objects_path():
    return str((Path(__file__).parent.parent / "data" / "simple_objects.duf").resolve())


@pytest.fixture(scope="session")
def simple_objects(simple_objects_path):
    with DUFCollectorContext(simple_objects_path) as context:
        yield context.collector


@pytest.fixture(scope="session")
def simple_objects_with_attrs_path():
    return str((Path(__file__).parent.parent / "data" / "simple_objects_with_attributes.duf").resolve())


@pytest.fixture(scope="session")
def simple_objects_with_attrs(simple_objects_with_attrs_path):
    with DUFCollectorContext(simple_objects_with_attrs_path) as context:
        yield context.collector


@pytest.fixture(scope="session")
def multiple_objects_path():
    return str((Path(__file__).parent.parent / "data" / "multiple_objects.duf").resolve())


@pytest.fixture(scope="session")
def multiple_objects(multiple_objects_path):
    with DUFCollectorContext(multiple_objects_path) as context:
        yield context.collector


@pytest.fixture(scope="session")
def polyline_attrs_boat_path():
    return str((Path(__file__).parent.parent / "data" / "polyline_attrs_boat.duf").resolve())


@pytest.fixture(scope="session")
def polyline_attrs_boat(polyline_attrs_boat_path):
    with DUFCollectorContext(polyline_attrs_boat_path) as context:
        yield context.collector


@pytest.fixture(scope="session")
def pit_mesh_attrs_path():
    return str((Path(__file__).parent.parent / "data" / "pit_mesh_attrs.duf").resolve())


@pytest.fixture(scope="session")
def pit_mesh_attrs(pit_mesh_attrs_path):
    with DUFCollectorContext(pit_mesh_attrs_path) as context:
        yield context.collector


@pytest.fixture(scope="session")
def polyline_empty_category_and_nan_attrs_path():
    return str((Path(__file__).parent.parent / "data" / "polyline_empty_category_and_nan_attr.duf").resolve())


@pytest.fixture(scope="session")
def polyline_empty_category_and_nan_attrs(polyline_empty_category_and_nan_attrs_path):
    with DUFCollectorContext(polyline_empty_category_and_nan_attrs_path) as context:
        yield context.collector


@pytest.fixture(scope="session")
def missing_attr_and_missing_xprops_path():
    return str((Path(__file__).parent.parent / "data" / "missing_attr_and_missing_xprops.duf").resolve())


@pytest.fixture(scope="session")
def missing_attr_and_missing_xprops(missing_attr_and_missing_xprops_path):
    with DUFCollectorContext(missing_attr_and_missing_xprops_path) as context:
        yield context.collector
