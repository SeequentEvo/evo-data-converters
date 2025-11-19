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

from evo.data_converters.common.objects.attributes import AttributeFactory
from evo.data_converters.common.objects.downhole_collection.tables import MeasurementTableAdapter
from evo.data_converters.common.crs import crs_from_any
import evo.logging
from evo.objects.utils.data import ObjectDataClient
from evo_schemas.components import (
    BoundingBox_V1_0_1 as BoundingBox,
    CategoryData_V1_0_1 as CategoryData,
    Crs_V1_0_1 as Crs,
    DownholeAttributes_V1_0_0 as DownholeAttributes,
    DownholeAttributes_V1_0_0_Item_DistanceTable as DownholeAttributes_Item_DistanceTable,
    DownholeAttributes_V1_0_0_Item_IntervalTable as DownholeAttributes_Item_IntervalTable,
    DownholeDirectionVector_V1_0_0 as DownholeDirectionVector,
    HoleChunks_V1_0_0 as HoleChunks,
    Intervals_V1_0_1 as Intervals,
    IntervalTable_V1_2_0_FromTo as IntervalTable_FromTo,
    DistanceTable_V1_2_0_Distance as DistanceTable_Distance,
    OneOfAttribute_V1_2_0 as OneOfAttribute,
)
from evo_schemas.elements import (
    FloatArray1_V1_0_1 as FloatArray1,
    FloatArray2_V1_0_1 as FloatArray2,
    FloatArray3_V1_0_1 as FloatArray3,
    IntegerArray1_V1_0_1 as IntegerArray1,
    LookupTable_V1_0_1 as LookupTable,
    UnitLength_V1_0_1_UnitCategories as UnitLength_UnitCategories,
)
from evo_schemas.objects import (
    DownholeCollection_V1_3_1 as DownholeCollectionGeoscienceObject,
    DownholeCollection_V1_3_1_Location as DownholeCollection_Location,
)
import pyarrow as pa

from .downhole_collection import (
    DownholeCollection,
    IntervalTable as IntervalMeasurementTable,
    DistanceTable as DistanceMeasurementTable,
)

AZIMUTH: float = 0.0  # Assume vertical
DIP: float = 90.0  # Positive dip = down

logger = evo.logging.getLogger("data_converters")


