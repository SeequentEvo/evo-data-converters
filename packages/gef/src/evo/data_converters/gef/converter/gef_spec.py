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


COLLAR_ATTRIBUTES: list[str] = [
    # GEF
    "delivered_vertical_position_offset",  # ZID
    "research_report_date",  # FILEDATE
    # TODO Understand these
    # NOT GEF
    "cpt_description",
    "standardized_location",
    "cone_diameter",
    "cone_to_friction_sleeve_surface_area",
    "zlm_inclination_resultant_before",
    "zlm_inclination_resultant_after",
]

COMPUTED = [
    "groundwater_level_offset",
    "predrilled_depth_offset",
    "final_depth_offset",
]

MEASUREMENT_TEXT_NAMES: dict[int, str] = {
    1: "client",
    2: "project_name",
    3: "location_name",
    4: "cone_type_serial",
    5: "probe_mass_geometry",
    6: "applied_standard",
    7: "coordinate_system",
    8: "reference_level",
    9: "ground_level",
    10: "inclination_n_direction",
    11: "unusual_circumstances",
    12: "reserved_12",
    13: "reserved_13",
    14: "reserved_14",
    15: "reserved_15",
    16: "reserved_16",
    17: "reserved_17",
    18: "reserved_18",
    19: "reserved_19",
    20: "zero_drift_correction",
    21: "interruption_processing",
    22: "remarks_22",
    23: "remarks_23",
    24: "reserved_24",
    25: "reserved_25",
    26: "reserved_26",
    27: "reserved_27",
    28: "reserved_28",
    29: "reserved_29",
    30: "calculation_formula_30",
    31: "calculation_formula_31",
    32: "calculation_formula_32",
    33: "calculation_formula_33",
    34: "calculation_formula_34",
    35: "calculation_formula_35",
    36: "reserved_36",
    37: "reserved_37",
    38: "reserved_38",
    39: "reserved_39",
    40: "reserved_40",
    41: "infrastructure_code",
    42: "zid_method",
    43: "xyid_method",
    44: "x_axis_orientation",
}

MEASUREMENT_VAR_NAMES: dict[int, str] = {
    1: "cone_tip_area",
    2: "friction_sleeve_area",
    3: "cone_tip_area_quotient",
    4: "friction_sleeve_area_quotient",
    5: "cone_friction_distance",
    6: "friction_present",
    7: "ppt_u1_present",
    8: "ppt_u2_present",
    9: "ppt_u3_present",
    10: "inclination_present",
    11: "backflow_compensator",
    12: "test_type",
    13: "preexcavated_depth",
    14: "groundwater_level",
    15: "water_depth",
    16: "end_depth",
    17: "stop_criteria",
    18: "reserved_18",
    19: "reserved_19",
    20: "cone_zero_before",
    21: "cone_zero_after",
    22: "friction_zero_before",
    23: "friction_zero_after",
    24: "ppt_u1_zero_before",
    25: "ppt_u1_zero_after",
    26: "ppt_u2_zero_before",
    27: "ppt_u2_zero_after",
    28: "ppt_u3_zero_before",
    29: "ppt_u3_zero_after",
    30: "inclination_zero_before",
    31: "inclination_zero_after",
    32: "inclination_ns_zero_before",
    33: "inclination_ns_zero_after",
    34: "inclination_ew_zero_before",
    35: "inclination_ew_zero_after",
    36: "reserved_36",
    37: "reserved_37",
    38: "reserved_38",
    39: "reserved_39",
    40: "reserved_40",
    41: "mileage",
    42: "x_axis_north_orientation",
}

