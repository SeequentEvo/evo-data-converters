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
import enum
import json
from dataclasses import dataclass
import re

import numpy
from typing import Optional, Any

from evo.data_converters.common import EvoObjectMetadata
from evo.objects import ObjectAPIClient
from evo.objects.utils import ObjectDataClient
from evo_schemas import (
    json_loads,
    LineSegments_V2_0_0,
    LineSegments_V2_1_0,
    LineSegments_V2_2_0,
    TriangleMesh_V2_1_0,
    TriangleMesh_V2_0_0,
    TriangleMesh_V2_2_0,
)
from evo_schemas.elements.serialiser import GSONEncoder, Serialiser


from evo.data_converters.duf.common.types import FetchedTriangleMesh, FetchedLines
from evo.data_converters.duf.common.attributes import EvoAttributes


class FetchStatus(enum.Enum):
    not_begun = enum.auto()
    downloading_geo_object = enum.auto()
    downloading_tables = enum.auto()
    downloaded = enum.auto()
    processing = enum.auto()
    processed = enum.auto()
    failed = enum.auto()


@dataclass
class FetchResult:
    status: FetchStatus
    status_message: str
    result: Any


class Fetch:
    def __init__(self, object_metadata: EvoObjectMetadata):
        self.status = FetchStatus.not_begun
        self.status_msg = ""
        self._object_metadata = object_metadata
        self._object_specific_fetcher: Optional[_ObjectSpecificFetch] = None

    async def _do_download(self, api_client: ObjectAPIClient, data_client: ObjectDataClient):
        raise NotImplementedError()

    @staticmethod
    def _get_schema_id(geo_object):
        return geo_object.SCHEMA_ID

    async def download(self, api_client: ObjectAPIClient, data_client: ObjectDataClient) -> "Fetch":
        if self.status != FetchStatus.not_begun:
            raise Exception(f"{self._object_metadata.object_id} is already downloading")

        self.status = FetchStatus.downloading_geo_object

        downloaded_obj = await api_client.download_object_by_id(
            self._object_metadata.object_id, version=self._object_metadata.version_id
        )
        geo_object: Serialiser = json_loads(json.dumps(downloaded_obj.as_dict(), cls=GSONEncoder))

        try:
            self._object_specific_fetcher = self.get_fetcher(self._get_schema_id(geo_object))
        except NotImplementedError:
            self.status = FetchStatus.failed
            self.status_msg = f"Schema {geo_object.SCHEMA_ID} not supported"
            return self

        self.status = FetchStatus.downloading_tables

        await self._object_specific_fetcher.download_blobs(geo_object, self._object_metadata.version_id, data_client)

        self.status = FetchStatus.downloaded
        return self

    def process(self):
        if self.status != FetchStatus.downloaded:
            raise Exception(
                f"{self._object_metadata.object_id} is cannot be processed because it has status {self.status}"
            )
        self.status = FetchStatus.processing
        processed = self._object_specific_fetcher.process()
        self.status = FetchStatus.processed
        return processed

    @classmethod
    def get_fetcher(cls, schema_id: str) -> "_ObjectSpecificFetch":
        for subclass in _ObjectSpecificFetch.__subclasses__():
            if subclass.matches_schema_id(schema_id):
                return subclass()
        raise NotImplementedError(f"{schema_id} not handled")

    @classmethod
    async def _async_downloader(cls, as_completed_future):
        for result in as_completed_future:
            fetcher = await result
            if fetcher.status == FetchStatus.failed:
                yield FetchResult(status=fetcher.status, status_message=fetcher.status_msg, result=None)
            else:
                processed = fetcher.process()
                yield FetchResult(status=fetcher.status, status_message=fetcher.status_msg, result=processed)

    @classmethod
    def download_all(
        cls,
        objects: list[EvoObjectMetadata],
        api_client: ObjectAPIClient,
        data_client: ObjectDataClient,
    ):
        fetchers: list[Fetch] = []
        for object_metadata in objects:
            fetchers.append(cls(object_metadata))

        futures = asyncio.as_completed([f.download(api_client, data_client) for f in fetchers])

        return cls._async_downloader(futures)


