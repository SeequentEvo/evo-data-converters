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
from __future__ import annotations

import contextlib
import copy
import hashlib
import math
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4, UUID

import numpy
import pandas as pd
import pytest
from evo_schemas.objects import DownholeCollection_V1_3_0 as DownholeCollectionGo
from packages.gef.tests.consts import GEF1, GEF2, GEF_XML_MULTIPLE

from evo.common.connector import APIConnector
from evo.common.data import Environment
from evo.common.interfaces import IContext, ICache

from evo.objects.client.object_client import DownloadedObject
from evo.objects.data import ObjectSchema, ObjectReference

from evo_schemas.objects.downhole_collection import DownholeCollection_V1_3_1

from evo.data_converters.common import EvoWorkspaceMetadata, create_evo_object_service_and_data_client
from evo.data_converters.common.objects.downhole_collection import DownholeCollection
from evo.data_converters.common.objects.downhole_collection_to_geoscience_object import (
    DownholeCollectionToGeoscienceObject,
)
from evo.data_converters.gef.importer import convert_gef
from evo.data_converters.gef.objects import DownholeCollection, DownholeCollectionData
from evo.objects.data import ObjectMetadata


class TestConvertGef:
    """Test the convert_gef function behaves as intended."""

    @pytest.fixture
    def sample_filepaths(self):
        """Sample file paths for testing."""
        return [Path("test1.gef"), Path("test2.gef")]

    @pytest.fixture
    def workspace_metadata(self):
        """Mock workspace metadata with hub_url."""
        hub_url = "https://example.org"
        cache_root = tempfile.TemporaryDirectory()
        return EvoWorkspaceMetadata(workspace_id=str(uuid4()), cache_root=cache_root.name, hub_url=hub_url)

    @pytest.fixture
    def mock_downhole_collection_go(self):
        """Mock downhole collection geoscience object."""
        dhc_go = Mock(spec=DownholeCollectionGo)
        dhc_go.tags = {}
        return dhc_go

    @pytest.fixture
    def mock_downhole_collection(self):
        """Mock downhole collection intermediary object."""
        dhc = Mock(spec=DownholeCollection)
        return dhc

    @pytest.fixture
    def mock_object_metadata(self):
        """Mock object metadata."""
        return Mock(spec=ObjectMetadata)

    @patch("evo.data_converters.gef.importer.gef_to_evo.publish_geoscience_objects_sync")
    @patch("evo.data_converters.gef.importer.gef_to_evo.create_evo_object_service_and_data_client")
    @patch("evo.data_converters.gef.importer.gef_to_evo.create_from_parsed_gef_cpts")
    @patch("evo.data_converters.gef.importer.gef_to_evo.parse_gef_files")
    @patch("evo.data_converters.gef.importer.gef_to_evo.DownholeCollectionToGeoscienceObject")
    def test_convert_gef_with_workspace_metadata_and_hub_url(
        self,
        mock_converter,
        mock_parse_files,
        mock_create_collection,
        mock_create_clients,
        mock_publish,
        sample_filepaths,
        workspace_metadata,
        mock_downhole_collection,
        mock_downhole_collection_go,
        mock_object_metadata,
    ):
        """Test conversion with workspace metadata and hub_url - should publish."""
        collection_name = "Test Collection"

        mock_create_clients.return_value = (Mock(), Mock())
        mock_converter.return_value = Mock(
            spec=DownholeCollectionToGeoscienceObject, convert=Mock(return_value=mock_downhole_collection_go)
        )
        mock_parse_files.return_value = Mock()
        mock_create_collection.return_value = mock_downhole_collection
        mock_publish.return_value = mock_object_metadata

        result = convert_gef(
            name=collection_name, filepaths=sample_filepaths, evo_workspace_metadata=workspace_metadata
        )

        assert result == mock_object_metadata
        assert isinstance(result, ObjectMetadata)
        mock_publish.assert_called_once()

        mock_create_collection.assert_called_once()
        assert mock_create_collection.call_args.kwargs["name"] == collection_name

        # Check tags were added
        expected_tags = {
            "Source": "GEF-CPT files (via Evo Data Converters)",
            "Stage": "Experimental",
            "InputType": "GEF-CPT",
        }
        for key, value in expected_tags.items():
            assert mock_downhole_collection_go.tags[key] == value


@dataclass
class _CPTSpec:
    collar_locations: list[float]
    collar_attributes: dict[str, Any]
    attributes: dict[str, str]
    hole_id: str
    hole_distancess: dict[str, float]
    num_rows: int
    sum_distances: float
    sum_azimuths: float
    sum_dips: float
    bbox: tuple[float, float, float, float, float, float]