# Note on reserved fields:
# CPT files have been observed to contain reserved fields, which apparently require some tribal knowledge to understand.
# In the "cpt.gef" file that is a test file in this repository, reserved TEXT fields 24 and 25 are used.
# The following is a list of potentially used reserved fields, that are documented here for insight but will not be
# handled during import. The "CPT" fields are are the ones that are relevant to the files currently being imported.
# This knowledge was generated using Github Copilot with Claude Opus 4.5.
# RESERVED MEASUREMENTTEXT USAGE:
#   12: Location determination method (GEF-BORE)
#   13: Drilling company (GEF-BORE)
#   14: Public (yes/no) (GEF-BORE)
#   15 Date of groundwater level measurement for piezometer 1 (Piezometer files)
#   16: Drilling date (GEF-BORE)
#   16: Filter inflow for pizemeter 1 (Piezometer files)
#   18: Piezometer present/absent (GEF-BORE)
#   19: End date of drilling (GEF-BORE)
#   24: CPTest software version (GEF-CPT)
#   25: CPTask software version (GEF-CPT)
#
# RESERVED MEASUREMENTVAR USAGE:
#   18: Groundwater level (GEF-BORE)
#   19: Number of piezometers (GEF-BORE)
#   36: Electrical conductivity before penetration (BRO CPT)
#   37: Electrical conductivity after penetration (BRO CPT)
#   37: Top of piezometer 2 (Piezometer files)
#   38: Diameter of piezometer 2 (Piezometer files)
#   39: Length of standpipe piezometer 2 (Piezometer files)
#   40: Length of sand trap piezometer 2 (Piezometer files)


# It should be noted here that the following column names are those provided
# by PyGef. If a column name maps to an empty string then this implies a
# dimensionless unit. Examples of dimensionless columns would be percentage
# values or ratios.
MEASUREMENT_UNITS: dict[str, str] = {
    "penetrationLength": "m",
    "coneResistance": "MPa",
    "localFriction": "MPa",
    "frictionRatio": "",
    "porePressureU1": "MPa",
    "porePressureU2": "MPa",
    "porePressureU3": "MPa",
    "inclinationResultant": "degrees",
    "inclinationNS": "degrees",
    "inclinationEW": "degrees",
    "depth": "m",
    "elapsedTime": "s",
    "correctedConeResistance": "MPa",
    "netConeResistance": "MPa",
    "poreRatio": "",
    "coneResistanceRatio": "",
    "soilDensity": "kN/m**3",
    "porePressure": "MPa",
    "verticalPorePressureTotal": "MPa",
    "verticalPorePressureEffective": "MPa",
    "inclinationX": "degrees",
    "inclinationY": "degrees",
    "electricalConductivity": "S/m",
    "magneticFieldStrengthX": "nT",
    "magneticFieldStrengthY": "nT",
    "magneticFieldStrengthZ": "nT",
    "magneticFieldStrengthTotal": "nT",
    "magneticInclination": "degrees",
    "magneticDeclination": "degrees",
}

MEASUREMENT_UNIT_CONVERSIONS: dict[str, str] = {
    "kN/m**3": "N/m**3",
}

# For reference, this is the specification for COLUMNINFO:
# 1: Penetration length
# 2: Cone resistance (qc)
# 3: Local friction (fs)
# 4: Friction ratio (Rf)
# 5: Pore pressure (u1)
# 6: Pore pressure (u2)
# 7: Pore pressure (u3)
# 8: Inclination resultant
# 9: Inclination N-S
# 10: Inclination E-W
# 11: Corrected depth
# 12: Elapsed time
# 13: Corrected cone resistance (qt)
# 14: Net cone resistance (qn)
# 15: Pore ratio (Bq)
# 16: Cone resistance ratio (Nm)
# 17: Weight per unit volume
# 18: In-situ initial pore pressure
# 19: Total vertical pore pressure
# 20: Effective vertical soil pressure
# 21: Inclination in X direction
# 22: Inclination in Y direction
# 23: Electric conductivity
# 24-30: Reserved for future use
# 31: Magnetic field strength in X direction
# 32: Magnetic field strength in Y direction
# 33: Magnetic field strength in Z direction
# 34: Total magnetic field strength
# 35: Magnetic inclination
# 36: Magnetic declination
