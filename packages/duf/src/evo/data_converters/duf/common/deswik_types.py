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

# ruff: noqa: E402

# This links the C# libraries and sets up the Python runtime to import Deswik's C# libraries
from evo.data_converters.duf.common import setup_deswik_lib_bindings  # noqa: F401

from Deswik.Core.Structures import Vector3_dp, Vector4_dp
from Deswik.Duf import (
    EntityMetadata,
    CompressionMethod,
    DufImplementation,
    FilterCriteria,
    ItemHeader,
    NotDufFileException,
    PerformanceTweaking,
    SaveByIndexSet,
    SaveEntityItem,
    SaveSet,
    SaveByEnumerableSet,
)
from Deswik.Entities import BaseEntity, PropValue, XProperty, XProperties
from Deswik.Entities.Base import DufList, SerializationBehaviour
from Deswik.Entities.Cad import (
    Activator,
    Category,
    Document,
    Figure,
    Layer,
    Polyface,
    Polyline,
    Upgrader,
    dwPolyline,
    LineType,
    Color,
    dwPoint,
)
from Deswik.Serialization import GuidReferences
from System import ArgumentException, Boolean, Double, Guid, Int32, NullReferenceException, String, UInt32
from System.Collections.Generic import List
from System.Reflection import BindingFlags


__all__ = [
    # Deswik
    "Activator",
    "BaseEntity",
    "BindingFlags",
    "Category",
    "Color",
    "CompressionMethod",
    "Document",
    "Double",
    "DufList",
    "DufImplementation",
    "dwPoint",
    "dwPolyline",
    "EntityMetadata",
    "Figure",
    "FilterCriteria",
    "GuidReferences",
    "ItemHeader",
    "Layer",
    "LineType",
    "NotDufFileException",
    "PerformanceTweaking",
    "Polyface",
    "Polyline",
    "PropValue",
    "SaveByEnumerableSet",
    "SaveEntityItem",
    "SaveByIndexSet",
    "SaveSet",
    "SerializationBehaviour",
    "Upgrader",
    "Vector3_dp",
    "Vector4_dp",
    "XProperty",
    "XProperties",
    # System
    "ArgumentException",
    "Boolean",
    "Guid",
    "NullReferenceException",
    "Int32",
    "String",
    "UInt32",
    "List",
]