EXPECTED_PATH_ATTRIBUTES = [
    "depthOffset",
    "delapsedTime",
    "inclinationEW",
    "inclinationNS",
    "inclinationResultant",
    "depth",
]


class _CPTData:
    def __init__(self, cpt_tables, collar_attributes, collar_locations, hole_distances, hole_ids, path_tables, path_attr_tables, bbox):
        self.cpt_tables = cpt_tables
        self.collar_attributes = collar_attributes
        self.collar_locations = collar_locations
        self.hole_distances = hole_distances
        self.hole_ids = hole_ids
        self.path_tables = path_tables
        self.path_attr_tables = path_attr_tables
        self.bbox = bbox

    @classmethod
    def from_gef_object(cls, gef_object, data_client):
        attrs = gef_object.location.attributes
        collar_attrs_pd = data_client.load_attributes(attrs)
        collar_locations_pd = data_client.load_table(gef_object.location.coordinates).to_pandas()
        hole_distances = data_client.load_table(gef_object.location.distances).to_pandas()
        hole_ids = data_client.load_category(gef_object.location.hole_id)
        path_tables, path_attr_tables = _load_path_geometries(gef_object, data_client)
        cpt_tables = _load_distance_collection(gef_object, data_client)
        bbox = _get_bbox(gef_object)

        if cpt_tables:
            # For GEF imports, the collection is supposed to match up exactly to the geometry definition
            # (gef_object.location).
            assert len(cpt_tables) == len(path_tables) == len(path_attr_tables)
            for cpt_table, path_table, attr_table in zip(cpt_tables, path_tables, path_attr_tables, strict=True):
                assert len(cpt_table) == len(path_table)
                assert len(cpt_table) == len(attr_table)

        return cls(
            cpt_tables=cpt_tables,
            collar_attributes=collar_attrs_pd,
            collar_locations=collar_locations_pd,
            hole_distances=hole_distances,
            hole_ids=hole_ids,
            path_tables=path_tables,
            path_attr_tables=path_attr_tables,
            bbox=bbox,
        )

    @classmethod
    def from_gef_dict(cls, object_dict, data_client):
        gef_object = DownholeCollection_V1_3_1.from_dict(object_dict)
        return cls.from_gef_object(gef_object, data_client)

    @property
    def attribute_names(self):
        return self.cpt_tables[0].columns.tolist()

    def _table_column_hashes(self, table: pd.DataFrame) -> dict[str, str]:
        column_hashes = {}
        for col in table.columns:
            col_hash = hashlib.md5(table[col].values.tobytes()).hexdigest()
            column_hashes[col] = str(col_hash)
        return column_hashes

    def get_table_column_hashes(self, index) -> dict[str, str]:
        return self._table_column_hashes(self.cpt_tables[index]) | self._table_column_hashes(self.path_attr_tables[index])

    def verify_hole_distances(self, index: int, spec: _CPTSpec):
        final, target, current = self.hole_distances.iloc[index]
        assert math.isclose(final, spec.hole_distancess["final"], rel_tol=1e-5)
        assert math.isclose(target, spec.hole_distancess["target"], rel_tol=1e-5)
        assert math.isclose(current, spec.hole_distancess["current"], rel_tol=1e-5)

    def verify_collar_attributes(self, index: int, spec: _CPTSpec):
        actual_dict = self.collar_attributes.iloc[index].to_dict()
        for key in spec.collar_attributes.keys():
            actual = actual_dict[key]
            expected = spec.collar_attributes[key][0]
            if isinstance(expected, float):
                assert math.isclose(expected, actual, rel_tol=1e-5)
            else:
                assert expected == actual

    def verify_collar_locations(self, index: int, spec: _CPTSpec):
        actual_list = self.collar_locations.iloc[index].to_list()
        assert numpy.isclose(actual_list, spec.collar_locations, rtol=1e-4).all()

    def verify_attributes(self, index: int, spec: _CPTSpec, expected_attribute_columns):
        expected_path_attribute = {attr for attr in expected_attribute_columns if attr in EXPECTED_PATH_ATTRIBUTES}
        expected_cpt_attributes = {attr for attr in expected_attribute_columns if attr not in EXPECTED_PATH_ATTRIBUTES}

        assert expected_cpt_attributes == set(self.cpt_tables[index].columns)
        assert expected_path_attribute == set(self.path_attr_tables[index].columns)

        actual_attr_hashes = self.get_table_column_hashes(index)
        for key, value in spec.attributes.items():
            actual_value = actual_attr_hashes[key]
            assert value == actual_value, (key, value, actual_value)

    def verify_path_tables(self, index: int, spec: _CPTSpec):
        geometry = self.path_tables[index]

        assert spec.num_rows == len(geometry)

        sum_distances = geometry["distance"].sum()
        sum_azimuths = geometry["azimuth"].sum()
        sum_dips = geometry["dip"].sum()

        assert math.isclose(sum_distances, spec.sum_distances, rel_tol=1e-5)
        assert math.isclose(sum_azimuths, spec.sum_azimuths, rel_tol=1e-5)
        assert math.isclose(sum_dips, spec.sum_dips, rel_tol=1e-5)

    def verify_bounding_box(self, index: int, spec: _CPTSpec):
        assert spec.bbox == self.bbox

    def verify(self, specs: list[_CPTSpec]):
        expected_attribute_columns = set().union(*[spec.attributes.keys() for spec in specs])
        expected_collar_attributes = set().union(*[spec.collar_attributes.keys() for spec in specs])

        assert expected_collar_attributes == set(self.collar_attributes.columns.tolist())

        for i, spec in enumerate(specs):
            assert spec.hole_id == self.hole_ids[i]

            self.verify_hole_distances(i, spec)
            self.verify_collar_attributes(i, spec)
            self.verify_collar_locations(i, spec)
            self.verify_attributes(i, spec, expected_attribute_columns)
            self.verify_path_tables(i, spec)
            self.verify_bounding_box(i, spec)


