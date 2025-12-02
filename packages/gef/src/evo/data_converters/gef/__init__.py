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

from pint import UnitRegistry, set_application_registry

# Create one registry for the GEF package
gef_unit_registry = UnitRegistry()

# Custom units not standard in pint
gef_unit_registry.define("kN_per_m3 = kilonewton / meter ** 3 = kN/m3")
gef_unit_registry.define("percent = 0.01 = % = pct")

# Set up pint-pandas to use that registry
set_application_registry(gef_unit_registry)
