# ruff: noqa: E402

import os
import platform
from collections import defaultdict

if not platform.system() == "Windows":
    raise RuntimeError("This script is only supported on Windows.")

if not os.path.exists(r"C:\Program Files\Deswik"):
    raise RuntimeError("Deswik.Suite is not installed. Please install Deswik.Suite to run this script.")

installs = [pth for pth in os.listdir(r"C:\Program Files\Deswik") if "Suite" in pth]
if not installs:
    raise RuntimeError("Deswik.Suite is not installed. Please install Deswik.Suite to run this script.")


# Sort by version
def by_version(path):
    version = path.split(" ")[-1]
    year, month = version.split(".")
    return int(year), int(month)


import evo.logging

logger = evo.logging.getLogger("data_converters")

newest = os.path.join(r"C:\Program Files\Deswik", sorted(installs, key=by_version)[-1])
logger.debug("Looking for Deswik DLLs in: %s", newest)

import sys

sys.path.append(newest)

import clr

clr.AddReference("Deswik.Duf")
clr.AddReference("Deswik.Entities")
clr.AddReference("Deswik.Entities.Cad")
clr.AddReference("Deswik.Serialization")

# Some imports below are unused but imported here to ensure the setup code above has run
from Deswik.Duf import CompressionMethod, DufImplementation, FilterCriteria, NotDufFileException
from Deswik.Entities import BaseEntity
from Deswik.Entities.Cad import Activator, Category, Polyface, Polyline, Upgrader  # noqa: F401
from Deswik.Serialization import GuidReferences
from System import Guid, NullReferenceException
from System.Collections.Generic import List


class InvalidDufFileException(ValueError):
    def __init__(self, message):
        super().__init__(message)


class DufFileNotFoundException(FileNotFoundError):
    def __init__(self, message):
        super().__init__(message)


class ObjectCollector:
    def __init__(self, verbose=False):
        self._objs: dict[Category, dict[type, BaseEntity]] = defaultdict(lambda: defaultdict(list))
        self._verbose = verbose

    def Loaded(self, category, item):
        self._objs[category][type(item)].append(item)
        if self._verbose:
            print(f"Loaded from category {category} entity of type {item.GetType().FullName} with guid {item.Guid}.")

    def get_objects_with_category_of_type(self, category: Category, object_type: BaseEntity) -> list[BaseEntity]:
        return self._objs[category][object_type]

    def get_objects_with_category(self, category: Category) -> list[BaseEntity]:
        return [obj for cat_objs in self._objs[category].values() for obj in cat_objs]

    def get_objects_of_type(self, object_type: type) -> list[tuple[Category, BaseEntity]]:
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

    def get_all_objects(self) -> list[BaseEntity]:
        return [obj for cat_objs in self._objs.values() for obj in cat_objs.values()]


class DufWrapper:
    nameofImperialOption = "_dw_Options_Imperial"
    nameOfZeroLayer = "0"
    nameOfSettingsLayer = "_dw_Settings_Layer"
    nameOfSettingsLayerDefault = "_DW_SETTINGS"
    DufCompressionMethod = CompressionMethod.Snappy

    def __init__(self, path: str, collector: ObjectCollector | None):
        if not os.path.exists(path):
            raise DufFileNotFoundException(f"DUF file not found: {path}")

        self._collector = collector or ObjectCollector()
        try:
            self._duf = DufImplementation[Category](path, Activator(), Upgrader())
        except (NotDufFileException, NullReferenceException):
            raise InvalidDufFileException(f"Invalid DUF file: {path}")

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
        dufGuidReferences = GuidReferences()
        self.LoadDocInternal(dufGuidReferences)
        return dufGuidReferences

    def LoadEverything(self):
        dufGuidReferences = GuidReferences()
        self.LoadDocInternal(dufGuidReferences)
        self.LoadEntitiesInternal(None, dufGuidReferences)

    def LoadSingleEntity(self, entityId, guidReferences):
        return self._duf.LoadSingleEntityFromLatest(entityId, guidReferences, False, None)

    def LoadEntitiesInternal(self, layerGuid, dufGuidReferences):
        parents = None
        if layerGuid is not None:
            parents = List[Guid]()
            parents.Add(layerGuid)

        Categories = List[Category]()
        Categories.Add(Category.ModelEntities)
        Crit = FilterCriteria[Category]()
        Crit.Categories = Categories
        Crit.ParentIds = parents
        for entity in self._duf.LoadFromLatest(dufGuidReferences, Crit, False, True, None):
            self._collector.Loaded(Category.ModelEntities, entity)

    def LoadLayerEntities(self, layerGuid, guidReferences):
        self.LoadEntitiesInternal(layerGuid, guidReferences)

    def LoadDocInternal(self, dufGuidReferences):
        self.LoadTopLevelEntitiesOfType(
            Category.Document,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.Document, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.LineTypes,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.LineTypes, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.Images,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.Images, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.Layers,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.Layers, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.TextStyles,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.TextStyles, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.DimStyles,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.DimStyles, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.Blocks,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.Blocks, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.HatchPatterns,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.HatchPatterns, item),
        )
        self.LoadTopLevelEntitiesOfType(
            Category.Lights,
            dufGuidReferences,
            lambda item: self._collector.Loaded(Category.Lights, item),
        )

    def LoadTopLevelEntitiesOfType(self, category, dufGuidReferences, callback):
        Categories = List[Category]()
        Categories.Add(category)
        Crit = FilterCriteria[Category]()
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
        Categories = List[Category]()
        Categories.Add(Category.Layers)
        Crit = FilterCriteria[Category]()
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