def _load_distance_collection(gef_object, data_client):
    if not gef_object.collections:
        return []
    collection = gef_object.collections[0]

    attributes = data_client.load_attributes(collection.distance.attributes)
    distance_table_holes = data_client.load_table(collection.holes).to_pandas()

    gefs = []
    for i in range(len(distance_table_holes)):
        offset = distance_table_holes["offset"].iloc[i]
        count = distance_table_holes["count"].iloc[i]
        hole_attrs = attributes.iloc[offset : offset + count]
        gefs.append(hole_attrs)

    return gefs


def _load_path_geometries(gef_object, data_client):
    path_table = data_client.load_table(gef_object.location.path).to_pandas()
    path_attr_table = data_client.load_attributes(gef_object.location.path.attributes)
    holes_table = data_client.load_table(gef_object.location.holes).to_pandas()

    paths = []
    path_attrs = []

    for i in range(len(holes_table)):
        offset = holes_table["offset"].iloc[i]
        count = holes_table["count"].iloc[i]
        paths.append(path_table.iloc[offset : offset + count])
        path_attrs.append(path_attr_table.iloc[offset : offset + count])

    return paths, path_attrs


def _get_bbox(gef_object):
    bbox_go = gef_object.bounding_box
    return bbox_go.min_x, bbox_go.max_x, bbox_go.min_y, bbox_go.max_y, bbox_go.min_z, bbox_go.max_z


def _check_path_geometry(hole_geometry, sum_distances: float, sum_azimuths: float, sum_dips: float, num_parts: int):
    assert len(hole_geometry) == num_parts
    actual_sum_distances, actual_sum_azimuths, actual_sum_dips = hole_geometry.sum()
    assert math.isclose(sum_distances, actual_sum_distances, rel_tol=1e-5)
    assert math.isclose(sum_azimuths, actual_sum_azimuths, rel_tol=1e-5)
    assert math.isclose(sum_dips, actual_sum_dips, rel_tol=1e-5)


