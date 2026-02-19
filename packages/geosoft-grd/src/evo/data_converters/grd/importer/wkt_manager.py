from .ipj_def_x import IPJ_DEF_X
from .ipj_def_x3 import IPJ_DEF_X3
from .wktfactory import WktFactory
from . import core_commons as commons
import math
from .ipj_type import PROJ_TYPE


class Wkt_Manager:
    @staticmethod 
    def get_wkt(def_x : IPJ_DEF_X, def_x3 : IPJ_DEF_X3) -> str:
        
        projectName = def_x.szIPJ
        datumName = def_x.szProj
        crsName = def_x.szDatum
        ellipsoidName = def_x.szEllipsoid
        ellipsoidRadius = def_x.dRadius
        ellipsoidEccentricity = def_x.dEccentricity

        if (ellipsoidEccentricity != commons.D_DUMMY and ellipsoidEccentricity != 0):  
            ellipsoidFlatenning = 1 - math.sqrt((1 - math.pow(ellipsoidEccentricity, 2)))
            ellipsoidInvFlatenning = 1 / ellipsoidFlatenning
        
        conversionName = PROJ_TYPE.parse_ipj_to_proj_type(def_x.lProjType)

        axisUnit = 'unknown'
        if (def_x.Units.szID != '' and def_x.Units.szID == "m"):
            axisUnit = "metre"
        else:
            axisUnit = def_x.Units.szID

        axisScale = def_x.dScaleAdjust
        primeMeridian = def_x.dPrimeMeridian

        longitudeOfNaturalOrigin = def_x.proj_params[1]
        latitudeOfNaturalOrigin = def_x.proj_params[0]
        scaleFactorAtNaturalOrigin = def_x.proj_params[4]
        falseEasting = def_x.proj_params[5]
        falseNorthing = def_x.proj_params[6]
        azimuthOfInitialLine = def_x.proj_params[2]
        latitudeOfFalseOrigin = def_x.proj_params[2]
        longitudeOfFalseOrigin = def_x.proj_params[3]
        latitudeOfFirstStdParallel = def_x.proj_params[0]
        latitudeOfSecondStdParallel = def_x.proj_params[1]

        if (def_x.szDatumTrf != ''):
            transformation_name = def_x.szDatumTrf
        
        transformation_x = def_x.dDx
        transformation_y = def_x.dDy
        transformation_z = def_x.dDz

        transformation_rx = commons.D_DUMMY
        transformation_ry = commons.D_DUMMY
        transformation_rz = commons.D_DUMMY
        transformation_scale = commons.D_DUMMY

        if(def_x.dRx != commons.D_DUMMY):
            transformation_rx = def_x.dRx / commons.ARCSEC2RAD
        if(def_x.dRy != commons.D_DUMMY):
            transformation_ry = def_x.dRy / commons.ARCSEC2RAD
        if(def_x.dRz != commons.D_DUMMY):
            transformation_rz = def_x.dRz / commons.ARCSEC2RAD
        if(def_x.dScaleAdjust != commons.D_DUMMY and def_x.dScaleAdjust != 0 and def_x.dScaleAdjust != 1):
            transformation_scale = (def_x.dScaleAdjust - 1.0) / commons.SCALEADJUSTCOEFFICIENT
        else:
            transformation_scale = def_x.dScaleAdjust

        authority_id_number = def_x3.lAuthoritativeID
        authority = def_x3.szAuthority

        # Build projection data dictionary for WktFactory
        proj_data = {
            'projectName': projectName,
            'datumName': datumName,
            'crsName': crsName,
            'ellipsoidName': ellipsoidName,
            'ellipsoidRadius': ellipsoidRadius,
            'ellipsoidInvFlatenning': ellipsoidInvFlatenning if 'ellipsoidInvFlatenning' in dir() else 0,
            'conversionName': conversionName,
            'axisUnit': axisUnit,
            'axisScale': axisScale,
            'primeMeridian': primeMeridian,
            'longitudeOfNaturalOrigin': longitudeOfNaturalOrigin,
            'latitudeOfNaturalOrigin': latitudeOfNaturalOrigin,
            'scaleFactorAtNaturalOrigin': scaleFactorAtNaturalOrigin,
            'falseEasting': falseEasting,
            'falseNorthing': falseNorthing,
            'azimuthOfInitialLine': azimuthOfInitialLine,
            'latitudeOfFalseOrigin': latitudeOfFalseOrigin,
            'longitudeOfFalseOrigin': longitudeOfFalseOrigin,
            'latitudeOfFirstStdParallel': latitudeOfFirstStdParallel,
            'latitudeOfSecondStdParallel': latitudeOfSecondStdParallel,
            'transformation_name': transformation_name if 'transformation_name' in dir() else None,
            'transformation_x': transformation_x,
            'transformation_y': transformation_y,
            'transformation_z': transformation_z,
            'transformation_rx': transformation_rx,
            'transformation_ry': transformation_ry,
            'transformation_rz': transformation_rz,
            'transformation_scale': transformation_scale,
            'authorityName': authority,
            'authorityIdChar': authority_id_number,
        }

        # Generate WKT using WktFactory
        return WktFactory.get_wkt(proj_data)