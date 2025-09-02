import asyncio
import copy
import enum
import json
import numpy
from typing import Optional

from evo.data_converters.common import EvoObjectMetadata
from evo.objects import ObjectAPIClient
from evo.objects.utils import ObjectDataClient
from evo_schemas import json_loads, LineSegments_V2_0_0, LineSegments_V2_1_0, LineSegments_V2_2_0, TriangleMesh_V2_1_0
from evo_schemas.elements.serialiser import GSONEncoder, Serialiser


from evo.data_converters.duf.common.types import EvoAttributes, FetchedTriangleMesh, FetchedLines


class FetchStatus(enum.Enum):
    not_begun = enum.auto()
    downloading_geo_object = enum.auto()
    downloading_tables = enum.auto()
    downloaded = enum.auto()
    processing = enum.auto()
    processed = enum.auto()


class Fetch:
    def __init__(self, object_metadata: EvoObjectMetadata):
        self.status = FetchStatus.not_begun
        self._object_metadata = object_metadata
        self._object_specific_fetcher: Optional[_ObjectSpecificFetch] = None

    async def _do_download(self, api_client: ObjectAPIClient, data_client: ObjectDataClient):
        raise NotImplementedError()

    async def download(self, api_client: ObjectAPIClient, data_client: ObjectDataClient) -> "Fetch":
        if self.status != FetchStatus.not_begun:
            raise Exception(f"{self._object_metadata.object_id} is already downloading")

        self.status = FetchStatus.downloading_geo_object

        downloaded_obj = await api_client.download_object_by_id(
            self._object_metadata.object_id, version=self._object_metadata.version_id
        )
        geo_object: Serialiser = json_loads(json.dumps(downloaded_obj.as_dict(), cls=GSONEncoder))

        self._object_specific_fetcher = self.get_fetcher(geo_object.SCHEMA_ID)

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
            if schema_id in subclass.supported_schemas:
                return subclass()
        raise NotImplementedError(f"{schema_id} not handled")

    @classmethod
    async def _async_downloader(cls, as_completed_future):
        for result in as_completed_future:
            fetcher = await result
            yield fetcher.process()

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

    async def download_blobs(self, geo_object: Serialiser, version_id: str, data_client):
        raise NotImplementedError()

    def process(self):
        raise NotImplementedError()


class FetchPolyline(_ObjectSpecificFetch):
    # TODO re-use this for export_omf_lineset?

    supported_schemas = [
        "/objects/line-segments/2.0.0/line-segments.schema.json",
        "/objects/line-segments/2.1.0/line-segments.schema.json",
        "/objects/line-segments/2.2.0/line-segments.schema.json",
    ]

    def __init__(self):
        self._indices = None  # segments
        self._vertices = None
        self._chunks = None
        self._name = None
        self._attributes = None
        self._lookups = None

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

        self._attributes = []
        self._lookups = []
        if geo_object.parts is not None:
            for attrs in geo_object.parts.attributes:
                # TODO What is "nan_description"?
                column = await data_client.download_table(obj_id, version_id, attrs.values.as_dict())
                attrs_column = EvoAttributes(
                    name=attrs.name,
                    values=column,
                    type=attrs.attribute_type,
                    description=attrs.attribute_description,
                    nan_description=getattr(attrs, 'nan_description', None)
                )
                self._attributes.append(attrs_column)

                lookup_table = getattr(attrs, 'table', None)
                if lookup_table is not None:
                    lookup = await data_client.download_table(obj_id, version_id, lookup_table.as_dict())
                    self._lookups.append(lookup)
                else:
                    self._lookups.append(None)

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

        processed_attr_columns = []
        for attr_table, lookup_table in zip(self._attributes, self._lookups):
            attr_table = copy.copy(attr_table)
            attr_values = numpy.asarray(attr_table.values)
            attr_values.reshape(len(attr_values))
            if lookup_table is None:
                processed = attr_values
            else:
                lookup = {k: v for k, v in numpy.asarray(lookup_table)}
                lookup_vec = numpy.vectorize(lookup.get)
                processed = lookup_vec(attr_values)
            attr_table.values = processed.reshape(len(processed))
            processed_attr_columns.append(attr_table)

        return FetchedLines(self._name, paths, processed_attr_columns)


class FetchTriangleMesh(_ObjectSpecificFetch):
    supported_schemas = [
        # TODO More?
        "/objects/triangle-mesh/2.1.0/triangle-mesh.schema.json",
    ]


    def __init__(self):
        self._name = None
        self._indices = None
        self._vertices = None
        self._chunks = None
        self._attributes = None
        self._lookups = None


    async def download_blobs(self, geo_object: TriangleMesh_V2_1_0, version_id: str, data_client):
        obj_id = geo_object.uuid

        self._name = geo_object.name
        self._indices = await data_client.download_table(obj_id, version_id, geo_object.triangles.indices.as_dict())
        self._vertices = await data_client.download_table(obj_id, version_id, geo_object.triangles.vertices.as_dict())
        if geo_object.parts is not None:
            self._chunks = await data_client.download_table(obj_id, version_id, geo_object.parts.chunks.as_dict())
        else:
            self._chunks = None

        self._attributes = []
        self._lookups = []
        if geo_object.parts is not None:
            for attrs in geo_object.parts.attributes:
                # TODO What is "nan_description"?
                column = await data_client.download_table(obj_id, version_id, attrs.values.as_dict())
                attrs_column = EvoAttributes(
                    name=attrs.name,
                    values=column,
                    type=attrs.attribute_type,
                    description=attrs.attribute_description,
                    nan_description=getattr(attrs, 'nan_description', None)
                )
                self._attributes.append(attrs_column)
                lookup_table = getattr(attrs, 'table', None)
                if lookup_table is not None:
                    lookup = await data_client.download_table(obj_id, version_id, lookup_table.as_dict())
                    self._lookups.append(lookup)
                else:
                    self._lookups.append(None)

    def process(self) -> FetchedTriangleMesh:
        indices_table = numpy.asarray(self._indices)
        vertices_table = numpy.asarray(self._vertices)

        if self._chunks is not None:
            chunks_table = numpy.asarray(self._chunks)
        else:
            chunks_table = numpy.asarray([[0, len(indices_table)]])

        parts = []
        for start, length in chunks_table:
            parts.append(indices_table[start: start + length])

        processed_attr_columns = []
        for attr_table, lookup_table in zip(self._attributes, self._lookups):
            attr_table = copy.copy(attr_table)
            attr_values = numpy.asarray(attr_table.values)
            attr_values.reshape(len(attr_values))
            if lookup_table is None:
                processed = attr_values
            else:
                lookup = {k: v for k, v in numpy.asarray(lookup_table)}
                lookup_vec = numpy.vectorize(lookup.get)
                processed = lookup_vec(attr_values)
            attr_table.values = processed.reshape(len(processed))
            processed_attr_columns.append(attr_table)

        return FetchedTriangleMesh(self._name, vertices_table, parts, processed_attr_columns)