_gef_cpt_spec_1 = _CPTSpec(
    collar_locations=[79578.38, 424838.97, -0.09],
    hole_id="CPTU17.8 + 83BITE",
    hole_distancess={"final": 20.0, "target": 20.0, "current": 20.0},
    num_rows=1004,
    sum_distances=1.006009e04,
    sum_azimuths=3.054131e04,  # derived from inclinationNS and inclinationEW
    sum_dips=1.087333e06,  # derived from inclinationResultant
    attributes={
        # Computed by pygef
        # This is computed from `delivered_vertical_position_offset - depth` (or penetrationLength if depth is abesent)
        "depthOffset": "740260f3a97f5af2269c3f785a1836b2",  # ?
        # This is computed from `localFriction / coneResistance * 100`
        "frictionRatioComputed": "23b3e60ed5c1c9b93399e406f596e37a",  # ?,
        "coneResistance": "5ef0301d72915c9258f2000ff8273fb0",  # 2
        "localFriction": "c98aabdaa48810064f9783c1cea80e9d",  # 3
        "frictionRatio": "9c8c631c5c2275946d6666761aa2f334",  # 4
        "porePressureU2": "053a15c6f83abca0de2e620a9371ba58",  # 6
        "inclinationResultant": "a8974308463a973edb1c1b157d3813c0",  # 8
        "inclinationNS": "e37081d8569d4ff974e430a595b82d3c",  # 9
        "inclinationEW": "24ef1a5c3465ec301978f3242e1cd7ed",  # 10
        "depth": "3a8a1d4f00a3c0c6e8318e7b301e192f",  # 11 - renamed by us from "depth"
        "correctedConeResistance": "86db84f105d3a7b4a807168d7c420867",  # 13

    },
    collar_attributes={
        "research_report_date": [pd.Timestamp("2019-02-13 00:00:00+0000", tz="UTC")],  # FILEDATE
        "delivered_vertical_position_offset": [-0.09],  # ZID
        # This one is always the empty string when parsing GEF
        "cpt_description": [""],
        # MEAUREMENTVAR
        "cone_tip_area": ["1000, mm2, nom. oppervlak conuspunt"],  # 1
        "friction_sleeve_area": ["15000, mm2, oppervlakte kleefmantel"],  # 2
        "cone_tip_area_quotient": ["0.80, -, netto oppervlakte coëfficiënt van de conuspunt"],  # 3
        "friction_sleeve_area_quotient": ["1.0, -, oppervlaktequotiënt kleefmantel"],  # 4
        "cone_friction_distance": ["80, mm, afstand tussen conuspunt en hart kleefmantel"],  # 5
        "ppt_u2_present": ["1, -, Waterspanningsopnemer u2 aanwezig"],  # 8
        "test_type": ["4, -, sondeermethode"],  # 12
        "preexcavated_depth": ["0, m, voorgeboorde/voorgegraven diepte"],  # 13
        "end_depth": ["20.00, m, einddiepte sondering"],  # 16
        "stop_criteria": ["0, -, Stopcriterium: Einddiepte bereikt"],  # 17
        "cone_zero_before": ["-0.257, MPa, Nulpunt conus voor de sondering"],  # 20
        "cone_zero_after": ["-0.245, MPa, Nulpunt conus na de sondering"],  # 21
        "friction_zero_before": ["-0.015, MPa, Nulpunt kleef voor de sondering"],  # 22
        "friction_zero_after": ["-0.016, MPa, Nulpunt kleef na de sondering"],  # 23
        "ppt_u2_zero_before": ["-0.028, MPa, Nulpunt waterspanning voor de sondering"],  # 26
        "ppt_u2_zero_after": ["-0.013, MPa, Nulpunt waterspaning na de sondering"],  # 27
        # MEASUREMENTTEXT
        "cone_type_serial": ["S10-CFIIP.1721, conus type en serienummer"],  # 4
        "probe_mass_geometry": ["Sondeerrups 1; 12400 kg; geen ankers, sondeerequipment"],  # 5
        "applied_standard": ["NEN-EN-ISO22476-1 / klasse 2 / TE2, gehanteerde norm en klasse en type sondering"],  # 6
        "ground_level": ["maaiveld, vast horizontaal vlak"],  # 9
        "interruption_processing": ["nee, bewerking onderbrekingen uitgevoerd"],  # 21
        "zero_drift_correction": ["nee, signaalbewerking uitgevoerd"],  # 20
        "zid_method": ["MRG1, methode verticale positiebepaling"],  # 42
        "xyid_method": ["LRG1, methode locatiebepaling"],  # 43
        # These are part of an extended spec which isn't supported yet
        "measurementtext_101": ["Bronhouder, 52605825, 31"],
        "measurementtext_102": ["opdracht publieke taakuitvoering, kader aanlevering"],
        "measurementtext_103": ["overig onderzoek, kader inwinning"],
        "measurementtext_104": ["uitvoerder locatiebepaling, 24257098, 31"],
        "measurementtext_105": ["2019, 01, 29"],
        "measurementtext_106": ["uitvoerder verticale positiebepaling, 24257098, 31"],
        "measurementtext_107": ["2019, 01, 29"],
        "measurementtext_109": ["nee, dissipatietest uitgevoerd"],
        "measurementtext_110": ["ja, expertcorrectie uitgevoerd"],
        "measurementtext_111": ["nee, aanvullend onderzoek uitgevoerd"],
        "measurementtext_112": ["2019, 01, 31"],
        "measurementtext_113": ["2019, 01, 30"],
        "measurementtext_114": ["2019, 01, 29"],
    },
    bbox=(79578.38, 79578.85203297655, 424838.968697291, 424839.9039877552, -20.094087662485098, -0.09),
)


