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

import dataclasses
import math
import os
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from pygef.cpt import CPTData
from pygef.common import Location as PyGEFoLcation, VerticalDatumClass
import pytest

from evo.data_converters.common.crs import UNSPECIFIED
from evo.data_converters.gef.common_gef import ParsedCptFile, CPTSource
from evo.data_converters.gef.converter.gef_spec import CAMEL_TO_SNAKE
from evo.data_converters.gef.converter.gef_to_downhole_collection import process_cpt_file, build_downhole_collection
from evo.data_converters.gef.objects import DownholeCollectionData


CRS1 = "EPSG:28992"
CRS2 = "EPSG:4326"


_OUT_OF_BOUNDS_NAME_TO_INDEX = {
    "_-1": -1,
    "_0": 0,
    "_9999": 9999,
}

# The "index" is a numerical identifier for this data as it appears in the GEF spec
MTEXT_NAME_TO_INDEX = {
    "cone_type_serial": 4,
    "ground_level": 9,
    "reserved_13": 13,
}
MTEXT_NAME_TO_INDEX.update(_OUT_OF_BOUNDS_NAME_TO_INDEX)


@dataclasses.dataclass
class MVarHeader:
    index: int
    unit: str
    desc: str


class MTextRow:
    def __init__(self, row: dict[str, Any]):
        self.row = row

    def get(self) -> list[list[str]]:
        # The format as presented by pygef (which we are mocking) will look like
        # index, ------------- values ----------------, label
        # ['5', 'Sondeerrups 1; 12400 kg; geen ankers', 'sondeerequipment']
        # And the original cpt looks like: #MEASUREMENTTEXT= 5, Sondeerrups 1; 12400 kg; geen ankers, sondeerequipment
        return [[MTEXT_NAME_TO_INDEX[x], v, x] for x, v in self.row.items()]

    def expected(self) -> dict[str, str]:
        return {x: f"{value}, {x}" for x, value in self.row.items()}

    def with_columns(self, columns: list[str] | None = None):
        if columns is None:
            return self
        return MTextRow({k: v for k, v in self.row.items() if k in columns})



MEASUREMENT_TEXT_ROWS = [
    MTextRow({"cone_type_serial": "serial1", "ground_level": "ground1", "reserved_13": "reserved1"}),
    MTextRow({"cone_type_serial": "serial2", "ground_level": "ground2", "reserved_13": "reserved2"}),
    MTextRow({"cone_type_serial": "serial3", "ground_level": "ground3", "reserved_13": "reserved3"}),
    MTextRow({"cone_type_serial": "serial4", "ground_level": "ground4", "reserved_13": "reserved4"}),
    MTextRow({"cone_type_serial": "serial5", "ground_level": "ground5", "reserved_13": "reserved5"}),
]


# The "index" is a numerical identifier for this data as it appears in the GEF spec
MVAR_NAME_TO_INDEX = {
    "cone_tip_area": 1,
    "test_type": 12,
    "cone_zero_before": 20,
}
MVAR_NAME_TO_INDEX.update(_OUT_OF_BOUNDS_NAME_TO_INDEX)
MVAR_INDEX_TO_NAME = dict(zip(MVAR_NAME_TO_INDEX.values(), MVAR_NAME_TO_INDEX.keys()))



class MVarRow:
    def __init__(self, row: dict[str, tuple[Any, str]]):
        self.row = row
    def get(self) -> list[list[str]]:
        # The format as presented by pygef (which we are mocking) will look like
        # index, value, unit, label
        # ['1', '1000', 'mm2', 'nom. oppervlak conuspunt']
        # #MEASUREMENTVAR= 1, 1000, mm2, nom. oppervlak conuspunt
        return [[MVAR_NAME_TO_INDEX[x], v, u, x] for x, (v, u) in self.row.items()]

    def expected(self) -> dict[str, str]:
        return {x: f"{value}, {unit}, {x}" for x, (value, unit) in self.row.items()}

    def with_columns(self, columns: list[str] | None = None):
        if columns is None:
            return self
        return MTextRow({k: v for k, v in self.row.items() if k in columns})



