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
from typing import Optional
from uuid import UUID

import numpy as np
from evo_schemas.objects import Pointset_V1_1_0, Pointset_V1_2_0
from omf import PointSetElement, PointSetGeometry

from evo.objects.utils.data import ObjectDataClient

from .evo_attributes_to_omf import export_omf_attributes


def export_omf_pointset(
    object_id: UUID,
    version_id: Optional[str],
    pointset_go: Pointset_V1_1_0 | Pointset_V1_2_0,
    data_client: ObjectDataClient,
) -> PointSetElement:
    vertices_table = asyncio.run(
        data_client.download_table(object_id, version_id, pointset_go.locations.coordinates.as_dict())
    )
    vertices = np.asarray(vertices_table)
    vertex_attribute_data = export_omf_attributes(
        object_id, version_id, pointset_go.locations.attributes, "vertices", data_client
    )

    element_description = pointset_go.description if pointset_go.description else ""
    return PointSetElement(
        name=pointset_go.name,
        description=element_description,
        geometry=PointSetGeometry(vertices=vertices),
        data=vertex_attribute_data,
    )