_gef_cpt_spec_2 = _CPTSpec(
    collar_locations=[116509.0, 469890.0, -1.63],
    hole_id="N04-25",
    hole_distancess={"final": 10.46, "target": 10.46, "current": 10.46},
    # TODO Make sure nothing is wrong here. There are 1039 rows in the source file, but the first bunch is being truncated.
    #  Looking at the imported "distance" column, the distances start at 2.0, which is the same as preexcavated_depth.
    #  Need to confirm that we want to discard these rows.
    num_rows=839,
    sum_distances=5193.41,
    sum_azimuths=199323.939914,
    sum_dips=75114.252900,
    attributes={
        "depthOffset": "ce7e5624d2f4d0d36d2c829d8273e33e",
        "frictionRatioComputed": "38368a44ebb0111c55cf89645196309f",
        "depth": "d7b3fce4f4aaac6062e15e5c4f510098",
        "coneResistance": "35cfc50676c8c84667faa7431c8ef0ba",  # 2
        "localFriction": "9a4b0e7d46ba24e47eece2b21d56fb91",  # 3
        "frictionRatio": "989f5f071c20331b6bb06126939992c8",  # 4
        "inclinationResultant": "5b3ed874c2936e1f750b62a55b68cc13",  # 8
        "inclinationNS": "87d36476d5422514aee6b191b55c0bf2",  # 9
        "inclinationEW": "8ac9f6acf1c60540c04fdf0600dbca83",  # 10
        "elapsedTime": "ec2c330960a006e5a7f5506f05e9b9d1",  # 12
    },
    collar_attributes={
        "research_report_date": [pd.Timestamp("2021-05-03 00:00:00+0000", tz="UTC")],
        "delivered_vertical_position_offset": [-1.63],
        # This one is always the empty string when parsing GEF
        "cpt_description": [""],
        # MEASUREMENTVAR
        "cone_tip_area": ["1000.000000, mm2, Nom. surface area of cone tip"],  # 1
        "friction_sleeve_area": ["15000.000000, mm2, Nom. surface area of friction casing"],  # 2
        "cone_tip_area_quotient": ["0.800000, -, Net surface area quotient of cone tip"],  # 3
        "friction_sleeve_area_quotient": ["1.000000, -, Net surface area quotient of friction casing"],  # 4
        "cone_friction_distance": ["80.000000, mm, Cone distance to centre of friction casing"],  # 5
        "friction_present": ["1.000000, -, Friction present"],  # 6
        "ppt_u2_present": ["1.000000, -, u2 present"],  # 8
        "inclination_present": ["1.000000, -, Inclination measurement present"],  # 10
        "backflow_compensator": ["1.000000, -, Use of back-flow compensator"],  # 11
        "test_type": ["4, -, electrical penetration test"],  # 12
        "preexcavated_depth": ["2.000000, m, Pre-excavated depth"],  # 13
        "groundwater_level": ["0.000000, m, WaterLevel"],  # 14
        "end_depth": ["10.460000, m, Penetration Length"],  # 16
        "stop_criteria": ["0, -, Stop criteria"],  # 17
        "cone_zero_before": ["-0.144303, MPa, Zero measurement cone before penetration test"],  # 20
        "cone_zero_after": ["-0.153163, MPa, Zero measurement cone after penetration test"],  # 21
        "friction_zero_before": ["0.001206, MPa, Zero measurement friction before penetration test"],  # 22
        "friction_zero_after": ["0.000885, MPa, Zero measurement friction after penetration test"],  # 23
        "inclination_ns_zero_before": [
            "0.108046, degrees, Zero measurement inclination NS before penetration test"
        ],  # 32
        "inclination_ns_zero_after": [
            "-0.274309, degrees, Zero measurement inclination NS after penetration test"
        ],  # 33
        "inclination_ew_zero_before": [
            "-0.524360, degrees, Zero measurement inclination EW before penetration test"
        ],  # 34
        "inclination_ew_zero_after": [
            "-0.785091, degrees, Zero measurement inclination EW after penetration test"
        ],  # 35
        # MEASUREMENTTEXT
        "client": ["Waternet, Client"],  # 1
        "project_name": ["Ringdijk 2de bedijking, Name of the project"],  # 2
        "location_name": ["P1011, Location"],  # 3
        "cone_type_serial": ["C10CFIIP.G88, Cone Type"],  # 4
        "probe_mass_geometry": ["Geen verankering, Mass and geometry of probe apparatus"],  # 5
        "applied_standard": ["22476-1 / 2, Test class"],  # 6
        "ground_level": ["Ground level, Fixed horizontal reference level"],  # 9
        "zero_drift_correction": ["Nee, signaalbewerking uitgevoerd"],  # 20
        "interruption_processing": ["Ja, bewerking onderbrekingen uitgevoerd"],  # 21
        "reserved_24": ["V3.54-01, CPTest version used"],  # 24
        "reserved_25": ["1.47, CPTask version used"],  # 25
        "zid_method": ["MRG1, methode verticale positiebepaling"],  # 42
        "xyid_method": ["LRG1, methode locatiebepaling"],  # 43
        "x_axis_orientation": ["ja, orientatie x as helling"],  # 44
        # These are part of an extended spec which isn't supported yet
        "measurementtext_101": ["Waterschap AGV, 34360267"],
        "measurementtext_102": ["opdracht publieke taakuitvoering, kader aanlevering"],
        "measurementtext_103": ["bouwwerk en constructie, kader inwinning"],
        "measurementtext_104": ["Uitvoerder locatiebepaling, 41216593"],
        "measurementtext_105": ["2021, 05, 03"],
        "measurementtext_106": ["Uitvoerder verticale positiebepaling, 41216593"],
        "measurementtext_107": ["2021, 05, 03"],
        "measurementtext_109": ["Nee, dissipatietest uitgevoerd"],
        "measurementtext_110": ["Ja, expertcorrectie uitgevoerd"],
        "measurementtext_111": ["Nee, aanvullend onderzoek uitgevoerd"],
        "measurementtext_112": ["2021, 05, 12"],
        "measurementtext_113": ["2021, 05, 12"],
        "measurementtext_114": ["2021, 05, 03"],
        "measurementtext_115": ["IMBRO, kwaliteitsregime"],
    },
    bbox=(116508.93743771227, 116509.0, 469889.95390897675, 469890.0, -12.009629784247299, -1.63),
)


