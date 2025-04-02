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
from unittest import TestCase

from evo.data_converters.common.publish import generate_paths


@dataclass
class GeoscienceObjectMock:
    name: str


class TestGeneratePaths(TestCase):
    def setUp(self) -> None:
        go_names = ["mypoints", "mylines", "mysurface", "mypoints2", "mylines"]
        self.go_objects = [GeoscienceObjectMock(name=name) for name in go_names]

    def test_paths_are_generated(self) -> None:
        paths = generate_paths(self.go_objects)
        expected_paths = [
            "mypoints.json",
            "mylines_1.json",
            "mysurface.json",
            "mypoints2.json",
            "mylines_2.json",
        ]

        self.assertEqual(expected_paths, paths)

    def test_paths_are_generated_with_prefix(self) -> None:
        paths = generate_paths(self.go_objects, "region_a/sites/mine_b")
        expected_paths = [
            "region_a/sites/mine_b/mypoints.json",
            "region_a/sites/mine_b/mylines_1.json",
            "region_a/sites/mine_b/mysurface.json",
            "region_a/sites/mine_b/mypoints2.json",
            "region_a/sites/mine_b/mylines_2.json",
        ]

        self.assertEqual(expected_paths, paths)

    def test_paths_are_generated_with_correct_slashes(self) -> None:
        paths = generate_paths(self.go_objects, "/leading-slash")
        expected_paths = [
            "leading-slash/mypoints.json",
            "leading-slash/mylines_1.json",
            "leading-slash/mysurface.json",
            "leading-slash/mypoints2.json",
            "leading-slash/mylines_2.json",
        ]

        self.assertEqual(expected_paths, paths)

        paths = generate_paths(self.go_objects, "trailing-slash/")
        expected_paths = [
            "trailing-slash/mypoints.json",
            "trailing-slash/mylines_1.json",
            "trailing-slash/mysurface.json",
            "trailing-slash/mypoints2.json",
            "trailing-slash/mylines_2.json",
        ]

        self.assertEqual(expected_paths, paths)
