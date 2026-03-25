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
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_GEF_CPT_DIR = os.path.join(_DATA_DIR, "gef-cpt")
_GEF_XML_DIF = os.path.join(_DATA_DIR, "gef-xml")

GEF1 = os.path.join(_GEF_CPT_DIR, "cpt.gef")
GEF2 = os.path.join(_GEF_CPT_DIR, "cpt2.gef")
GEF_XML_MULTIPLE = os.path.join(_GEF_XML_DIF, "cpt_multiple.xml")