@pytest.mark.asyncio
async def test_import_gef_1(evo_metadata, data_client):
    context = TestContext(mock_metadata=evo_metadata)

    with _mock_geoscience_objects(context.get_environment()) as mock_client:
        gef_object = await convert_gef(
            filepaths=[GEF1],
            evo_workspace_metadata=evo_metadata,
            epsg_code=32650,
            # publish_objects=False,  # TODO - Review the best way to no-op a publish
        )

    gef_object_dict, *_ = mock_client.objects.values()
    cpt_data = _CPTData.from_gef_dict(gef_object_dict, data_client)

    # TODO - Fix
    cpt_data.verify([_gef_cpt_spec_1])


@pytest.mark.asyncio
async def test_import_gef_2(evo_metadata, data_client):
    context = TestContext(mock_metadata=evo_metadata)

    with _mock_geoscience_objects(context.get_environment()) as mock_client:
        gef_object = await convert_gef(
            filepaths=[GEF2],
            evo_workspace_metadata=evo_metadata,
            epsg_code=32650,
            # publish_objects=False,
        )

    gef_object_dict, *_ = mock_client.objects.values()
    cpt_data = _CPTData.from_gef_dict(gef_object_dict, data_client)

    # TODO - Fix
    cpt_data.verify([_gef_cpt_spec_2])


@pytest.mark.asyncio
async def test_import_multiple_with_different_attributes(evo_metadata, data_client):
    context = TestContext(mock_metadata=evo_metadata)

    with _mock_geoscience_objects(context.get_environment()) as mock_client:
        gef_object = await convert_gef(
            filepaths=[GEF1, GEF2],
            evo_workspace_metadata=evo_metadata,
            epsg_code=32650,
            # publish_objects=False,
        )

    gef_object_dict, *_ = mock_client.objects.values()
    cpt_data = _CPTData.from_gef_dict(gef_object_dict, data_client)

    # TODO - Fix
    cpt_data.verify([_gef_cpt_spec_1, _gef_cpt_spec_2])

    # Spot check that the attributes columns get padded out to null for the GEF data that doesn't have them
    table_1 = cpt_data.cpt_tables[0]
    table_2 = cpt_data.cpt_tables[1]
    # The first table should have "porePressureU2" and "correctedConeResistance", which the second one lacks
    assert not table_1["porePressureU2"].isnull().all()
    assert not table_1["correctedConeResistance"].isnull().all()
    assert table_2["porePressureU2"].isnull().all()
    assert table_2["correctedConeResistance"].isnull().all()

    # Spot check that the collar attributes also get padded to null
    for attr in _gef_cpt_spec_1.collar_attributes.keys() - _gef_cpt_spec_2.collar_attributes.keys():
        assert cpt_data.collar_attributes[attr].iloc[0] is not None
        assert cpt_data.collar_attributes[attr].iloc[1] is None

    for attr in _gef_cpt_spec_2.collar_attributes.keys() - _gef_cpt_spec_1.collar_attributes.keys():
        assert cpt_data.collar_attributes[attr].iloc[0] is None
        assert cpt_data.collar_attributes[attr].iloc[1] is not None


