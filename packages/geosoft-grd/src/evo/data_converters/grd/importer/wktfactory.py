#  Copyright © 2026 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from . import core_commons as commons

# Constants
AXIS = "AXIS"
USAGE = "USAGE"
LENGTHUNIT = "LENGTHUNIT"
GEOGCRS = "GEOGCRS"
GEODCRS = "GEODCRS"
PROJCRS = "PROJCRS"
BASEGEOGCRS = "BASEGEOGCRS"
BASEGEODCRS = "BASEGEODCRS"
DATUM = "DATUM"
ENSEMBLE = "ENSEMBLE"
METHOD = "METHOD"
ID = "ID"
PRIMEM = "PRIMEM"
ELLIPSOID = "ELLIPSOID"
PARAMETER = "PARAMETER"
CS = "CS"

LONGITUDE_OF_NATURAL_ORIGIN = "Longitude of natural origin"
LATITUDE_OF_NATURAL_ORIGIN = "Latitude of natural origin"
SCALE_FACTOR_AT_NATURAL_ORIGIN = "Scale factor at natural origin"
FALSE_EASTING = "False easting"
FALSE_NORTHING = "False northing"
AZIMUTH_OF_INITIAL_LINE = "Azimuth of initial line"
LATITUDE_OF_FALSE_ORIGIN = "Latitude of false origin"
LONGITUDE_OF_FALSE_ORIGIN = "Longitude of false origin"
LATITUDE_OF_FIRST_STD_PARALLEL = "Latitude of 1st standard parallel"
LATITUDE_OF_SECOND_STD_PARALLEL = "Latitude of 2nd standard parallel"

DERIVEDPROJCRS = "DERIVEDPROJCRS"
BASESTR = "BASE"
DERIVINGCONVERSION = "DERIVINGCONVERSION"

EMPTYWKT = (
    'PROJCRS["",\n'
    '    BASEGEOGCRS["",\n'
    '        DATUM["",\n'
    '            ELLIPSOID["",0,0,\n'
    '                LENGTHUNIT["metre",1]]],\n'
    '        PRIMEM["Greenwich",0,\n'
    '            ANGLEUNIT["degree",0.0174532925199433]],\n'
    '        ID["EPSG",0]],\n'
    '    CONVERSION["",\n'
    '        METHOD["",\n'
    '            ID["EPSG",9807]],\n'
    '        PARAMETER["Latitude of natural origin",0,\n'
    '            ANGLEUNIT["degree",0.0174532925199433],\n'
    '            ID["EPSG",8801]],\n'
    '        PARAMETER["Longitude of natural origin",0,\n'
    '            ANGLEUNIT["degree",0.0174532925199433],\n'
    '            ID["EPSG",8802]],\n'
    '        PARAMETER["Scale factor at natural origin",0,\n'
    '            SCALEUNIT["unity",1],\n'
    '            ID["EPSG",8805]],\n'
    '        PARAMETER["Azimuth of initial line",0,\n'
    '            SCALEUNIT["degree",1],\n'
    '            ID["EPSG",8813]],\n'
    '        PARAMETER["Latitude of false origin",0,\n'
    '            SCALEUNIT["degree",1],\n'
    '            ID["EPSG",8821]],\n'
    '        PARAMETER["Longitude of false origin",0,\n'
    '            SCALEUNIT["degree",1],\n'
    '            ID["EPSG",8822]],\n'
    '        PARAMETER["Latitude of 1st standard parallel",0,\n'
    '            SCALEUNIT["degree",1],\n'
    '            ID["EPSG",8823]],\n'
    '        PARAMETER["Latitude of 2nd standard parallel",0,\n'
    '            SCALEUNIT["unity",1],\n'
    '            ID["EPSG",8824]],\n'
    '        PARAMETER["False easting",0,\n'
    '            LENGTHUNIT["metre",1],\n'
    '            ID["EPSG",8806]],\n'
    '        PARAMETER["False northing",0,\n'
    '            LENGTHUNIT["metre",1],\n'
    '            ID["EPSG",8807]]],\n'
    '    CS[Cartesian,2],\n'
    '        AXIS["(E)",east,\n'
    '            ORDER[1],\n'
    '            LENGTHUNIT["metre",1]],\n'
    '        AXIS["(N)",north,\n'
    '            ORDER[2],\n'
    '            LENGTHUNIT["metre",1]],\n'
    '   ID["",0]]]'
)

