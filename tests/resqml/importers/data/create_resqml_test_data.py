#!/usr/bin/env python

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

# Create resqml files used by tests
from os import path

import numpy as np
import resqpy.model as rqm
import resqpy.surface as rqs


def _set_model_author(model: rqm.Model, author: str) -> None:
    # resqpy seems to lack a way to specify the originator on some parts of the model
    # so the name of the user gets embedded in the .epc file. This updates those references
    # to the desired author.
    namespaces = {
        "eml": "http://www.energistics.org/energyml/data/commonv2",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    for forest in (model.parts_forest, model.rels_forest, model.other_forest):
        for part_name in forest:
            xml_node = forest[part_name][-1]
            originator_nodes = xml_node.xpath("//eml:Originator|dc:creator", namespaces=namespaces)
            for node in originator_nodes:
                node.text = author


def _create_test_surface(author: str) -> rqm.Model:
    model_file = path.join(path.dirname(__file__), "surface.epc")
    model = rqm.new_model(model_file)

    surface = rqs.Surface(model, crs_uuid=model.crs_uuid, originator=author)
    surface.set_to_horizontal_plane(depth=50.00, box_xyz=np.array([[100.00, 100.00, 0.0], [100.00, 100.00, 0.0]]))
    surface.write_hdf5()
    surface.create_xml(title="surface", originator=author)

    _set_model_author(model, author)

    model.store_epc()


def _create_resqml_test_data() -> None:
    author = "seequent"
    _create_test_surface(author)


if __name__ == "__main__":
    _create_resqml_test_data()