# TODO Fix this
@pytest.mark.skip(reason="GEF-XML import seems to be broken")
def test_import_gef_xml_cpt_multiple(evo_metadata, data_client):
    gef_object = convert_gef(
        filepaths=[GEF_XML_MULTIPLE],
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        publish_objects=False,
    )

    cpt_data = _CPTData.from_gef_object(gef_object, data_client)  # noqa


# TODO - The test code for mocking was mostly copy/pasted. The assumption is that the tests that require them will
#  be moved to evo-python-sdk.

# Copied from evo-objects/tests/typed/helpers.py
class TestContext(IContext):

    def __init__(self, mock_metadata):
        self._mock_metadata: EvoWorkspaceMetadata = mock_metadata

        object_service_client, data_client = create_evo_object_service_and_data_client(
            evo_workspace_metadata=mock_metadata
        )

        self._connector = data_client._connector
        self._cache = data_client._cache

        self._org_id = uuid.uuid4()

    def get_environment(self) -> Environment:
        return Environment(
            hub_url=self._mock_metadata.hub_url,
            org_id=self.get_org_id(),
            workspace_id=UUID(self._mock_metadata.workspace_id),
        )

    def get_org_id(self) -> UUID:
        return self._org_id
        return UUID(self._mock_metadata.org_id)

    def get_connector(self) -> APIConnector:
        return self._connector

    def get_cache(self) -> ICache | None:
        return self._cache


# Copied from evo-objects/tests/typed/helpers.py
class MockDownloadedObject(DownloadedObject):
    def __init__(self, mock_client: MockClient, object_dict: dict, version_id: str = "1"):
        self.mock_client = mock_client
        self.object_dict = object_dict
        self._metadata = Mock()
        self._metadata.schema_id = ObjectSchema.from_id(object_dict["schema"])
        self._metadata.url = ObjectReference.new(
            environment=mock_client.environment,
            object_id=uuid.UUID(object_dict["uuid"]),
        )
        self._metadata.version_id = version_id
        self._metadata.environment = mock_client.environment
        self._metadata.id = uuid.UUID(object_dict["uuid"])
        # Store connector and cache for IContext implementation
        self._connector: APIConnector = Mock(spec=APIConnector)
        self._connector.base_url = mock_client.environment.hub_url
        self._cache: ICache | None = None

    @property
    def metadata(self):
        return self._metadata

    def get_environment(self) -> Environment:
        return self._metadata.environment

    def get_org_id(self) -> uuid.UUID:
        return self._metadata.environment.org_id

    def get_connector(self) -> APIConnector:
        return self._connector

    def get_cache(self) -> ICache | None:
        return self._cache

    def as_dict(self):
        return self.object_dict

    async def download_dataframe(self, data: dict, fb=None, **kwargs) -> pd.DataFrame:
        """Download a DataFrame from a table info dict."""
        return self.mock_client.get_dataframe(data)

    async def download_attribute_dataframe(self, data: dict, fb) -> pd.DataFrame:
        return self.mock_client.get_dataframe(data["values"])

    async def download_array(self, jmespath_expr: str, fb=None):
        """Download an array from the object using a JMESPath expression."""

        from evo import jmespath as jp

        data_info = jp.search(jmespath_expr, self.object_dict)
        if data_info is None:
            raise ValueError(f"No data found at {jmespath_expr}")
        df = self.mock_client.get_dataframe(data_info)
        # Return the first column as a numpy array
        return df.iloc[:, 0].values

    async def update(self, object_dict):
        new_version_id = str(int(self.metadata.version_id) + 1)
        return MockDownloadedObject(self.mock_client, object_dict, new_version_id)