class WktFactory:
    """Produces WKT strings from projection data"""

    @staticmethod
    def get_wkt(proj_data: dict) -> str:
        """
        Produces a WKT string from projection data.
        
        Args:
            proj_data: Dictionary containing projection parameters
        
        Returns:
            WKT string
        """
        wkt = EMPTYWKT

        wkt = WktFactory.update_property_name(wkt, PROJCRS, proj_data.get('projectName', ''))
        wkt = WktFactory.update_property_name(wkt, GEOGCRS, proj_data.get('crsName', ''))
        wkt = WktFactory.update_property_name(wkt, GEODCRS, proj_data.get('crsName', ''))
        wkt = WktFactory.update_property_name(wkt, BASEGEODCRS, proj_data.get('crsName', ''))
        wkt = WktFactory.update_property_name(wkt, DATUM, proj_data.get('datumName', ''))
        wkt = WktFactory.update_property_name(wkt, ENSEMBLE, proj_data.get('datumName', ''))
        wkt = WktFactory.update_ellipsoid(
            wkt,
            proj_data.get('ellipsoidName', ''),
            proj_data.get('ellipsoidRadius', 0),
            proj_data.get('ellipsoidInvFlatenning', 0)
        )
        wkt = WktFactory.update_property_name(wkt, METHOD, proj_data.get('conversionName', ''))
        wkt = WktFactory.update_axis_units(wkt, proj_data.get('axisUnit', 'metre'), proj_data.get('axisScale', 1))
        wkt = WktFactory.update_id(wkt, proj_data.get('authorityName', ''), proj_data.get('authorityIdChar', ''))
        wkt = WktFactory.update_prime_meridian(wkt, proj_data.get('primeMeridian', 0))
        wkt = WktFactory.update_parameter(wkt, LONGITUDE_OF_NATURAL_ORIGIN, proj_data.get('longitudeOfNaturalOrigin', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, LATITUDE_OF_NATURAL_ORIGIN, proj_data.get('latitudeOfNaturalOrigin', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, SCALE_FACTOR_AT_NATURAL_ORIGIN, proj_data.get('scaleFactorAtNaturalOrigin', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, FALSE_EASTING, proj_data.get('falseEasting', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, FALSE_NORTHING, proj_data.get('falseNorthing', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, AZIMUTH_OF_INITIAL_LINE, proj_data.get('azimuthOfInitialLine', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, LATITUDE_OF_FALSE_ORIGIN, proj_data.get('latitudeOfFalseOrigin', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, LONGITUDE_OF_FALSE_ORIGIN, proj_data.get('longitudeOfFalseOrigin', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, LATITUDE_OF_FIRST_STD_PARALLEL, proj_data.get('latitudeOfFirstStdParallel', commons.D_DUMMY))
        wkt = WktFactory.update_parameter(wkt, LATITUDE_OF_SECOND_STD_PARALLEL, proj_data.get('latitudeOfSecondStdParallel', commons.D_DUMMY))

        # Handle transformation if it exists
        if proj_data.get('transformation_name'):
            wkt = WktFactory.create_derived_proj_wkt(wkt, proj_data)

        return WktFactory.copy_compressed_wkt(wkt)

    @staticmethod
    def update_property_name(wkt: str, prop: str, value: str) -> str:
        """Updates the name value of a property"""
        init = wkt.find(prop)

        if init == -1:
            return wkt

        end = wkt.find("\n", init)

        if end == -1:
            return wkt

        name = f'{prop}["{value}",'
        return wkt[:init] + name + wkt[end:]

    @staticmethod
    def update_ellipsoid(wkt: str, name: str, radius: float, flattening: float) -> str:
        """Updates the ellipsoid parameter"""
        init = wkt.find(ELLIPSOID)

        if init == -1:
            return wkt

        end = wkt.find("\n", init)

        if end == -1:
            return wkt

        ellips = f'{ELLIPSOID}["{name}",{radius},{flattening},'
        return wkt[:init] + ellips + wkt[end:]

    @staticmethod
    def update_axis_units(wkt: str, unit: str, scale: float) -> str:
        """Updates axis length units"""
        axis_pos = wkt.find(AXIS)

        while axis_pos != -1:
            wkt = WktFactory.update_length_unit(wkt, axis_pos, unit, scale)
            axis_pos = wkt.find(AXIS, axis_pos + 1)

        return wkt

    @staticmethod
    def update_length_unit(wkt: str, init: int, unit: str, scale: float) -> str:
        """Updates a length unit at a specific position"""
        length_init = wkt.find(LENGTHUNIT, init)
        length_end = wkt.find("\n", length_init)

        if length_init == -1:
            return wkt

        length_unit_str = f'{LENGTHUNIT}["{unit}",{scale}]],'
        return wkt[:length_init] + length_unit_str + wkt[length_end:]

    @staticmethod
    def update_id(wkt: str, authority_name: str, authority_code: str) -> str:
        """Updates the ID property"""
        id_pos = wkt.rfind(ID)

        if id_pos == -1 or not authority_code or not authority_name:
            return wkt

        id_str = f'{ID}["{authority_name}",{authority_code}]]'
        return wkt[:id_pos] + id_str

    @staticmethod
    def update_prime_meridian(wkt: str, prime_meridian: float) -> str:
        """Updates the prime meridian value"""
        prime_merd = wkt.find(PRIMEM)

        if prime_merd == -1:
            return wkt

        end = wkt.find("\n", prime_merd)

        new_param = f'{PRIMEM}["Greenwich",{prime_meridian},'
        return wkt[:prime_merd] + new_param + wkt[end:]

    @staticmethod
    def update_parameter(wkt: str, param_name: str, value: float) -> str:
        """Updates a parameter value"""
        init = wkt.find(param_name)
        end = wkt.find("\n", init)

        if init != -1 and value != commons.D_DUMMY:
            init -= len(PARAMETER)
            init -= 2
            new_param = f'{PARAMETER}["{param_name}",{value},'
            return wkt[:init] + new_param + wkt[end:]

        return wkt

    @staticmethod
    def create_derived_proj_wkt(wkt: str, proj_data: dict) -> str:
        """Updates a WKT to have a transformation embedded in it"""
        wkt = WktFactory.remove_not_transformation_params(wkt)

        wkt = (
            f'{DERIVEDPROJCRS}["{proj_data.get("transformation_name", "")}",'
            f'{BASESTR}{wkt},'
            f'{WktFactory.get_derived_conversion_string(proj_data)},'
            f'{WktFactory.get_transformation_cs_axis_parameter(proj_data.get("axisUnit", "metre"), proj_data.get("axisScale", 1))}]'
        )

        return wkt

    @staticmethod
    def remove_not_transformation_params(wkt: str) -> str:
        """Removes non-transformation parameters from WKT"""
        single_bracket = "],"
        double_bracket = "]],"
        triple_bracket = "]]],"

        # Remove CS
        begin_it = wkt.find(CS)
        if begin_it != -1:
            end_it = wkt.find(single_bracket, begin_it)
            if end_it != -1:
                wkt = wkt[:begin_it] + wkt[end_it + len(single_bracket):]

        # Remove AXIS
        begin_it = wkt.find(AXIS)
        while begin_it != -1:
            end_it = wkt.find(double_bracket, begin_it)
            if end_it != -1:
                wkt = wkt[:begin_it] + wkt[end_it + len(double_bracket):]
            begin_it = wkt.find(AXIS)

        # Remove USAGE
        begin_it = wkt.find(USAGE)
        if begin_it != -1:
            end_it = wkt.find(double_bracket, begin_it)
            if end_it != -1:
                wkt = wkt[:begin_it] + wkt[end_it + len(double_bracket):]

        # Remove closing bracket from the last parameter
        last_parameter_pos = wkt.rfind(PARAMETER)
        last_id_pos = wkt.rfind(ID)

        if last_parameter_pos != -1 and last_id_pos != -1 and last_id_pos > last_parameter_pos:
            begin_it = wkt.rfind(triple_bracket, 0, last_id_pos)
            if begin_it != -1:
                wkt = wkt[:begin_it] + wkt[begin_it + 1:]

        return wkt

    @staticmethod
    def get_derived_conversion_string(proj_data: dict) -> str:
        """Gets the derived conversion string for transformation"""
        transformation = "Coordinate Frame rotation(geocentric domain)"
        code = "1032"

        return (
            f'{DERIVINGCONVERSION}['
            f'"{proj_data.get("datumName", "")} applying {transformation}",'
            f'{WktFactory.get_rotation_method_string(transformation, code)},'
            f'{WktFactory.get_transformation_linear_parameter("X-axis translation", proj_data.get("transformation_x", 0))},'
            f'{WktFactory.get_transformation_linear_parameter("Y-axis translation", proj_data.get("transformation_y", 0))},'
            f'{WktFactory.get_transformation_linear_parameter("Z-axis translation", proj_data.get("transformation_z", 0))},'
            f'{WktFactory.get_transformation_angular_parameter("X-axis rotation", proj_data.get("transformation_rx", 0))},'
            f'{WktFactory.get_transformation_angular_parameter("Y-axis rotation", proj_data.get("transformation_ry", 0))},'
            f'{WktFactory.get_transformation_angular_parameter("Z-axis rotation", proj_data.get("transformation_rz", 0))},'
            f'{WktFactory.get_transformation_scalar_parameter("Scale difference", proj_data.get("transformation_scale", 0))}]'
        )

    @staticmethod
    def get_rotation_method_string(transformation_name: str, epsg_code: str) -> str:
        """Defines the rotation where the transformation is applied"""
        return f'{METHOD}["{transformation_name}", {ID}["EPSG",{epsg_code}]]'

    @staticmethod
    def get_transformation_linear_parameter(param: str, value: float) -> str:
        """Gets a linear transformation parameter string"""
        return f'{PARAMETER}["{param}", {value}, {LENGTHUNIT}["metre", 1.0]]'

    @staticmethod
    def get_transformation_angular_parameter(param: str, value: float) -> str:
        """Gets an angular transformation parameter string"""
        return f'{PARAMETER}["{param}", {value}, ANGLEUNIT["arc-second", 4.84813681109536E-6]]'

    @staticmethod
    def get_transformation_scalar_parameter(param: str, value: float) -> str:
        """Gets a scalar transformation parameter string"""
        return f'{PARAMETER}["{param}", {value}, SCALEUNIT["parts per million", 1E-6]]'

    @staticmethod
    def get_transformation_cs_axis_parameter(unit: str, scale: float) -> str:
        """Gets the CS axis parameter string for transformation"""
        return (
            f'{CS}[Cartesian,2],'
            f'{WktFactory.get_transformation_axis_parameter("E", "1", unit, scale)},'
            f'{WktFactory.get_transformation_axis_parameter("N", "2", unit, scale)}'
        )

    @staticmethod
    def get_transformation_axis_parameter(direction: str, order_index: str, unit: str, scale: float) -> str:
        """Gets a transformation axis parameter string"""
        direction_full = "east" if direction == "E" else "north"
        return (
            f'{AXIS}["({direction})",{direction_full},'
            f'ORDER[{order_index}],'
            f'{LENGTHUNIT}["{unit}",{scale}]]'
        )

    @staticmethod
    def copy_compressed_wkt(wkt_str: str) -> str:
        """
        Copies the WKT string skipping non-essential characters (newlines and
        spaces outside quotes)
        """
        result = []
        is_between_quotes = False

        for c in wkt_str:
            if c == '\n':
                continue
            if c == '"':
                is_between_quotes = not is_between_quotes
            if not is_between_quotes and c == ' ':
                continue
            result.append(c)

        return ''.join(result)
