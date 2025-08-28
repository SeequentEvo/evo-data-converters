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
from collections import defaultdict

import evo.data_converters.duf.common.deswik_types as dw
import evo.logging

logger = evo.logging.getLogger("data_converters")


class InvalidDUFFileException(ValueError):
    def __init__(self, message):
        super().__init__(message)


class DUFFileNotFoundException(FileNotFoundError):
    def __init__(self, message):
        super().__init__(message)


class ObjectCollector:
    def __init__(self, verbose=False):
        self._objs: dict[dw.Category, dict[type, dw.BaseEntity]] = defaultdict(lambda: defaultdict(list))
        self._layers_by_guid: dict[dw.Guid, dw.Layer] = {}
        self._verbose = verbose

    def Loaded(self, category, item):
        if category == dw.Category.Layers:
            if not isinstance(item, dw.Layer):
                raise TypeError(f"Expected Layer, got {type(item).__name__}")
            self._layers_by_guid[item.Guid] = item
        elif hasattr(item, "Layer"):
            # Sometimes the loaded layer on the object is not the same as the one in the layer collection, fix this
            if item.Layer is not None and item.Layer is not self._layers_by_guid[item.Layer.Guid]:
                item.Layer = self._layers_by_guid[item.Layer.Guid]

        self._objs[category][type(item)].append(item)
        if self._verbose:
            logger.info(
                f"Loaded from category {category} entity of type {item.GetType().FullName} with guid {item.Guid}."
            )

    def get_objects_with_category(self, category: dw.Category) -> list[dw.BaseEntity]:
        return [obj for cat_objs in self._objs[category].values() for obj in cat_objs]

    def get_objects_with_category_by_type(self, category: dw.Category):
        return {klass: [obj for obj in objs] for klass, objs in self._objs[category].items()}

    def get_objects_with_category_by_layer(self, category: dw.Category):
        by_layer = defaultdict(list)
        for objs in self._objs[category].values():
            for obj in objs:
                layer = getattr(obj, "Layer", None)
                if layer is not None:
                    real_layer = self._layers_by_guid.get(layer.Guid, layer)
                    by_layer[real_layer].append(obj)
                else:
                    by_layer[None].append(obj)
        return by_layer

    def get_objects_of_type(self, object_type: type) -> list[tuple[dw.Category, dw.BaseEntity]]:
        return [
            (cat, obj)
            for cat, cat_objs in self._objs.items()
            for klass, objs in cat_objs.items()
            for obj in objs
            if issubclass(klass, object_type)
        ]

    def get_all_objects_by_type(self):
        return {
            klass: [(cat, obj) for obj in objs]
            for cat, cat_objs in self._objs.items()
            for klass, objs in cat_objs.items()
        }

    def get_all_objects(self) -> list[dw.BaseEntity]:
        return [obj for cat_objs in self._objs.values() for obj in cat_objs.values()]


class DUFWrapper:
    nameofImperialOption = "_dw_Options_Imperial"
    nameOfZeroLayer = "0"
    nameOfSettingsLayer = "_dw_Settings_Layer"
    nameOfSettingsLayerDefault = "_DW_SETTINGS"
    DufCompressionMethod = dw.CompressionMethod.Snappy

    def __init__(self, path: str, collector: ObjectCollector | None = None):
        if not os.path.exists(path):
            raise DUFFileNotFoundException(f"DUF file not found: {path}")

        self._collector = collector or ObjectCollector()
        try:
            self._duf = dw.DufImplementation[dw.Category](path, dw.Activator(), dw.Upgrader())
        except (dw.NotDufFileException, dw.NullReferenceException):
            raise InvalidDUFFileException(f"Invalid DUF file: {path}")

        self._document = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.Dispose()
        self._collector = None
        self._duf = None

    def Dispose(self):
        if self._duf:
            self._duf.Dispose()

    def LoadDocumentAndReferenceDataOnly(self):
        dufGuidReferences = dw.GuidReferences()
        self.LoadDocInternal(dufGuidReferences)
        return dufGuidReferences

    def LoadEverything(self):
        dufGuidReferences = dw.GuidReferences()
        self.LoadDocInternal(dufGuidReferences)
        self.LoadEntitiesInternal(None, dufGuidReferences)
        _, self._document = self._collector.get_objects_of_type(dw.Document)[0]

    def LoadSingleEntity(self, entityId, guidReferences):
        return self._duf.LoadSingleEntityFromLatest(entityId, guidReferences, False, None)

    def LoadEntitiesInternal(self, layerGuid, dufGuidReferences):
        parents = None
        if layerGuid is not None:
            parents = dw.List[dw.Guid]()
            parents.Add(layerGuid)

        Categories = dw.List[dw.Category]()
        Categories.Add(dw.Category.ModelEntities)
        Crit = dw.FilterCriteria[dw.Category]()
        Crit.Categories = Categories
        Crit.ParentIds = parents
        for entity in self._duf.LoadFromLatest(dufGuidReferences, Crit, False, True, None):
            self._collector.Loaded(dw.Category.ModelEntities, entity)

    def LoadLayerEntities(self, layerGuid, guidReferences):
        self.LoadEntitiesInternal(layerGuid, guidReferences)

    def LoadDocInternal(self, dufGuidReferences):
        self.LoadTopLevelEntitiesOfType(
            dw.Category.Document,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.Document, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.Layers,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.Layers, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.LineTypes,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.LineTypes, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.Images,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.Images, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.TextStyles,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.TextStyles, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.DimStyles,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.DimStyles, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.Blocks,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.Blocks, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.HatchPatterns,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.HatchPatterns, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.Lights,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.Lights, item),
        )
        self.LoadTopLevelEntitiesOfType(
            dw.Category.Palette,
            dufGuidReferences,
            lambda item: self._collector.Loaded(dw.Category.Lights, item),
        )

    def LoadTopLevelEntitiesOfType(self, category, dufGuidReferences, callback):
        Categories = dw.List[dw.Category]()
        Categories.Add(category)
        Crit = dw.FilterCriteria[dw.Category]()
        Crit.Categories = Categories
        for entity in self._duf.LoadFromLatest(dufGuidReferences, Crit, False, True, None):
            callback(entity)

    def XPropertyExists(self, xprops, name):
        for xprop in xprops:
            if xprop.Key == name:
                return True
        return False

    def XPropertyGet(self, xprops, name):
        for xprop in xprops:
            if xprop.Key == name:
                return xprop
        return None

    def LoadSettings(self):
        Categories = dw.List[dw.Category]()
        Categories.Add(dw.Category.Layers)
        Crit = dw.FilterCriteria[dw.Category]()
        Crit.Categories = Categories
        layers = list(self._duf.LoadFromLatest(None, Crit, False, True, None))
        zeroLayer = next(layer for layer in layers if layer.Name == self.nameOfZeroLayer)
        settingsLayerName = self.nameOfZeroLayer

        if self.XPropertyExists(zeroLayer.XProperties, self.nameOfSettingsLayer):
            xprop = self.XPropertyGet(zeroLayer.XProperties, self.nameOfSettingsLayer)
            settingsLayerName = xprop.Value.Value[0].Value or self.nameOfSettingsLayerDefault

        settingsLayer = next((layer for layer in layers if layer.Name == settingsLayerName), None)

        if settingsLayer is None:
            settingsLayer = zeroLayer

        return settingsLayer.XProperties