# Mostly copied from evo-python-sdk
class MockClient:
    def __init__(self, environment: Environment):
        self.environment = environment
        self.data = {}
        self.objects = {}
        # self.geo_objects = {}

    def get_dataframe(self, data: dict) -> pd.DataFrame:
        return self.data[data["data"]]

    async def upload_dataframe(self, df: pd.DataFrame, *args, **kwargs) -> dict:
        data_id = str(uuid.uuid4())
        self.data[data_id] = df
        return {"data": data_id, "length": df.shape[0]}

    async def upload_table(self, table, *args, **kwargs) -> dict:
        """Upload a PyArrow table (used for masks and other array data)."""
        data_id = str(uuid.uuid4())
        # Convert PyArrow table to pandas for storage
        self.data[data_id] = table.to_pandas()
        # Return table info with length
        return {"data": data_id, "length": len(table)}

    async def upload_category_dataframe(self, df: pd.DataFrame, *args, **kwargs) -> dict:
        return {
            "values": await self.upload_dataframe(df),
            "category_data": True,
        }

    async def create_geoscience_object(
            self, context: IContext, object_dict: dict, parent: str | None = None, path: str | None = None
    ):
        object_dict = object_dict.copy()
        object_dict["uuid"] = str(uuid.uuid4())
        self.objects[object_dict["uuid"]] = copy.deepcopy(object_dict)
        # self.geo_objects[object_dict["uuid"]] = models.GeoscienceObject.model_validate(object_dict)
        return MockDownloadedObject(self, object_dict)

    async def replace_geoscience_object(
            self, context: IContext, reference: ObjectReference, object_dict: dict, create_if_missing=False
    ):
        object_dict = object_dict.copy()
        assert reference.object_id is not None, "Reference must have an object ID"
        object_dict["uuid"] = str(reference.object_id)
        self.objects[object_dict["uuid"]] = copy.deepcopy(object_dict)
        return MockDownloadedObject(self, object_dict)

    async def from_reference(self, context: IContext, reference: ObjectReference):
        assert reference.object_id is not None, "Reference must have an object ID"
        object_dict = copy.deepcopy(self.objects[str(reference.object_id)])
        return MockDownloadedObject(self, object_dict)


# Inspired by test_pointset.py from evo-python-sdk
@contextlib.contextmanager
def _mock_geoscience_objects(environment):
    mock_client = MockClient(environment)
    with (
        patch("evo.objects.io.ObjectDataUpload.upload_from_cache"),
        patch("evo.objects.typed.base.create_geoscience_object", mock_client.create_geoscience_object),
    ):
        yield mock_client


@pytest.mark.asyncio
async def test_typed_dhc(evo_metadata, data_client):
    hole1 = pd.DataFrame({
        'depth': [1.0, 2, 3, 4, 5, 6],
        'dip': [90.0, 90, 90, 90, 90, 90],
        'azimuth': [0.0, 0, 0, 0, 0, 0],
        'attr1': ["oh", "bye", "oh", "bye",  "oh", "bye",],
    })

    hole2 = pd.DataFrame({
        'depth': [0.0, 1, 2, 3, 4, 5],
        'dip': [90.0, 90, 90, 90, 90, 90],
        'azimuth': [0.0, 0, 0, 0, 0, 0],
        'attr1': ["hi", "okay", "hi", "okay","hi", "okay",],
        'attr2': [1.1, 2.2, 3.3, 4.4, 5.5, 6.6],
    })

    context = TestContext(mock_metadata=evo_metadata)

    with _mock_geoscience_objects(context.get_environment()) as mock_client:
        dhc_data = DownholeCollectionData(
            name="test DHC",
            holes=[
                hole1,
                hole2,
            ],
            properties=pd.DataFrame({
                'id': ['id 1', 'id 2'],
                'x': [0., 1],
                'y': [0., 20],
                'z': [0., 300],
                'final': [1., 4],
                'current': [2., 5],
                'target': [3., 6],
            }),
            attributes=pd.DataFrame({
                'attr1': [1, 2],
                'attr2': [1.1, 2.2],
                'attr3': ["hi", "there"],
            })
        )

        result = await DownholeCollection.create(context, dhc_data)

        gef_object_dict, *_ = mock_client.objects.values()
        cpt_data = _CPTData.from_gef_dict(gef_object_dict, data_client)

        # TODO - temporary
        assert len(cpt_data.cpt_tables) == 0

        # TODO - This is just a spot check. This test might just be temporary anyway.
        assert list(cpt_data.bbox) == [0.0, 1.0, 0.0, 20.0, -6.0, 300.0]
        assert list(cpt_data.geometries[1]["depth"]) == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
