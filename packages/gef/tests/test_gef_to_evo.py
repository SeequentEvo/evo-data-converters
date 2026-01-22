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
import hashlib
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import numpy
import pandas as pd
import pytest
from evo_schemas.objects import DownholeCollection_V1_3_0 as DownholeCollectionGo
from packages.gef.tests.consts import GEF1, GEF2, GEF_XML_MULTIPLE

from evo.data_converters.common import EvoWorkspaceMetadata
from evo.data_converters.common.objects.downhole_collection import DownholeCollection
from evo.data_converters.common.objects.downhole_collection_to_geoscience_object import (
    DownholeCollectionToGeoscienceObject,
)
from evo.data_converters.gef.importer import convert_gef
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


class _CPTData:
    def __init__(self, cpt_tables, collar_attributes, collar_locations, hole_distances, hole_ids, geometries):
        self.cpt_tables = cpt_tables
        self.collar_attributes = collar_attributes
        self.collar_locations = collar_locations
        self.hole_distances = hole_distances
        self.hole_ids = hole_ids
        self.geometries = geometries

    @classmethod
    def from_gef_object(cls, gef_object, data_client):
        attrs = gef_object.location.attributes
        collar_attrs_pd = data_client.load_attributes(attrs)
        collar_locations_pd = data_client.load_table(gef_object.location.coordinates).to_pandas()
        hole_distances = data_client.load_table(gef_object.location.distances).to_pandas()
        hole_ids = data_client.load_category(gef_object.location.hole_id)
        hole_geometries = _load_path_geometries(gef_object, data_client)
        cpt_tables = _load_distance_collection(gef_object, data_client)

        # For GEF imports, the collection is supposed to match up exactly to the geometry definition
        # (gef_object.location).
        assert len(cpt_tables) == len(hole_geometries)
        for cpt_table, hole_geometry in zip(cpt_tables, hole_geometries, strict=True):
            assert len(cpt_table) == len(hole_geometry)

        return cls(
            cpt_tables=cpt_tables,
            collar_attributes=collar_attrs_pd,
            collar_locations=collar_locations_pd,
            hole_distances=hole_distances,
            hole_ids=hole_ids,
            geometries=hole_geometries,
        )

    @property
    def attribute_names(self):
        return self.cpt_tables[0].columns.tolist()

    def get_table_column_hashes(self, index) -> dict[str, str]:
        table = self.cpt_tables[index]
        column_hashes = {}
        for col in table.columns:
            col_hash = hashlib.md5(table[col].values.tobytes()).hexdigest()
            column_hashes[col] = str(col_hash)
        return column_hashes

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
        assert expected_attribute_columns == set(self.cpt_tables[index].columns)
        actual_attr_hashes = self.get_table_column_hashes(index)
        for key, value in spec.attributes.items():
            assert value == actual_attr_hashes[key]

    def verify_geometries(self, index: int, spec: _CPTSpec):
        geometry = self.geometries[index]

        assert spec.num_rows == len(geometry)

        sum_distances = geometry["distance"].sum()
        sum_azimuths = geometry["azimuth"].sum()
        sum_dips = geometry["dip"].sum()

        assert math.isclose(sum_distances, spec.sum_distances, rel_tol=1e-5)
        assert math.isclose(sum_azimuths, spec.sum_azimuths, rel_tol=1e-5)
        assert math.isclose(sum_dips, spec.sum_dips, rel_tol=1e-5)

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
            self.verify_geometries(i, spec)


def _load_distance_collection(gef_object, data_client):
    assert len(gef_object.collections) == 1
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
    holes_table = data_client.load_table(gef_object.location.holes).to_pandas()

    paths = []

    for i in range(len(holes_table)):
        offset = holes_table["offset"].iloc[i]
        count = holes_table["count"].iloc[i]
        paths.append(path_table.iloc[offset : offset + count])

    return paths


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
    sum_azimuths=3.054131e04,
    sum_dips=1.087333e06,
    attributes={
        # Computed by us
        "azimuth": "90e5ed90d6338ce4b03c4c4b542948fc",  # derived from inclinationNS and inclinationEW
        "dip": "98b6273bc30e489e31f78e6a95ce15ff",  # derived from inclinationResultant
        # Computed by pygef
        # This is computed from `delivered_vertical_position_offset - depth` (or penetrationLength if depth is abesent)
        "depthOffset": "740260f3a97f5af2269c3f785a1836b2",  # ?
        # This is computed from `localFriction / coneResistance * 100`
        "frictionRatioComputed": "23b3e60ed5c1c9b93399e406f596e37a",  # ?,
        "coneResistance": "5ef0301d72915c9258f2000ff8273fb0",  # 2
        "localFriction": "c98aabdaa48810064f9783c1cea80e9d",  # 3
        "frictionRatio": "ca1077a8961f7bdfcdc48dad55d3cd4d",  # 4
        "porePressureU2": "053a15c6f83abca0de2e620a9371ba58",  # 6
        "inclinationResultant": "a8974308463a973edb1c1b157d3813c0",  # 8
        "inclinationNS": "e37081d8569d4ff974e430a595b82d3c",  # 9
        "inclinationEW": "24ef1a5c3465ec301978f3242e1cd7ed",  # 10
        "depth": "3a8a1d4f00a3c0c6e8318e7b301e192f",  # 11
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
        "azimuth": "f71bfc1875eec015f8a0c86c886416c9",
        "dip": "ace3becc5897a609d28c7fae101d4672",
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
)


def test_import_gef_1(evo_metadata, data_client):
    gef_object = convert_gef(
        filepaths=[GEF1],
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        publish_objects=False,
    )

    cpt_data = _CPTData.from_gef_object(gef_object, data_client)
    cpt_data.verify([_gef_cpt_spec_1])


def test_import_gef_2(evo_metadata, data_client):
    gef_object = convert_gef(
        filepaths=[GEF2],
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        publish_objects=False,
    )
    cpt_data = _CPTData.from_gef_object(gef_object, data_client)
    cpt_data.verify([_gef_cpt_spec_2])


def test_import_multiple_with_different_attributes(evo_metadata, data_client):
    gef_object = convert_gef(
        filepaths=[GEF1, GEF2],
        evo_workspace_metadata=evo_metadata,
        epsg_code=32650,
        publish_objects=False,
    )
    cpt_data = _CPTData.from_gef_object(gef_object, data_client)
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

