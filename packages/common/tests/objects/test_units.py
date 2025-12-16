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


from evo_schemas.elements.unit_energy_per_volume import UnitEnergyPerVolume_V1_0_1_UnitCategories as UnitEnergyPerVolume
from evo_schemas.elements.unit_force_per_volume import UnitForcePerVolume_V1_0_1_UnitCategories as UnitForcePerVolume
from evo_schemas.elements.unit_length import UnitLength_V1_0_1_UnitCategories as UnitLength
from evo_schemas.elements.unit_magnetic_flux_density import (
    UnitMagneticFluxDensity_V1_0_1_UnitCategories as UnitMagneticFluxDensity,
)
from evo_schemas.elements.unit_plane_angle import UnitPlaneAngle_V1_0_1_UnitCategories as UnitPlaneAngle
from evo_schemas.elements.unit_time_per_length import UnitTimePerLength_V1_0_1_UnitCategories as UnitTimePerLength
from pint_pandas import PintType

from evo.data_converters.common.objects.units import UnitMapper


class TestUnitMapper:
    """Test Pint Unit to Evo Unit mapping"""

    def test_lookup_non_EVO_unit(self) -> None:
        # Use Astronomical unit as it's unlikely to be used in
        # a geological data set
        type = PintType("au")
        unit = UnitMapper.lookup(type)
        assert unit is None

    def test_lookup_pint_m3_per_m2_unit(self) -> None:
        # m^3/m^2 is problematic because pint by default will
        # reduce the unit to m which is not what we want
        # so we've defined a custom unit "m3_per_m2" which
        # prevents the simplification
        type = PintType("m3_per_m2")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitLength.Unit_m3_per_m2, "Pint type is " + str(type)

    def test_lookup_pint_m3_per_m2(self) -> None:
        # m^3/m^2 is problematic because pint by default will
        # reduce the unit to m which is not what we want
        # this test confirms that behaviour
        type = PintType("m^3/m^2")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitLength.Unit_m, "Pint type is " + str(type)

    def test_lookup_bbl_per_acre(self) -> None:
        type = PintType("bbl/acre")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitLength.Unit_bbl_per_acre, "Pint type is " + str(type)

    def test_lookup_ft3_per_ft2(self) -> None:
        type = PintType("ft^3/ft^2")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitLength.Unit_ft3_per_ft2, "Pint type is " + str(type)

    #
    # Units used by GEF format files
    #
    def test_lookup_pint_MPa(self) -> None:
        type = PintType("MPa")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitEnergyPerVolume.Unit_MPa

    def test_lookup_pint_m(self) -> None:
        type = PintType("m")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitLength.Unit_m, "Pint type is " + str(type)

    def test_lookup_pint_N_m3(self) -> None:
        type = PintType("N/m^3")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitForcePerVolume.Unit_N_per_m3

    def test_lookup_pint_degrees(self) -> None:
        type = PintType("degrees")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitPlaneAngle.Unit_dega

    def test_lookup_s_m(self) -> None:
        type = PintType("s/m")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitTimePerLength.Unit_s_per_m

    def test_lookup_nT(self) -> None:
        type = PintType("nT")
        unit = UnitMapper.lookup(type)
        assert unit is not None
        assert unit == UnitMagneticFluxDensity.Unit_nT