MEASUREMENT_VAR_ROWS = [
    MVarRow({"cone_tip_area": ("1000", "mm2"), "test_type": ("1", "-"), "cone_zero_before": ("-0.2", "MPa")}),
    MVarRow({"cone_tip_area": ("1100", "mm2"), "test_type": ("2", "-"), "cone_zero_before": ("-0.2", "MPa")}),
    MVarRow({"cone_tip_area": ("1200", "mm2"), "test_type": ("3", "-"), "cone_zero_before": ("-0.2", "MPa")}),
    MVarRow({"cone_tip_area": ("1300", "mm2"), "test_type": ("4", "-"), "cone_zero_before": ("-0.2", "MPa")}),
    MVarRow({"cone_tip_area": ("1400", "mm2"), "test_type": ("5", "-"), "cone_zero_before": ("-0.2", "MPa")}),
]


def _build_expected_attributes():
    attrs = {}

    for mtext_row in MEASUREMENT_TEXT_ROWS:
        for field, value in mtext_row.row.items():
            expected_entry = f'{value}, {field}'
            attrs.setdefault(field, []).append(expected_entry)

    for mvar_row in MEASUREMENT_VAR_ROWS:
        for field, (value, unit) in mvar_row.row.items():
            expected_entry = f'{value}, {unit}, {field}'
            attrs.setdefault(field, []).append(expected_entry)

    return attrs


EXPECTED_ATTRIBUTES = _build_expected_attributes()


def _build_raw_headers(mtext: MTextRow, mvar: MVarRow, project_id: str | None = None):
    headers = {
        "MEASUREMENTTEXT": mtext.get(),
        "MEASUREMENTVAR": mvar.get(),
    }
    if project_id is not None:
        headers["PROJECTID"] = [[project_id]]

    return headers


def _make_raw_headers(row: int, text_cols: list[str] | None = None, var_cols: list[str] | None = None, project_id: str | None = None) -> dict:
    m_txt_row = MEASUREMENT_TEXT_ROWS[row].with_columns(text_cols)
    m_var_row = MEASUREMENT_VAR_ROWS[row].with_columns(var_cols)

    return _build_raw_headers(m_txt_row, m_var_row, project_id=project_id)


PENETRATION_LENGTH = [x * .1 for x in range(100)]
NEG_90_to_POS_90 =[x * 180/99 - 90 for x in range(100)]
CONE_RESISTANCE = [x / 10 - 5 for x in PENETRATION_LENGTH]
LOCAL_FRICTION = [x + 20 for x in CONE_RESISTANCE]
RANGE = list([float(x) for x in range(100)])
SOIL_DENSITY = [math.cos(x) for x in range(100)]


SNAKE_TO_CAMEL = {v: k for k, v in CAMEL_TO_SNAKE.items()}