class _ObjectSpecificFetch:
    supported_schemas: list[str]

    @classmethod
    def matches_schema_id(cls, schema_id: str) -> bool:
        for schema_regex in cls.supported_schemas:
            if re.match(schema_regex, schema_id):
                return True
        return False

    async def download_blobs(self, geo_object: Serialiser, version_id: str, data_client):
        raise NotImplementedError()

    def process(self):
        raise NotImplementedError()

    @staticmethod
    async def _get_attributes_from_parts(parts, data_client, obj_id, version_id) -> list[EvoAttributes]:
        attributes = []
        if parts is not None:
            for attrs in parts.attributes:
                column = await data_client.download_table(obj_id, version_id, attrs.values.as_dict())

                lookup_table = None
                lookup_table_ref = getattr(attrs, "table", None)
                if lookup_table_ref is not None:
                    lookup_table = await data_client.download_table(obj_id, version_id, lookup_table_ref.as_dict())

                if (nan_description_go := getattr(attrs, "nan_description", None)) is not None:
                    nan_description = nan_description_go.values

                attrs_column = EvoAttributes(
                    name=attrs.name,
                    type=attrs.attribute_type,
                    description=attrs.attribute_description,
                    fetched_table=column,
                    lookup_table=lookup_table,
                    nan_description=nan_description,
                )
                attributes.append(attrs_column)

        return attributes

    @staticmethod
    def _process_attrs(attributes: list[EvoAttributes]):
        for attr in attributes:
            attr.process()


class FetchPolyline(_ObjectSpecificFetch):
    supported_schemas = [
        r"/objects/line-segments/2.\d+.\d+/line-segments.schema.json",
    ]

    def __init__(self):
        self._indices = None  # segments
        self._vertices = None
        self._chunks = None
        self._name = None
        self._attributes = None

    async def download_blobs(
        self,
        geo_object: LineSegments_V2_0_0 | LineSegments_V2_1_0 | LineSegments_V2_2_0,
        version_id: str,
        data_client,
    ):
        self._name = geo_object.name

        obj_id = geo_object.uuid

        self._indices = await data_client.download_table(obj_id, version_id, geo_object.segments.indices.as_dict())
        self._vertices = await data_client.download_table(obj_id, version_id, geo_object.segments.vertices.as_dict())
        if geo_object.parts is not None:
            self._chunks = await data_client.download_table(obj_id, version_id, geo_object.parts.chunks.as_dict())
        else:
            self._chunks = None

        self._attributes = await self._get_attributes_from_parts(geo_object.parts, data_client, obj_id, version_id)

    def process(self) -> FetchedLines:
        indices_table = numpy.asarray(self._indices)
        vertices_table = numpy.asarray(self._vertices)

        if self._chunks is not None:
            chunks_table = numpy.asarray(self._chunks)
        else:
            chunks_table = numpy.asarray([[0, len(indices_table)]])

        parts = []
        for start, length in chunks_table:
            parts.append(indices_table[start : start + length])

        paths = []
        for part in parts:
            _path = vertices_table[part[:, 0]]
            path = numpy.append(_path, vertices_table[part[-1, -1]].reshape(1, 3), axis=0)

            if len(path) == 2 and numpy.array_equal(path[0], path[1]):
                print(f"Skipped point {path}")
                continue

            paths.append(path)

        self._process_attrs(self._attributes)
        return FetchedLines(self._name, paths, self._attributes)


TriangleMesh = TriangleMesh_V2_0_0 | TriangleMesh_V2_1_0 | TriangleMesh_V2_2_0


class FetchTriangleMesh(_ObjectSpecificFetch):
    supported_schemas = [
        "/objects/triangle-mesh/2.\d+.\d+/triangle-mesh.schema.json",
    ]

    def __init__(self):
        self._name = None
        self._indices = None
        self._vertices = None
        self._chunks = None
        self._attributes = None

    async def download_blobs(self, geo_object: TriangleMesh_V2_1_0, version_id: str, data_client):
        obj_id = geo_object.uuid

        self._name = geo_object.name
        self._indices = await data_client.download_table(obj_id, version_id, geo_object.triangles.indices.as_dict())
        self._vertices = await data_client.download_table(obj_id, version_id, geo_object.triangles.vertices.as_dict())
        if geo_object.parts is not None:
            self._chunks = await data_client.download_table(obj_id, version_id, geo_object.parts.chunks.as_dict())
        else:
            self._chunks = None

        self._attributes = await self._get_attributes_from_parts(geo_object.parts, data_client, obj_id, version_id)

    def process(self) -> FetchedTriangleMesh:
        indices_table = numpy.asarray(self._indices)
        vertices_table = numpy.asarray(self._vertices)

        if self._chunks is not None:
            chunks_table = numpy.asarray(self._chunks)
        else:
            chunks_table = numpy.asarray([[0, len(indices_table)]])

        parts = []
        for start, length in chunks_table:
            parts.append(indices_table[start : start + length])

        self._process_attrs(self._attributes)
        return FetchedTriangleMesh(self._name, vertices_table, parts, self._attributes)