class DownholeCollectionToGeoscienceObject:
    """Converter for transforming DownholeCollection data into a DownholeCollectionGeoscienceObject"""

    def __init__(self, dhc: DownholeCollection, data_client: ObjectDataClient) -> None:
        """
        Initialize the converter with a downhole collection and data client.

        :param dhc: The downhole collection to convert
        :param data_client: Client for saving and managing object data
        """
        self.dhc: DownholeCollection = dhc
        self.data_client: ObjectDataClient = data_client

    def convert(self) -> DownholeCollectionGeoscienceObject:
        """
        Convert the downhole collection into a geoscience object.

        :return: A complete DownholeCollection geoscience object with all spatial data,
                 location information, and measurement collections
        """
        logger.debug("Converting to Geoscience Object.")

        coordinate_reference_system = self.create_coordinate_reference_system()
        bounding_box = self.create_bounding_box()

        distance_unit = UnitLength_UnitCategories("m")

        dhc_location = self.create_dhc_location()
        dhc_collections = self.create_dhc_collections()

        dhc_go = DownholeCollectionGeoscienceObject(
            # Base Object
            name=self.dhc.name,
            uuid=None,
            # Base Spatial Data
            bounding_box=bounding_box,
            coordinate_reference_system=coordinate_reference_system,
            # Downhole Collection
            distance_unit=distance_unit,
            location=dhc_location,
            collections=dhc_collections,
        )

        logger.debug(f"Created: {dhc_go}")

        return dhc_go

    def create_coordinate_reference_system(self) -> Crs:
        """
        Create a coordinate reference system object from the downhole collection's CRS.

        :return: Standardised CRS object
        """
        return crs_from_any(self.dhc.coordinate_reference_system)

    def create_bounding_box(self) -> BoundingBox:
        """
        Create a bounding box object from the downhole collection's spatial extent.

        :return: BoundingBox object defining the spatial extent with min/max X, Y, Z values
        """
        bounding_box: list[float] = self.dhc.get_bounding_box()

        return BoundingBox(
            min_x=bounding_box[0],
            max_x=bounding_box[1],
            min_y=bounding_box[2],
            max_y=bounding_box[3],
            min_z=bounding_box[4],
            max_z=bounding_box[5],
        )

    def create_dhc_location(self) -> DownholeCollection_Location:
        """
        Create a downhole collection location object containing all location-related data.

        This includes coordinates, distances, hole chunks, hole IDs, paths, and attributes
        from the collar information.

        :return: Complete location object with spatial and organisational data
        """
        measurement_table = self.get_first_distance_measurement_table()

        return DownholeCollection_Location(
            # Attributes
            attributes=self.create_dhc_location_attributes(),
            # Locations
            coordinates=self.create_dhc_location_coordinates(),
            # Hole Collars
            distances=self.create_dhc_location_distances(),
            holes=self.create_dhc_hole_chunks(measurement_table),
            # DC Location
            hole_id=self.create_dhc_location_hole_id(),
            path=self.create_dhc_location_path(),
        )

    def create_dhc_location_attributes(self) -> OneOfAttribute | None:
        """
        Create attribute objects from collar attribute columns.

        :return: List of attribute objects, or None if no attributes exist
        """
        attributes: OneOfAttribute = []
        for attribute_name in self.dhc.collars.get_attribute_column_names():
            attribute = AttributeFactory.create(
                name=attribute_name,
                series=self.dhc.collars.df[attribute_name],
                client=self.data_client,
            )
            if attribute:
                attributes.append(attribute)
        return attributes or None

    def create_dhc_location_coordinates(self) -> FloatArray3:
        """
        Create a 3D coordinate array from downhole collar locations.

        :return: FloatArray3 object containing X, Y, Z coordinates for each collar
        """
        coordinates_table = self.coordinates_table()
        coordinates_args = self.data_client.save_table(coordinates_table)
        return FloatArray3.from_dict(coordinates_args)

    def create_dhc_location_distances(self) -> FloatArray3:
        """
        Create distance measurements (final, target, current) for each downhole.

        Currently sets all three distance values to the final depth from collar data.

        :return: FloatArray3 object containing distance measurements
        """
        distances_table = self.distances_table()
        distances_args = self.data_client.save_table(distances_table)
        return FloatArray3.from_dict(distances_args)

    def create_dhc_hole_chunks(self, measurement_table: MeasurementTableAdapter) -> HoleChunks:
        """
        Create hole chunks metadata describing data organization for measurement tables.

        :param measurement_table: The measurement table to create chunks for

        :return: HoleChunks object with offset and count information for each hole
        """
        holes_table = self.holes_table(measurement_table)
        holes_args = self.data_client.save_table(holes_table)
        return HoleChunks.from_dict(holes_args)

    def create_dhc_location_hole_id(self) -> CategoryData:
        """
        Create a categorical hole ID mapping with lookup table and indices.

        :return: CategoryData object mapping hole indices to hole ID strings
        """
        lookup_table, integer_array_table = self.hole_id_tables()

        lookup_table_args = self.data_client.save_table(lookup_table)
        lookup_table_go = LookupTable.from_dict(lookup_table_args)

        integer_array_args = self.data_client.save_table(integer_array_table)
        integer_array_go = IntegerArray1.from_dict(integer_array_args)

        return CategoryData(table=lookup_table_go, values=integer_array_go)

    def create_dhc_location_path(self) -> DownholeDirectionVector:
        """
        Create downhole direction vectors defining the trajectory of each hole.

        Currently assumes all holes are vertical with azimuth=0° and dip=90°.

        :return: DownholeDirectionVector object with distance, azimuth, and dip values
        """
        path_table = self.path_table()
        path_args = self.data_client.save_table(path_table)
        return DownholeDirectionVector.from_dict(path_args)

    def create_dhc_collections(self) -> DownholeAttributes:
        """
        Create all measurement data collections associated with the downholes.

        Processes both distance-based and interval-based measurement tables and
        converts them to the appropriate attribute collection format.

        :return: List of attribute collection objects (distance or interval tables)
        """
        collections: DownholeAttributes = []

        for measurement_table in self.dhc.get_measurement_tables():
            if isinstance(measurement_table, DistanceMeasurementTable):
                collections.append(self.create_dhc_collection_distance(measurement_table))
            elif isinstance(measurement_table, IntervalMeasurementTable):
                collections.append(self.create_dhc_collection_interval(measurement_table))

        return collections

    def create_dhc_collection_distance(self, mt: DistanceMeasurementTable) -> DownholeAttributes_Item_DistanceTable:
        """
        Create a distance-based attribute collection from a distance measurement table.

        :param mt: Distance measurement table to convert

        :return: Distance table attribute collection with depth values and associated attributes
        """
        distances_table = self.collection_distances_table(mt)
        distances_args = self.data_client.save_table(distances_table)
        distances_go = FloatArray1.from_dict(distances_args)

        distances_unit = UnitLength_UnitCategories("m")

        distance_go = DistanceTable_Distance(
            attributes=self.create_collection_attributes(mt),
            unit=distances_unit,
            values=distances_go,
        )

        distance_table_go = DownholeAttributes_Item_DistanceTable(
            name="distances", holes=self.create_dhc_hole_chunks(mt), distance=distance_go
        )

        return distance_table_go

    def create_dhc_collection_interval(self, mt: IntervalMeasurementTable) -> DownholeAttributes_Item_IntervalTable:
        """
        Create an interval-based attribute collection from an interval measurement table.

        :param mt: Interval measurement table to convert

        :return: Interval table attribute collection with from/to depths and associated attributes
        """
        start_end_table = self.collection_start_end_table(mt)
        start_end_args = self.data_client.save_table(start_end_table)
        start_end_go = FloatArray2.from_dict(start_end_args)

        intervals_go = Intervals(start_and_end=start_end_go)

        interval_table_from_to = IntervalTable_FromTo(
            intervals=intervals_go, attributes=self.create_collection_attributes(mt)
        )

        interval_table_go = DownholeAttributes_Item_IntervalTable(
            name="intervals",
            from_to=interval_table_from_to,
            holes=self.create_dhc_hole_chunks(mt),
        )

        return interval_table_go

    def create_collection_attributes(self, mt: MeasurementTableAdapter) -> OneOfAttribute | None:
        """
        Create attribute objects from measurement table attribute columns.

        Preserves NaN value metadata from the measurement table if present.

        :param mt: Measurement table containing attribute columns

        :return: List of attribute objects, or None if no attributes exist
        """
        attributes: OneOfAttribute = []
        for attribute_name in mt.get_attribute_columns():
            series = mt.df[attribute_name]
            if mt.get_nan_values(attribute_name):
                series.attrs["nan_values"] = mt.get_nan_values(attribute_name)
            attribute = AttributeFactory.create(
                name=attribute_name,
                series=series,
                client=self.data_client,
            )
            if attribute:
                attributes.append(attribute)
        return attributes or None

    def coordinates_table(self) -> pa.Table:
        """
        Create a PyArrow table of 3D coordinates from collar information.

        :return: PyArrow table with X, Y, Z coordinate columns
        """
        coordinates_df = self.dhc.collars.df[["x", "y", "z"]]
        coordinates_schema = pa.schema(
            [
                pa.field("x", pa.float64()),
                pa.field("y", pa.float64()),
                pa.field("z", pa.float64()),
            ]
        )
        return pa.Table.from_pandas(coordinates_df, schema=coordinates_schema)

    def distances_table(self) -> pa.Table:
        """
        Create a PyArrow table of distance measurements from final depth of each downhole.

        Currently sets final, target, and current distances all to the final_depth value.

        :return: PyArrow table with final, target, and current distance columns
        """
        distances_schema = pa.schema(
            [
                pa.field("final", pa.float64()),
                pa.field("target", pa.float64()),
                pa.field("current", pa.float64()),
            ]
        )
        arrays = [
            pa.array(self.dhc.collars.df["final_depth"], type=pa.float64()),
            pa.array(self.dhc.collars.df["final_depth"], type=pa.float64()),
            pa.array(self.dhc.collars.df["final_depth"], type=pa.float64()),
        ]
        return pa.Table.from_arrays(arrays, schema=distances_schema)

    def holes_table(self, mt: MeasurementTableAdapter) -> pa.Table:
        """
        Create hole chunk metadata table describing data organization for each downhole.

        Generates indexing information that describes where each hole's data begins
        (offset) and how many data points it contains (count) in a flattened data array.

        :param mt: Measurement table to generate hole chunk metadata for

        :return: PyArrow table with hole_index, offset, and count columns
        """
        grouped = mt.df.groupby("hole_index", sort=False).size().reset_index().rename(columns={0: "count"})
        grouped["offset"] = grouped["count"].shift(1, fill_value=0).cumsum()
        holes_schema = pa.schema(
            [
                pa.field("hole_index", pa.int32()),
                pa.field("offset", pa.uint64()),
                pa.field("count", pa.uint64()),
            ]
        )
        arrays = [
            pa.array(grouped["hole_index"], type=pa.int32()),
            pa.array(grouped["offset"], type=pa.uint64()),
            pa.array(grouped["count"], type=pa.uint64()),
        ]
        return pa.Table.from_arrays(arrays, schema=holes_schema)

    def hole_id_tables(self) -> tuple[pa.Table, pa.Table]:
        """
        Create lookup and index tables for hole ID categorical mapping.

        :return: Tuple of (lookup table mapping indices to ID strings, integer array table of indices)
        """
        lookup_table = pa.table(
            {"key": self.dhc.collars.df["hole_index"], "value": self.dhc.collars.df["hole_id"]},
            schema=pa.schema(
                [
                    pa.field("key", pa.int32()),
                    pa.field("value", pa.string()),
                ]
            ),
        )
        integer_array_table = pa.table(
            {"data": self.dhc.collars.df["hole_index"]}, schema=pa.schema([pa.field("data", pa.int32())])
        )
        return (lookup_table, integer_array_table)

    def path_table(self) -> pa.Table:
        """
        Create directional path table for downholes.

        Currently assumes all holes are vertical (azimuth=0.0°, dip=90.0°).
        Positive dip indicates downward direction.
        Distance values are taken from the first distance measurement table.

        :return: PyArrow table with distance, azimuth, and dip columns
        """
        path_schema = pa.schema(
            [
                pa.field("distance", pa.float64()),
                pa.field("azimuth", pa.float64()),
                pa.field("dip", pa.float64()),
            ]
        )
        measurements = self.get_first_distance_measurement_table()
        num_measurements = len(measurements.df)

        arrays = [
            pa.array(measurements.get_depth_values(), type=pa.float64()),
            pa.array([AZIMUTH] * num_measurements, type=pa.float64()),
            pa.array([DIP] * num_measurements, type=pa.float64()),
        ]

        return pa.Table.from_arrays(arrays, schema=path_schema)

    def collection_distances_table(self, mt: DistanceMeasurementTable) -> pa.Table:
        """
        Create a PyArrow table of distance values from a distance measurement table.

        :param mt: Distance measurement table to extract values from

        :return: PyArrow table with a single 'values' column containing all distances
        """
        distances_df = mt.df[[mt.get_primary_column()]].rename(columns={mt.get_primary_column(): "values"})
        distances_schema = pa.schema([pa.field("values", pa.float64())])
        return pa.Table.from_pandas(distances_df, schema=distances_schema)

    def collection_start_end_table(self, mt: IntervalMeasurementTable) -> pa.Table:
        """
        Create a PyArrow table of interval start and end depths.

        :param mt: Interval measurement table to extract from/to values from

        :return: PyArrow table with 'from' and 'to' columns defining intervals
        """
        intervals_df = mt.df[[mt.get_from_column(), mt.get_to_column()]].rename(
            columns={mt.get_from_column(): "from", mt.get_to_column(): "to"}
        )
        intervals_schema = pa.schema([pa.field("from", pa.float64()), pa.field("to", pa.float64())])
        return pa.Table.from_pandas(intervals_df, intervals_schema)

    def get_first_distance_measurement_table(self) -> DistanceMeasurementTable:
        """
        Get the first distance measurement table from the downhole collection.

        :return: The first available distance measurement table

        :raises ValueError: If no distance measurement tables are found
        """
        distance_tables = self.dhc.get_measurement_tables(filter=[DistanceMeasurementTable])
        if len(distance_tables) >= 1 and isinstance(distance_tables[0], DistanceMeasurementTable):
            return distance_tables[0]
        raise ValueError("No distance measurement tables found.")