class MeasurementsColumn:
    str_lookup: dict[str, MeasurementsColumn] = {}

    def __new__(cls, name, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        cls.str_lookup[name] = obj
        cls.str_lookup[SNAKE_TO_CAMEL.get(name, name)] = obj
        return obj

    def __init__(self, name: str):
        self.name = name

    @property
    def as_snake(self):
        return self.name

    @property
    def as_camel(self):
        return SNAKE_TO_CAMEL.get(self.name, self.name)

    @classmethod
    def from_strs(cls, strs: list[str]):
        return [cls.str_lookup[s] for s in strs]

    def __repr__(self):
        return self.as_snake


inclination_ns = MeasurementsColumn("inclination_ns")
inclination_ew = MeasurementsColumn("inclination_ew")
inclination_resultant = MeasurementsColumn("inclination_resultant")
depth = MeasurementsColumn("depth")
cone_resistance = MeasurementsColumn("cone_resistance")
local_friction = MeasurementsColumn("local_friction")
friction_ratio_computed = MeasurementsColumn("friction_ratio_computed")
soil_density = MeasurementsColumn("soil_density")
elapsed_time = MeasurementsColumn("elapsed_time")
dip = MeasurementsColumn("dip")
azimuth = MeasurementsColumn("azimuth")
depth_offset = MeasurementsColumn("depth_offset")
_unknown = MeasurementsColumn("_unknown")


# Input table, as it appears in pygef's CPTData. Note the camel case.
DEFAULT_TABLE = pl.DataFrame({
    'penetrationLength': PENETRATION_LENGTH,  # Will be converted to "distance"
    # Path columns
    'inclinationNS': NEG_90_to_POS_90,
    'inclinationEW': [90 * math.sin(x) for x in RANGE],
    'inclinationResultant': NEG_90_to_POS_90,
    "depth": PENETRATION_LENGTH,
    # Collection columns
    'coneResistance': CONE_RESISTANCE,
    "localFriction": LOCAL_FRICTION,
    "soilDensity": SOIL_DENSITY,
    # Unknown column
    "_unknown": RANGE,
})

COLUMN_RENAMES = {"penetrationLength": "distance"}
COLLECTION_COLUMNS = [cone_resistance, local_friction, soil_density]

PATH_COLUMNS: list[MeasurementsColumn] = [
    elapsed_time,
    inclination_ew,
    inclination_ns,
    inclination_resultant,
    depth,
    # Calculated by us
    dip,
    azimuth,
    # Can be calculated by pygef after CPTData construction
    depth_offset,
]


UNIT_CONVERSIONS = {
    # pygef is KN/m3, but evo is N/m3
    "soilDensity": 1000,
}


def _make_pygef_cpt_table(rows: list[int] = None, columns: list[MeasurementsColumn] = None) -> pl.DataFrame:
    if rows is None:
        rows = list(range(100))
    if columns is None:
        column_strs = DEFAULT_TABLE.columns
    else:
        column_strs = [col.as_camel for col in columns]
    if "penetrationLength" not in column_strs:
        column_strs = ['penetrationLength'] + column_strs
    return DEFAULT_TABLE.select(column_strs)[rows]


EVEN_ROWS = [x * 2 for x in range(50)]
ODD_ROWS = [1 + x for x in EVEN_ROWS]
EVERY_THREE_MOD_0 = [x * 3 for x in range(33)]
EVERY_THREE_MOD_1 = [x + 1 for x in EVERY_THREE_MOD_0 if x < 100]
EVERY_THREE_MOD_2 = [x + 2 for x in EVERY_THREE_MOD_0 if x < 100]

_default_pygef_cpt = {
    "alias": None,  # GEF
    "bro_id": None,  # BRO-XML
    "cpt_standard": None,
    "standardized_location": None,
    "dissipationtest_performed": None,
    "quality_class": None,
    "predrilled_depth": 2.0,
    "final_depth": 10.0,
    "groundwater_level": None,
    "cpt_description": None,
    "cpt_type": 4.0,
    "cone_surface_area": 1000.0,  # TODO - It looks like this isn't getting included in the DHC
    "cone_diameter": None,
    "cone_surface_quotient": None,
    "cone_to_friction_sleeve_distance": None,
    "cone_to_friction_sleeve_surface_area": None,
    "cone_to_friction_sleeve_surface_quotient": None,
    "zlm_cone_resistance_before": -.1,
    "zlm_cone_resistance_after": -.2,
    "zlm_inclination_ew_before":  None,
    "zlm_inclination_ew_after":  None,
    "zlm_inclination_ns_before":  None,
    "zlm_inclination_ns_after":  None,
    "zlm_inclination_resultant_before":  None,
    "zlm_inclination_resultant_after":  None,
    "zlm_local_friction_before":  None,
    "zlm_local_friction_after":  None,
    "zlm_pore_pressure_u1_before":  None,
    "zlm_pore_pressure_u2_before":  None,
    "zlm_pore_pressure_u3_before":  None,
    "zlm_pore_pressure_u1_after":  None,
    "zlm_pore_pressure_u2_after":  None,
    "zlm_pore_pressure_u3_after":  None,
    "delivered_vertical_position_offset": 1.0,
    "delivered_vertical_position_reference_point": "unknown",
    "delivered_vertical_position_datum": VerticalDatumClass.Unknown,
    "column_void_mapping": None,

    # REQUIRED TO BE PASSED
    # data
    # raw_headers
    # alias or bro_id
    # research_report_depth
    # delivered_location
}


def _make_pygef_data(**kwargs) -> CPTData:
    return CPTData(**kwargs)


@dataclasses.dataclass
class TestCPT:
    filename: str
    table_rows: list[int]
    hole_index: int

    location: PyGEFoLcation

    project_id: str= "project id 1"

    research_report_date: date = date(2000, 1, 1)

    # One of these
    table_columns: list[MeasurementsColumn] = None

    # One of these
    hole_attrs: list[str] = None
    hole_attrs_excluded: list[str] = None
    extra_hole_attrs: dict[str, Any] = None

    extra_args: dict = None

    def with_table_columns(self, columns: list[MeasurementsColumn]):
        self.table_columns = columns
        return self

    def with_excluded_table_columns(self, columns: list[MeasurementsColumn] | MeasurementsColumn):
        columns = columns if isinstance(columns, list) else [columns]
        self.table_columns = [col for col in self._get_table_columns_used() if col not in columns]
        return self

    def get_hole_attrs_used(self) -> list[str]:
        if self.hole_attrs is not None:
            return self.hole_attrs
        base_hole_attrs = ["cone_type_serial", "ground_level", "reserved_13", "cone_tip_area", "test_type", "cone_zero_before"]  # TODO avoid hardcode?
        return base_hole_attrs  # TODO - Handle other test configs

    def _get_table_columns_used(self) -> list[MeasurementsColumn]:
        if self.table_columns is not None:
            return self.table_columns
        column_strs = [col for col in DEFAULT_TABLE.columns if col != "penetrationLength"]
        base_table_columns = MeasurementsColumn.from_strs(column_strs)
        return base_table_columns  # TODO - Handle other test configs

    def _get_path_table_columns_used(self) -> list[MeasurementsColumn]:
        all_columns = self._get_table_columns_used()
        return [col for col in all_columns if col in PATH_COLUMNS]

    def _get_collection_table_columns_used(self) -> list[MeasurementsColumn]:
        all_columns = self._get_table_columns_used()
        return [col for col in all_columns if col in COLLECTION_COLUMNS]

    def _get_location(self) -> PyGEFoLcation:
        # TODO - incorporate standardised location
        return self.location

    def _get_expected_attr(self, attr: str):
        return self._get_pygef_args()[attr]

    def _get_pygef_args(self):
        if hasattr(self, "_pygef_args"):
            return self._pygef_args

        raw_headers = _make_raw_headers(self.hole_index, project_id=self.project_id)

        kwargs = _default_pygef_cpt.copy()
        kwargs.update({
            "data": _make_pygef_cpt_table(rows=self.table_rows, columns=self.table_columns),
            "raw_headers": raw_headers,
            "research_report_date": self.research_report_date,
            "delivered_location": self.location,
        })
        source_type = CPTSource.infer_from_filename(self.filename)
        if source_type == CPTSource.GEF:
            kwargs["alias"] = self.name
        else:
            kwargs["bro_id"] = self.name

        kwargs.update(self.extra_args or {})

        self._pygef_args = kwargs
        return self._pygef_args

    @property
    def name(self) -> str:
        return os.path.basename(self.filename)

    @property
    def hole_id(self):
        return f"hole {self.hole_index}"

    def build_parsed_cpt(self, **kwargs) -> ParsedCptFile:
        pygef_kwargs = self._get_pygef_args()
        pygef_kwargs.update(kwargs)
        gef_cpt = _make_pygef_data(**pygef_kwargs)
        return ParsedCptFile(self.filename, self.hole_id, gef_cpt)

    def _check_attributes(self, attrs: pd.DataFrame):
        assert attrs["project_id"] == self.project_id
        assert attrs["research_report_date"] == self.research_report_date
        expected_fields = self.get_hole_attrs_used()
        mtext_row = MEASUREMENT_TEXT_ROWS[self.hole_index]
        for field, expected_value in mtext_row.expected().items():
            if field in expected_fields:
                assert attrs[field] == expected_value
        mvar_row = MEASUREMENT_VAR_ROWS[self.hole_index]
        for field, expected_value in mvar_row.expected().items():
            if field in expected_fields:
                assert attrs[field] == expected_value

    def _check_properties(self, props: pd.Series):
        location = self._get_location()
        assert props["hole_id"] == self.hole_id
        assert props["x"] == location.x
        assert props["y"] == location.y
        assert props["z"] == self._get_expected_attr("delivered_vertical_position_offset")
        assert props["final"] == props["current"] == props["target"] == self._get_expected_attr("final_depth")

    def _check_path(self, path: pd.Series):
        path_columns = self._get_path_table_columns_used()
        for col in path_columns:
            expected_col = DEFAULT_TABLE[col.as_camel][self.table_rows]
            actual_col = path[col.as_snake]
            assert np.array_equal(actual_col, expected_col)
        assert np.array_equal(path["distance"], DEFAULT_TABLE["penetrationLength"][self.table_rows])

    def _check_collections(self, collection: pd.DataFrame):
        collection_columns = self._get_collection_table_columns_used()
        for col in collection_columns:
            expected_col = DEFAULT_TABLE[col.as_camel][self.table_rows]
            actual_col = collection[col.as_snake]
            if col.as_camel in UNIT_CONVERSIONS:
                expected_col *= UNIT_CONVERSIONS[col.as_camel]
            assert np.array_equal(actual_col, expected_col)
        assert np.array_equal(collection["distance"], DEFAULT_TABLE["penetrationLength"][self.table_rows])

    def check_dhc(self, dhc: DownholeCollectionData):
        assert dhc.name == f"GEF CPT hole {self.hole_index}"
        self.check(collar_attributes=dhc.attributes.iloc[0], collar_properties=dhc.properties.iloc[0], path=dhc.path, collection=dhc.collections[0].distance_table, crs=dhc.coordinate_reference_system)

    def check(self, collar_attributes: pd.Series, collar_properties: pd.Series, path: pd.DataFrame, collection: pd.DataFrame, crs):
        # Assume its an EPSG
        assert crs.epsg_code == int(self.location.srs_name.split(":")[1])

        self._check_properties(collar_properties)
        self._check_attributes(collar_attributes)
        self._check_path(path)
        self._check_collections(collection)


def check_dhc(dhc: DownholeCollectionData, test_cpts: list[TestCPT]):
    assert len(dhc.holes) == len(dhc.collections[0].holes), "For GEF import, the path and collection should correspond"
    for i in range(len(dhc.holes)):
        path_offset = dhc.holes["offset"].iloc[i]
        path_count = dhc.holes["count"].iloc[i]
        path = dhc.path[path_offset: path_offset + path_count]

        coll_offset = dhc.collections[0].holes["offset"].iloc[i]
        coll_count = dhc.collections[0].holes["count"].iloc[i]
        collection = dhc.collections[0].distance_table[coll_offset: coll_offset + coll_count]
        assert len(path) == len(collection), f"For GEF import, the path and collection should correspond, hole {i}"

        collar_attributes = dhc.attributes.iloc[i]
        collar_properties = dhc.properties.iloc[i]
        crs = dhc.coordinate_reference_system

        test_cpts[i].check(
            collar_properties=collar_properties,
            collar_attributes=collar_attributes,
            path=path,
            collection=collection,
            crs=crs,
        )


@pytest.fixture
def test_cpt1() -> TestCPT:
    return TestCPT(
        filename="cpt1.gef",
        table_rows=EVEN_ROWS,
        hole_index=0,
        location=PyGEFoLcation(srs_name=CRS1, x=1000, y=-2000),
    )


@pytest.fixture
def test_cpt2() -> TestCPT:
    return TestCPT(
        filename="cpt2.gef",
        table_rows=ODD_ROWS,
        hole_index=1,
        location=PyGEFoLcation(srs_name=CRS1, x=2000, y=-2000),
    )


@pytest.fixture
def test_cpt3() -> TestCPT:
    return TestCPT(
        filename="cpt1.gef",
        table_rows=EVERY_THREE_MOD_0,
        hole_index=2,
        location=PyGEFoLcation(srs_name=CRS1, x=3000, y=-2000),
    )


@pytest.fixture
def test_cpt4() -> TestCPT:
    return TestCPT(
        filename="cpt1.gef",
        table_rows=EVERY_THREE_MOD_1,
        hole_index=3,
        location=PyGEFoLcation(srs_name=CRS1, x=4000, y=-2000),
    )


@pytest.fixture
def test_cpt5() -> TestCPT:
    return TestCPT(
        filename="cpt5.gef",
        table_rows=EVERY_THREE_MOD_2,
        hole_index=4,
        location=PyGEFoLcation(srs_name=CRS1, x=5000, y=-2000),
    )


@pytest.fixture
def cpt(test_cpt1) -> ParsedCptFile:
    return test_cpt1.build_parsed_cpt()


def _process_cpt(cpt: ParsedCptFile | list[ParsedCptFile]) -> DownholeCollectionData:
    cpts = cpt if isinstance(cpt, list) else [cpt]
    processed = [process_cpt_file(c) for c in cpts]
    return build_downhole_collection(processed)


class TestProcessCptFile:
    def test_happy_path_process_one(self, test_cpt1):
        cpt = test_cpt1.build_parsed_cpt()
        dhc = _process_cpt(cpt)
        test_cpt1.check_dhc(dhc)

    def test_no_parsed_files_raises(self):
        with pytest.raises(ValueError, match="No CPT"):
            _process_cpt([])

    def test_multiple_gefs(self, test_cpt1, test_cpt2, test_cpt3, test_cpt4, test_cpt5):
        cpt1 = test_cpt1.build_parsed_cpt()
        cpt2 = test_cpt2.build_parsed_cpt()
        cpt3 = test_cpt3.build_parsed_cpt()
        cpt4 = test_cpt4.build_parsed_cpt()
        cpt5 = test_cpt5.build_parsed_cpt()

        dhc = _process_cpt([cpt1, cpt2, cpt3, cpt4, cpt5])

        check_dhc(dhc, [test_cpt1, test_cpt2, test_cpt3, test_cpt4, test_cpt5])

        assert dhc.name == 'GEF CPT 5 holes hole 0...hole 4'

    @staticmethod
    def _remove_from_raw_headers(headers, to_remove: dict[str, list[str]]):
        for k, removals in to_remove.items():
            sub_headers = headers[k]
            for item_to_remove in removals:
                sub_headers = [h_parts for h_parts in sub_headers if item_to_remove != h_parts[-1]]
            headers[k] = sub_headers

    def test_two_gefs_with_differing_attributes(self, test_cpt1, test_cpt2):
        original_attribute_columns: list[str] = test_cpt1.get_hole_attrs_used()
        
        cpt1 = test_cpt1.build_parsed_cpt()
        cpt2 = test_cpt2.build_parsed_cpt()

        # The two test CPTs start with the same attributes. Remove different attributes from each one.
        self._remove_from_raw_headers(cpt1.data.raw_headers, {"MEASUREMENTTEXT": ["cone_type_serial"]})
        self._remove_from_raw_headers(cpt2.data.raw_headers, {"MEASUREMENTVAR": ["cone_zero_before"]})

        dhc = _process_cpt([cpt1, cpt2])

        # The table has the full set of attributes
        assert set(original_attribute_columns) < set(dhc.attributes)

        # Rows whose source was missing attributes are filled with NA
        assert pd.isna(dhc.attributes.iloc[0]["cone_type_serial"])
        assert dhc.attributes.drop(columns="cone_type_serial").iloc[0].notna().all()
        assert pd.isna(dhc.attributes.iloc[1]["cone_zero_before"])
        assert dhc.attributes.drop(columns="cone_zero_before").iloc[1].notna().all()

    def test_to_gefs_with_differing_collection_measurements(self, test_cpt1, test_cpt2):
        cpt1 = test_cpt1.with_excluded_table_columns(cone_resistance).build_parsed_cpt()
        cpt2 = test_cpt2.with_excluded_table_columns(soil_density).build_parsed_cpt()

        dhc = _process_cpt([cpt1, cpt2])

        table_first_section = dhc.collections[0].distance_table[:len(EVEN_ROWS)]
        table_second_section = dhc.collections[0].distance_table[len(EVEN_ROWS):]

        assert table_first_section["cone_resistance"].isna().all()
        assert table_first_section["friction_ratio_computed"].isna().all()  # Derived from cone_resistance
        assert table_first_section.drop(columns=["cone_resistance", "friction_ratio_computed"]).notna().all().all()

        assert table_second_section["soil_density"].isna().all()
        assert table_second_section.drop(columns=["soil_density"]).notna().all().all()


class TestCRS:
    @pytest.mark.parametrize("valid_crs,expected", [
        ("EPSG:28992", 28992),  # Short format
        ("urn:ogc:def:crs:EPSG::4326", 4326),  # urn format
        ("4326", 4326),
    ])
    def test_valid_epsg_formats(self, cpt, valid_crs: str, expected: int):
        cpt.data.delivered_location.srs_name = valid_crs
        dhc = _process_cpt(cpt)
        assert dhc.coordinate_reference_system.epsg_code == expected

    def test_inconsistent_epsg_picks_first_one(self, test_cpt1):
        cpt1 = test_cpt1.build_parsed_cpt()
        cpt1.data.delivered_location.srs_name = "EPSG:4326"
        cpt2 = test_cpt1.build_parsed_cpt()

        dhc = _process_cpt([cpt1, cpt2])
        assert dhc.coordinate_reference_system.epsg_code == 4326

    @pytest.mark.parametrize("invalid_crs", ["", "blah", "123", ":", "EPSG:", ":4326"])
    def test_build_without_epsg_raises_error(self, cpt, invalid_crs: str):
        cpt.data.delivered_location.srs_name = invalid_crs
        dhc = _process_cpt(cpt)
        assert dhc.coordinate_reference_system == UNSPECIFIED

    def test_epsg_404000_treated_as_unspecified(self, cpt):
        cpt.data.delivered_location.srs_name = "urn:ogc:def:crs:EPSG::404000"
        dhc = _process_cpt(cpt)
        assert dhc.coordinate_reference_system == UNSPECIFIED


class TestCalculateFinalDepth:
    def test_calculates_from_penetration_length(self, test_cpt1):
        cpt = test_cpt1.build_parsed_cpt(final_depth=0.0)
        dhc = _process_cpt(cpt)
        expected = dhc.path["distance"].iloc[-1]
        # final, target, and current are all calculated
        assert (dhc.properties[["final", "target", "current"]] == expected).all().all()

    def test_negative_final_depth_is_used(self, test_cpt1):
        cpt = test_cpt1.build_parsed_cpt(final_depth=-1.0)
        dhc = _process_cpt(cpt)
        assert (dhc.properties[["final", "target", "current"]] == -1.0).all().all()


class TestCollarAttributes:
    def test_gathers_only_whitelisted_attributes(self, cpt):
        dhc = _process_cpt(cpt)
        attr_columns = dhc.attributes.columns


        # These are valid attributes on the cpt_data returned by pygef
        assert "data" not in attr_columns
        assert "column_void_mapping" not in attr_columns
        assert "raw_headers" not in attr_columns

        # These were added ad hoc to `mock_cpt_data`, and aren't known to the cpt processing code
        assert "engineer" not in attr_columns
        assert "wind_speed" not in attr_columns

        # These are valid attributes
        assert dhc.attributes["research_report_date"].iloc[0] == cpt.data.research_report_date
        # TODO - Are there other attributes that come directly from CPTData?

    def test_includes_unmapped_raw_headers(self, test_cpt1):
        mtext_row = MTextRow({"_-1": "negative", "_0": "zero", "_9999": "big"})
        mvar_row = MVarRow({"_-1": (-1.0, "-"), "_0": (0.0, "-"), "_9999": (9999.0, "-")})
        header_data = _build_raw_headers(mtext_row, mvar_row)

        cpt = test_cpt1.build_parsed_cpt(raw_headers=header_data)

        dhc = _process_cpt(cpt)
        attrs = dhc.attributes.iloc[0]
        assert attrs["measurementtext_-1"] == "negative, _-1"
        assert attrs["measurementtext_0"] == "zero, _0"
        assert attrs["measurementtext_9999"] == "big, _9999"
        # TODO - It doesn't really make sense how the vars are processed. They should be numeric with units.
        assert attrs["measurementvar_-1"] == "-1.0, -, _-1"
        assert attrs["measurementvar_0"] == "0.0, -, _0"
        assert attrs["measurementvar_9999"] == "9999.0, -, _9999"

    def test_missing_project_id_is_okay(self, cpt):
        cpt.data.raw_headers.pop("PROJECTID")
        dhc = _process_cpt(cpt)
        assert dhc.attributes.iloc[0]["project_id"] == ""


class TestCollarProperties:
    def test_dtypes(self, cpt):
        dhc = _process_cpt(cpt)
        assert dhc.properties["hole_id"].dtype == pd.StringDtype()
        for col in dhc.properties:
            if col == "hole_id":
                continue
            assert dhc.properties[col].dtype == np.float64


class TestCollections:
    def test_table_data_gets_split_between_path_and_collections_and_īncluding_unknown(self, cpt):
        dhc = _process_cpt(cpt)

        path_cols = dhc.path.columns
        coll_cols = dhc.collections[0].distance_table.columns

        # "penetrationLength" has been converted to "distance", which appears in both tables
        assert "penetrationLength" not in path_cols
        assert "penetration_length" not in path_cols
        assert "penetrationLength" not in coll_cols
        assert "penetration_length" not in coll_cols
        assert np.array_equal(dhc.path["distance"] , DEFAULT_TABLE["penetrationLength"][EVEN_ROWS])
        assert np.array_equal(dhc.collections[0].distance_table["distance"], DEFAULT_TABLE["penetrationLength"][EVEN_ROWS])

        # Check other path columns
        other_path_cols = MeasurementsColumn.from_strs([col for col in path_cols if col != "distance"])
        assert set(other_path_cols) < set(PATH_COLUMNS)

        # Check other collection columns
        assert "cone_resistance" in coll_cols
        assert "local_friction" in coll_cols

    def test_we_include_friction_ratio_computed(self, test_cpt1):
        test_cpt1.with_table_columns([cone_resistance, local_friction])
        cpt = test_cpt1.build_parsed_cpt()
        dhc = _process_cpt(cpt)
        assert "friction_ratio_computed" in dhc.collections[0].distance_table.columns

    def test_dtypes(self, cpt):
        """The measurement table should consistent of floats, because they are measurements"""
        dhc = _process_cpt(cpt)
        coll_table = dhc.collections[0].distance_table
        for col in coll_table.columns:
            assert coll_table[col].dtype == np.float64


class TestPath:
    @pytest.mark.parametrize("columns, expected_dip_calculated", [
        ([], False),
        ([inclination_resultant], True),
    ])
    def test_calculates_dip_when_inclination_resultant_present(self, test_cpt1, columns, expected_dip_calculated):
        cpt = test_cpt1.with_table_columns(columns).build_parsed_cpt()
        dhc = _process_cpt(cpt)

        if not expected_dip_calculated:
            assert (dhc.path["dip"] == 90.0).all()
            return

        # Dip has been calculated
        expected_dip = 90 - dhc.path["inclination_resultant"]
        assert np.array_equal(expected_dip, dhc.path["dip"])

    @pytest.mark.parametrize("columns, expected_az_calculated", [
        ([inclination_ew], False),
        ([inclination_ns], False),
        ([inclination_ew, inclination_ns], True),
    ])
    def test_calculates_azimuth_if_both_inclination_ns_and_ew_are_present(self, test_cpt1, columns, expected_az_calculated):
        cpt = test_cpt1.with_table_columns(columns).build_parsed_cpt()
        dhc = _process_cpt(cpt)
        if not expected_az_calculated:
            assert (dhc.path["azimuth"] == 0.0).all()
            return
        ew = dhc.path["inclination_ew"]
        ns = dhc.path["inclination_ns"]
        expected_az = (np.degrees(np.arctan2(ew, ns)) + 360) % 360
        assert np.array_equal(dhc.path["azimuth"], expected_az)

    def test_dtypes(self, cpt):
        """All path attributes should be float"""
        dhc = _process_cpt(cpt)
        for col in dhc.path.columns:
            assert dhc.path[col].dtype == np.float64


class TestApplyMeasurementUnits:
    def test_units(self, cpt):
        processed = process_cpt_file(cpt)

        # Pint types
        assert processed.cpt_table["penetration_length"].dtype.units == "meter"
        assert processed.cpt_table["cone_resistance"].dtype.units == "megapascal"
        assert processed.cpt_table["local_friction"].dtype.units == "megapascal"
        assert processed.cpt_table["soil_density"].dtype.units == "newton / meter ** 3"
        # Not a pint type
        assert processed.cpt_table["friction_ratio_computed"].dtype == np.float64

        dhc = build_downhole_collection([processed])

        # Checking the units as they get sent to Evo
        path_descs = dhc.path.attrs["attribute_descriptions"]
        assert path_descs["distance"].unit.value == "m"
        coll_descs = dhc.collections[0].distance_table.attrs["attribute_descriptions"]
        assert coll_descs["cone_resistance"].unit.value == "MPa"
        assert coll_descs["local_friction"].unit.value == "MPa"
        assert coll_descs["soil_density"].unit.value == "N/m3"
        assert "friction_ratio_computed" not in coll_descs


class TestNanHandling:
    def test_nan(self, test_cpt1):
        nan_mapping = {
            "coneResistance": 2222.22,
            "inclinationEW": 3333.33,
            "inclinationNS": 4444.44,
            "inclinationResultant": 5555.55,
        }
        data_table = DEFAULT_TABLE[["penetrationLength"] + list(nan_mapping.keys())]
        for col in nan_mapping.keys():
            xs = data_table[col].to_list()
            xs[1:1 + len(nan_mapping)] = list(nan_mapping.values())
            data_table = data_table.with_columns(pl.Series(col, xs))

        cpt = test_cpt1.build_parsed_cpt(column_void_mapping=nan_mapping, data=data_table)
        dhc = _process_cpt(cpt)

        assert np.array_equal(
            data_table["coneResistance"] == nan_mapping["coneResistance"],
            dhc.collections[0].distance_table["cone_resistance"].isna()
        )
        for col in [inclination_ew, inclination_ns, inclination_resultant]:
            assert np.array_equal(
                data_table[col.as_camel] == nan_mapping[col.as_camel],
                dhc.path[col.as_snake].isna()
            )

        # Check how the dip and azimuth get handled if any of their inputs are NaN. It's inconsistent that azimuth
        # gets a value of 0.0 and dip gets NaN, but that's how it is.
        nan_inputs_to_az = np.logical_or(dhc.path["inclination_ew"].isna(), dhc.path["inclination_ns"].isna())
        assert (dhc.path["azimuth"][nan_inputs_to_az] == 0.0).all()

        nan_inputs_to_dip = dhc.path["inclination_resultant"].isna()
        assert dhc.path["dip"][nan_inputs_to_dip].isna().all()
