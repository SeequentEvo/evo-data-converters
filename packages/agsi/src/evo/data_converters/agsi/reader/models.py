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

"""Typed models for the subset of the AGSi 1.0.x schema used by the converter.

Python attribute names are snake_case; the AGSi (camelCase) names are used as aliases, so
models are populated from, and serialised back to, AGSi JSON with ``model_validate`` and
:meth:`AgsiBaseModel.to_agsi`. Every model keeps unknown attributes (``extra="allow"``) so
nothing in the source document is lost on a round trip.

Reference: https://ags-data-format-wg.gitlab.io/agsi/agsi_standard/latest/
"""

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class AgsiBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
        protected_namespaces=(),
    )

    def to_agsi(self) -> dict[str, Any]:
        """Serialise to an AGSi JSON-compatible dict, keeping unknown attributes."""
        return self.model_dump(by_alias=True, exclude_unset=True, exclude_none=True, mode="json")

    @property
    def extra_attributes(self) -> dict[str, Any]:
        """Attributes present in the source that are not modelled explicitly."""
        return dict(self.model_extra or {})


# --- General / project -------------------------------------------------------------------


class AgsSchema(AgsiBaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    link: Optional[str] = None


class AgsFile(AgsiBaseModel):
    file_uuid: Optional[str] = Field(None, alias="fileUUID")
    title: Optional[str] = None
    project_title: Optional[str] = None
    description: Optional[str] = None
    produced_by: Optional[str] = None
    file_uri: Optional[str] = Field(None, alias="fileURI")
    reference: Optional[str] = None
    revision: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = None
    status_code: Optional[str] = None
    made_by: Optional[str] = None
    checked_by: Optional[str] = None
    approved_by: Optional[str] = None
    remarks: Optional[str] = None


class AgsProjectCoordinateSystem(AgsiBaseModel):
    system_id: Optional[str] = Field(None, alias="systemID")
    description: Optional[str] = None
    system_type: Optional[str] = None
    system_name_xy: Optional[str] = Field(None, alias="systemNameXY")
    system_name_z: Optional[str] = None
    axis_name_x: Optional[str] = None
    axis_name_y: Optional[str] = None
    axis_name_z: Optional[str] = None
    axis_units_xy: Optional[str] = Field(None, alias="axisUnitsXY")
    axis_units_z: Optional[str] = None
    global_xy_system: Optional[str] = Field(None, alias="globalXYSystem")
    global_z_system: Optional[str] = None
    transform_shift_x: Optional[float] = None
    transform_shift_y: Optional[float] = None
    transform_xy_rotation: Optional[float] = Field(None, alias="transformXYRotation")
    transform_xy_scale_factor: Optional[float] = Field(None, alias="transformXYScaleFactor")
    transform_shift_z: Optional[float] = None
    remarks: Optional[str] = None


class AgsProject(AgsiBaseModel):
    project_uuid: Optional[str] = Field(None, alias="projectUUID")
    project_name: Optional[str] = None
    producer: Optional[str] = None
    producer_suppliers: Optional[str] = None
    client: Optional[str] = None
    description: Optional[str] = None
    project_country: Optional[str] = None
    producer_project_id: Optional[str] = Field(None, alias="producerProjectID")
    client_project_id: Optional[str] = Field(None, alias="clientProjectID")
    parent_project_name: Optional[str] = None
    ultimate_project_name: Optional[str] = None
    ultimate_project_client: Optional[str] = None
    brief_document_set_id: Optional[str] = Field(None, alias="briefDocumentSetID")
    report_document_set_id: Optional[str] = Field(None, alias="reportDocumentSetID")
    ags_project_coordinate_system: list[AgsProjectCoordinateSystem] = Field(default_factory=list)
    ags_project_investigation: list[dict[str, Any]] = Field(default_factory=list)
    ags_project_document_set: list[dict[str, Any]] = Field(default_factory=list)
    ags_project_code_set: list[dict[str, Any]] = Field(default_factory=list)
    remarks: Optional[str] = None


# --- Geometry ----------------------------------------------------------------------------


class AgsiGeometryFromFile(AgsiBaseModel):
    """Pointer to geometry held in a supporting file (WKT, DXF, STL, ...)."""

    geometry_id: Optional[str] = Field(None, alias="geometryID")
    description: Optional[str] = None
    geometry_type: Optional[str] = None
    file_format: Optional[str] = None
    file_format_version: Optional[str] = None
    file_uri: str = Field(alias="fileURI")
    file_part: Optional[str] = None
    revision: Optional[str] = None
    date: Optional[str] = None
    revision_info: Optional[str] = None
    remarks: Optional[str] = None


class AgsiGeometryPlane(AgsiBaseModel):
    """Infinite horizontal plane at a given elevation."""

    geometry_id: Optional[str] = Field(None, alias="geometryID")
    description: Optional[str] = None
    elevation: float
    remarks: Optional[str] = None


class AgsiGeometryLayer(AgsiBaseModel):
    """Volume between two infinite horizontal planes."""

    geometry_id: Optional[str] = Field(None, alias="geometryID")
    description: Optional[str] = None
    top_elevation: Optional[float] = None
    bottom_elevation: Optional[float] = None
    remarks: Optional[str] = None


class AgsiGeometryAreaFromLines(AgsiBaseModel):
    """Area between a top and/or bottom line, typically a cross-section unit."""

    geometry_id: Optional[str] = Field(None, alias="geometryID")
    description: Optional[str] = None
    agsi_geometry_top: Optional[AgsiGeometryFromFile] = None
    agsi_geometry_bottom: Optional[AgsiGeometryFromFile] = None
    remarks: Optional[str] = None


class AgsiGeometryVolFromSurfaces(AgsiBaseModel):
    """Volume between a top and/or bottom surface."""

    geometry_id: Optional[str] = Field(None, alias="geometryID")
    description: Optional[str] = None
    agsi_geometry_top: Optional[Union[AgsiGeometryFromFile, AgsiGeometryPlane]] = None
    agsi_geometry_bottom: Optional[Union[AgsiGeometryFromFile, AgsiGeometryPlane]] = None
    remarks: Optional[str] = None


AgsiGeometry = Union[
    AgsiGeometryVolFromSurfaces,
    AgsiGeometryAreaFromLines,
    AgsiGeometryFromFile,
    AgsiGeometryPlane,
    AgsiGeometryLayer,
]

GEOMETRY_OBJECT_TYPES: dict[str, type[AgsiBaseModel]] = {
    "agsiGeometryFromFile": AgsiGeometryFromFile,
    "agsiGeometryLayer": AgsiGeometryLayer,
    "agsiGeometryPlane": AgsiGeometryPlane,
    "agsiGeometryVolFromSurfaces": AgsiGeometryVolFromSurfaces,
    "agsiGeometryAreaFromLines": AgsiGeometryAreaFromLines,
}

# geometryType values (lower case) that indicate the child of a top/bottom pair is a line.
_LINE_GEOMETRY_TYPES = {"profile", "line", "polyline", "section", "linestring"}


def infer_geometry_object(geometry: dict[str, Any]) -> str:
    """Infer the AGSi geometry object name from the attributes present in ``geometry``."""
    if "fileURI" in geometry or "file_uri" in geometry:
        return "agsiGeometryFromFile"
    if "elevation" in geometry:
        return "agsiGeometryPlane"
    children: list[dict[str, Any]] = [
        c for c in (geometry.get(k) for k in ("agsiGeometryTop", "agsiGeometryBottom")) if isinstance(c, dict)
    ]
    if children:
        types = {str(c.get("geometryType", "")).lower() for c in children}
        if types & _LINE_GEOMETRY_TYPES:
            return "agsiGeometryAreaFromLines"
        return "agsiGeometryVolFromSurfaces"
    if "topElevation" in geometry or "bottomElevation" in geometry:
        return "agsiGeometryLayer"
    return "agsiGeometryFromFile"


# --- Data --------------------------------------------------------------------------------


class AgsiDataParameterValue(AgsiBaseModel):
    data_id: Optional[str] = Field(None, alias="dataID")
    code_id: Optional[str] = Field(None, alias="codeID")
    case_id: Optional[str] = Field(None, alias="caseID")
    value_numeric: Optional[float] = None
    value_text: Optional[str] = None
    value_profile_ind_var_code_id: Optional[str] = Field(None, alias="valueProfileIndVarCodeID")
    value_profile: Optional[list[list[float]]] = None
    remarks: Optional[str] = None


# --- Model -------------------------------------------------------------------------------


class AgsiModelBoundary(AgsiBaseModel):
    boundary_id: Optional[str] = Field(None, alias="boundaryID")
    description: Optional[str] = None
    min_x: Optional[float] = None
    max_x: Optional[float] = None
    min_y: Optional[float] = None
    max_y: Optional[float] = None
    top_elevation: Optional[float] = None
    bottom_elevation: Optional[float] = None
    agsi_geometry_boundary_xy: Optional[AgsiGeometryFromFile] = Field(None, alias="agsiGeometryBoundaryXY")
    agsi_geometry_surface_top: Optional[AgsiGeometryFromFile] = None
    agsi_geometry_surface_bottom: Optional[AgsiGeometryFromFile] = None
    remarks: Optional[str] = None


class AgsiModelAlignment(AgsiBaseModel):
    alignment_id: Optional[str] = Field(None, alias="alignmentID")
    alignment_name: Optional[str] = None
    description: Optional[str] = None
    agsi_geometry: Optional[AgsiGeometryFromFile] = None
    start_chainage: Optional[float] = None
    remarks: Optional[str] = None


class AgsiModelElement(AgsiBaseModel):
    element_id: Optional[str] = Field(None, alias="elementID")
    element_name: Optional[str] = None
    description: Optional[str] = None
    element_type: Optional[str] = None
    geometry_object: Optional[str] = None
    agsi_geometry: Optional[AgsiGeometry] = None
    agsi_geometry_area_limit: Optional[AgsiGeometryFromFile] = None
    agsi_data_parameter_value: list[AgsiDataParameterValue] = Field(default_factory=list)
    agsi_data_property_value: list[dict[str, Any]] = Field(default_factory=list)
    agsi_data_property_summary: list[dict[str, Any]] = Field(default_factory=list)
    agsi_data_property_from_file: Optional[dict[str, Any]] = None
    colour_rgb: Optional[str] = Field(None, alias="colourRGB")
    remarks: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _select_geometry_class(cls, data: Any) -> Any:
        """Pick the geometry model using ``geometryObject``; AreaFromLines and VolFromSurfaces
        have identical attributes, so a plain union cannot tell them apart."""
        if not isinstance(data, dict):
            return data
        key = "agsiGeometry" if "agsiGeometry" in data else "agsi_geometry"
        geometry = data.get(key)
        if not isinstance(geometry, dict):
            return data
        name = data.get("geometryObject", data.get("geometry_object"))
        geometry_cls = GEOMETRY_OBJECT_TYPES.get(str(name)) if name else None
        if geometry_cls is None:
            geometry_cls = GEOMETRY_OBJECT_TYPES[infer_geometry_object(geometry)]
        return {**data, key: geometry_cls.model_validate(geometry)}

    @property
    def geometry_object_name(self) -> Optional[str]:
        """AGSi object name of :attr:`agsi_geometry`, e.g. ``"agsiGeometryAreaFromLines"``."""
        if self.agsi_geometry is None:
            return None
        for name, geometry_cls in GEOMETRY_OBJECT_TYPES.items():
            if type(self.agsi_geometry) is geometry_cls:
                return name
        return None

    def geometry_files(self) -> list[tuple[str, AgsiGeometryFromFile]]:
        """All file-based geometry referenced by this element as ``(role, geometry)`` pairs.

        Roles are ``"top"``, ``"bottom"``, ``"geometry"`` (directly referenced file) and
        ``"area_limit"``.
        """
        files: list[tuple[str, AgsiGeometryFromFile]] = []
        geometry = self.agsi_geometry
        if isinstance(geometry, AgsiGeometryFromFile):
            files.append(("geometry", geometry))
        elif isinstance(geometry, (AgsiGeometryAreaFromLines, AgsiGeometryVolFromSurfaces)):
            for role, child in (("top", geometry.agsi_geometry_top), ("bottom", geometry.agsi_geometry_bottom)):
                if isinstance(child, AgsiGeometryFromFile):
                    files.append((role, child))
        if self.agsi_geometry_area_limit is not None:
            files.append(("area_limit", self.agsi_geometry_area_limit))
        return files


class AgsiModel(AgsiBaseModel):
    model_id: Optional[str] = Field(None, alias="modelID")
    model_name: Optional[str] = None
    description: Optional[str] = None
    coord_system_id: Optional[str] = Field(None, alias="coordSystemID")
    model_type: Optional[str] = None
    category: Optional[str] = None
    domain: Optional[str] = None
    input: Optional[str] = None
    method: Optional[str] = None
    usage: Optional[str] = None
    uncertainty: Optional[str] = None
    document_set_id: Optional[str] = Field(None, alias="documentSetID")
    alignment_id: Optional[str] = Field(None, alias="alignmentID")
    agsi_model_element: list[AgsiModelElement] = Field(default_factory=list)
    agsi_model_boundary: Optional[AgsiModelBoundary] = None
    agsi_model_alignment: list[AgsiModelAlignment] = Field(default_factory=list)
    agsi_observation_set: list[dict[str, Any]] = Field(default_factory=list)
    remarks: Optional[str] = None

    def elements_by_geometry(self, geometry_object: str) -> list[AgsiModelElement]:
        """Elements whose geometry is the given AGSi object, e.g. ``"agsiGeometryAreaFromLines"``."""
        return [e for e in self.agsi_model_element if e.geometry_object_name == geometry_object]


class AgsiDocument(AgsiBaseModel):
    """Root of an AGSi 1.0.x file."""

    ags_schema: Optional[AgsSchema] = None
    ags_file: Optional[AgsFile] = None
    ags_project: Optional[AgsProject] = None
    agsi_model: list[AgsiModel] = Field(default_factory=list)

    def coordinate_system(self, model: Optional[AgsiModel] = None) -> Optional[AgsProjectCoordinateSystem]:
        """Coordinate system for ``model`` (matched on ``coordSystemID``), else the first defined."""
        systems = self.ags_project.ags_project_coordinate_system if self.ags_project else []
        if not systems:
            return None
        if model is not None and model.coord_system_id:
            for system in systems:
                if system.system_id == model.coord_system_id:
                    return system
        return systems[0]
