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

import logging
import os
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

import numpy as np
import numpy.typing as npt
import pyarrow as pa
from evo_schemas import DownholeCollection_V1_3_1 as DownholeCollection
from evo_schemas.components import (
    AttributeDescription_V1_0_1 as AttributeDescription,
)
from evo_schemas.components import (
    BoundingBox_V1_0_1 as BoundingBox,
)
from evo_schemas.components import (
    CategoryData_V1_0_1 as CategoryData,
)
from evo_schemas.components import (
    ContinuousAttribute_V1_1_0 as ContinuousAttribute,
)
from evo_schemas.components import (
    Crs_V1_0_1 as Crs,
)
from evo_schemas.components import (
    DesurveyMethod_V1_0_0 as DesurveyMethod,
)
from evo_schemas.components import (
    DistanceTable_V1_2_0_Distance as DistanceTableDistance,
)
from evo_schemas.components import (
    DownholeAttributes_V1_0_0_Item_DistanceTable as DistanceTable,
)
from evo_schemas.components import CategoryAttribute_V1_1_0 as CategoryAttribute
from evo_schemas.components import NanCategorical_V1_0_1 as NanCategorical
from evo_schemas.objects import (
    DownholeCollection_V1_3_1_Location as Location,
)
from evo_schemas.objects import Pointset_V1_2_0 as Pointset
from evo_schemas.objects import Pointset_V1_2_0_Locations as PointsetLocations
from evo_schemas.components import (
    DownholeDirectionVector_V1_0_0 as DownholeDirectionVector,
)
from evo_schemas.components import (
    HoleChunks_V1_0_0 as HoleChunks,
)
from evo_schemas.components import (
    NanContinuous_V1_0_1 as NanContinuous,
)
from evo_schemas.elements import (
    FloatArray1_V1_0_1 as FloatArray1,
)
from evo_schemas.elements import (
    FloatArray3_V1_0_1 as FloatArray3,
)
from evo_schemas.elements import (
    IntegerArray1_V1_0_1 as IntegerArray1,
)
from evo_schemas.elements import (
    LookupTable_V1_0_1 as LookupTable,
)
from evo_schemas.elements import (
    UnitLength_V1_0_1_UnitCategories as UnitLength,
)

from evo.data_converters.las.importer.dev_reader import DeviationSurvey, read_dev_file
from evo.data_converters.las.importer.las_reader import LASFile, LASInvalidDataError, read_las_file
from evo.objects.utils.data import ObjectDataClient

logger = logging.getLogger("data_converters.las")

DeviationFiles = Mapping[str, str | os.PathLike] | Sequence[str | os.PathLike] | str | os.PathLike


def get_geoscience_object_from_las(
    data_client: ObjectDataClient,
    filepaths: str | os.PathLike | Sequence[str | os.PathLike],
    coordinate_reference_system: Crs,
    tags: Optional[dict[str, str]] = None,
    *,
    deviation_files: Optional[DeviationFiles] = None,
    allow_missing_deviation: bool = False,
    collection_name: Optional[str] = None,
) -> list[DownholeCollection | Pointset]:
    """Build a downhole collection and a point set from one or more LAS 2.0 files, one hole per file.

    :param data_client: Client used to upload referenced data.
    :param filepaths: Path, or paths, of the LAS files to convert.
    :param coordinate_reference_system: The CRS to assign to the created object.
    :param tags: (Optional) Additional tags to attach to the object.
    :param deviation_files: (Optional) Petrel deviation (.dev) files providing each hole's collar and survey: a
        directory, a list of files, or a mapping of hole id to file. Files are matched to holes by well name.
        Without them each hole gets a collar at (0, 0, 0) and a vertical path.
    :param allow_missing_deviation: If True, holes without a matching deviation file get the default collar and
        vertical path instead of raising an error.
    :param collection_name: (Optional) Name of the object. Defaults to the file name, or a generic name for many files.
    :raise LASInvalidDataError: If a file is invalid, hole ids are duplicated or a deviation file is missing.
    """
    if isinstance(filepaths, (str, os.PathLike)):
        filepaths = [filepaths]
    if not filepaths:
        raise ValueError("At least one LAS file is required")

    las_files = [read_las_file(path) for path in filepaths]
    hole_ids = [las.hole_id for las in las_files]
    if len({h.lower() for h in hole_ids}) != len(hole_ids):
        duplicates = sorted({h for h in hole_ids if [x.lower() for x in hole_ids].count(h.lower()) > 1})
        raise LASInvalidDataError(f"Duplicate hole ids across LAS files: {', '.join(duplicates)}")

    deviations = _load_deviations(deviation_files)
    holes = [_build_hole(las, deviations, deviation_files is not None, allow_missing_deviation) for las in las_files]

    positions = [_desurvey(h["collar"], h["survey"], h["final_depth"]) for h in holes]
    all_positions = np.vstack(positions)
    mins, maxs = all_positions.min(axis=0), all_positions.max(axis=0)
    bounding_box = BoundingBox(
        min_x=float(mins[0]),
        max_x=float(maxs[0]),
        min_y=float(mins[1]),
        max_y=float(maxs[1]),
        min_z=float(mins[2]),
        max_z=float(maxs[2]),
    )

    location = Location(
        coordinates=_float_array_3(data_client, [h["collar"] for h in holes], ("x", "y", "z")),
        distances=_float_array_3(data_client, [(h["final_depth"],) * 3 for h in holes], ("final", "target", "current")),
        holes=_hole_chunks(data_client, [len(h["survey"]) for h in holes]),
        hole_id=_hole_id_category(data_client, hole_ids),
        path=DownholeDirectionVector.from_dict(
            data_client.save_table(_table(np.vstack([h["survey"] for h in holes]), ("distance", "azimuth", "dip")))
        ),
    )

    object_tags = {"Source": f"{_source_description(filepaths)} (via Evo Data Converters)"}
    object_tags.update({"Stage": "Experimental", "InputType": "LAS"})
    if tags:
        object_tags.update(tags)

    name = collection_name or _default_name(filepaths)
    collection = DownholeCollection(
        name=name,
        uuid=None,
        bounding_box=bounding_box,
        coordinate_reference_system=coordinate_reference_system,
        tags=object_tags,
        distance_unit=UnitLength.Unit_m,
        desurvey=DesurveyMethod.ENUM_MINIMUM_CURVATURE,
        location=location,
        collections=[_logs_collection(data_client, las_files)],
    )
    pointset = _pointset(data_client, f"{name} points", las_files, holes, coordinate_reference_system, object_tags)
    return [collection, pointset]


def _source_description(filepaths: Sequence[str | os.PathLike]) -> str:
    names = [os.path.basename(os.fspath(p)) for p in filepaths]
    return names[0] if len(names) == 1 else f"{len(names)} LAS files"


def _default_name(filepaths: Sequence[str | os.PathLike]) -> str:
    if len(filepaths) == 1:
        return Path(os.fspath(filepaths[0])).stem
    return "LAS downhole collection"


def _load_deviations(deviation_files: Optional[DeviationFiles]) -> dict[str, DeviationSurvey]:
    """Index deviation surveys by lower-cased hole id."""
    if deviation_files is None:
        return {}
    deviations: dict[str, DeviationSurvey] = {}

    def register(key: str, survey: DeviationSurvey) -> None:
        existing = deviations.get(key.lower())
        if existing is not None and existing.filepath != survey.filepath:
            raise LASInvalidDataError(
                f"Deviation files '{existing.filepath}' and '{survey.filepath}' both match hole '{key}'"
            )
        deviations[key.lower()] = survey

    if isinstance(deviation_files, Mapping):
        for hole_id, path in deviation_files.items():
            register(hole_id, read_dev_file(path))
        return deviations

    if isinstance(deviation_files, (str, os.PathLike)):
        path = Path(os.fspath(deviation_files))
        paths = sorted(p for p in path.iterdir() if p.suffix.lower() == ".dev") if path.is_dir() else [path]
    else:
        paths = [Path(os.fspath(p)) for p in deviation_files]
    for path in paths:
        survey = read_dev_file(path)
        register(survey.well_name, survey)
        if survey.well_name.lower() != path.stem.lower():
            deviations.setdefault(path.stem.lower(), survey)
    return deviations


def _build_hole(
    las: LASFile, deviations: dict[str, DeviationSurvey], deviations_supplied: bool, allow_missing: bool
) -> dict:
    max_depth = float(las.depth_in_metres.max())
    deviation = deviations.get(las.hole_id.lower())
    if deviation is None:
        if deviations_supplied and not allow_missing:
            raise LASInvalidDataError(
                f"No deviation file found for hole '{las.hole_id}'; supply one or set allow_missing_deviation=True"
            )
        logger.warning(f"No deviation file for hole '{las.hole_id}', using a collar at (0, 0, 0) and a vertical path")
        collar: tuple[float, float, float] = (0.0, 0.0, 0.0)
        survey = np.array([[0.0, 0.0, 90.0], [max_depth, 0.0, 90.0]])
    else:
        collar, survey = deviation.collar, deviation.survey
    return {
        "collar": collar,
        "survey": survey,
        "final_depth": max(max_depth, float(survey[-1, 0])),
        "las": las,
    }


def _mc_step(dl: Any, i1: Any, a1: Any, i2: Any, a2: Any) -> tuple[Any, Any, Any]:
    """Minimum curvature displacement (east, north, down); inclination is from vertical, azimuth from north."""
    beta = np.arccos(np.clip(np.cos(i1) * np.cos(i2) + np.sin(i1) * np.sin(i2) * np.cos(a2 - a1), -1.0, 1.0))
    safe_beta = np.where(beta < 1e-9, 1.0, beta)
    ratio = np.where(beta < 1e-9, 1.0, 2.0 / safe_beta * np.tan(safe_beta / 2.0))
    north = dl / 2 * (np.sin(i1) * np.cos(a1) + np.sin(i2) * np.cos(a2)) * ratio
    east = dl / 2 * (np.sin(i1) * np.sin(a1) + np.sin(i2) * np.sin(a2)) * ratio
    down = dl / 2 * (np.cos(i1) + np.cos(i2)) * ratio
    return east, north, down


def _extended_survey(survey: npt.NDArray[np.float64], final_depth: float) -> npt.NDArray[np.float64]:
    if survey[-1, 0] < final_depth:
        return np.vstack([survey, [final_depth, survey[-1, 1], survey[-1, 2]]])
    return survey


def _desurvey(
    collar: tuple[float, float, float], survey: npt.NDArray[np.float64], final_depth: float
) -> npt.NDArray[np.float64]:
    """Minimum curvature positions (x, y, elevation) of the survey stations and the end of the hole."""
    survey = _extended_survey(survey, final_depth)
    md = survey[:, 0]
    azimuth = np.radians(survey[:, 1])
    incl = np.radians(90.0 - survey[:, 2])
    positions = np.empty((len(survey), 3))
    positions[0] = collar
    for i in range(1, len(survey)):
        east, north, down = _mc_step(md[i] - md[i - 1], incl[i - 1], azimuth[i - 1], incl[i], azimuth[i])
        positions[i] = positions[i - 1] + [east, north, -down]
    return positions


def _positions_at(
    collar: tuple[float, float, float],
    survey: npt.NDArray[np.float64],
    final_depth: float,
    depths: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Minimum curvature (x, y, elevation) at arbitrary measured depths along the trajectory."""
    survey = _extended_survey(survey, final_depth)
    stations = _desurvey(collar, survey, final_depth)
    md = survey[:, 0]
    azimuth = np.radians(survey[:, 1])
    incl = np.radians(90.0 - survey[:, 2])
    if len(md) == 1:
        return np.tile(stations[0], (len(depths), 1))
    idx = np.clip(np.searchsorted(md, depths, side="right") - 1, 0, len(md) - 2)
    seg = md[idx + 1] - md[idx]
    t = np.clip(np.divide(depths - md[idx], seg, out=np.zeros(len(depths)), where=seg > 0), 0.0, None)

    def unit(i: Any, a: Any) -> npt.NDArray[np.float64]:
        return np.stack([np.sin(i) * np.sin(a), np.sin(i) * np.cos(a), np.cos(i)], axis=1)

    vec = (1 - t)[:, None] * unit(incl[idx], azimuth[idx]) + t[:, None] * unit(incl[idx + 1], azimuth[idx + 1])
    norm = np.linalg.norm(vec, axis=1)
    vec = vec / np.where(norm > 0, norm, 1.0)[:, None]
    incl_d = np.arccos(np.clip(vec[:, 2], -1.0, 1.0))
    azimuth_d = np.arctan2(vec[:, 0], vec[:, 1])
    east, north, down = _mc_step(depths - md[idx], incl[idx], azimuth[idx], incl_d, azimuth_d)
    return np.asarray(stations[idx] + np.stack([east, north, -down], axis=1), dtype=np.float64)


def _table(values: npt.NDArray[np.float64], names: Sequence[str]) -> pa.Table:
    return pa.table({name: pa.array(values[:, i], type=pa.float64()) for i, name in enumerate(names)})


def _float_array_3(
    data_client: ObjectDataClient, rows: Sequence[Sequence[float]] | npt.NDArray[np.float64], names: Sequence[str]
) -> FloatArray3:
    return FloatArray3.from_dict(data_client.save_table(_table(np.asarray(rows, dtype=np.float64), names)))


def _hole_chunks(data_client: ObjectDataClient, counts: Sequence[int]) -> HoleChunks:
    counts_array = np.asarray(counts, dtype=np.uint64)
    offsets = np.concatenate([[0], np.cumsum(counts_array)[:-1]]).astype(np.uint64)
    table = pa.table(
        {
            "hole_index": pa.array(np.arange(len(counts), dtype=np.int32), type=pa.int32()),
            "offset": pa.array(offsets, type=pa.uint64()),
            "count": pa.array(counts_array, type=pa.uint64()),
        }
    )
    return HoleChunks.from_dict(data_client.save_table(table))


def _hole_id_category(data_client: ObjectDataClient, hole_ids: Sequence[str]) -> CategoryData:
    keys = np.arange(len(hole_ids), dtype=np.int64)
    lookup = pa.table({"key": pa.array(keys, type=pa.int64()), "value": pa.array(hole_ids, type=pa.string())})
    values = pa.table({"data": pa.array(keys, type=pa.int64())})
    return CategoryData(
        table=LookupTable.from_dict(data_client.save_table(lookup)),
        values=IntegerArray1.from_dict(data_client.save_table(values)),
    )


def _continuous_attributes(data_client: ObjectDataClient, las_files: Sequence[LASFile]) -> list[ContinuousAttribute]:
    """One attribute per curve (union over files, NaN where a file lacks it), rows concatenated in file order."""
    total = sum(len(las.index) for las in las_files)
    offsets = np.concatenate([[0], np.cumsum([len(las.index) for las in las_files])])

    curves: dict[str, tuple[str, str]] = {}  # mnemonic -> (unit, description) of the first file defining it
    for las in las_files:
        for curve in las.curves[1:]:
            curves.setdefault(curve.mnemonic, (curve.unit, curve.description))

    attributes = []
    for mnemonic, (unit, description) in curves.items():
        values = np.full(total, np.nan)
        for las, start in zip(las_files, offsets):
            names = [c.mnemonic for c in las.curves]
            if mnemonic in names:
                values[start : start + len(las.index)] = las.data[:, names.index(mnemonic)]
        if np.isnan(values).all():
            logger.warning(f"Skipping curve '{mnemonic}' as it contains no data")
            continue
        curve_tags = {"LAS mnemonic": mnemonic}
        if unit:
            curve_tags["unit"] = unit
        if description:
            curve_tags["description"] = description
        attributes.append(
            ContinuousAttribute(
                name=mnemonic,
                key=str(uuid.uuid4()),
                attribute_description=AttributeDescription(discipline="None", type=mnemonic, tags=curve_tags),
                nan_description=NanContinuous(values=[]),
                values=FloatArray1.from_dict(
                    data_client.save_table(pa.table({"data": pa.array(values, type=pa.float64())}))
                ),
            )
        )
    return attributes


def _logs_collection(data_client: ObjectDataClient, las_files: Sequence[LASFile]) -> DistanceTable:
    """One depth-indexed table holding every curve of every file; curves missing from a file are null."""
    depths = np.concatenate([las.depth_in_metres for las in las_files])
    return DistanceTable(
        name="Well logs",
        distance=DistanceTableDistance(
            values=FloatArray1.from_dict(
                data_client.save_table(pa.table({"data": pa.array(depths, type=pa.float64())}))
            ),
            unit=UnitLength.Unit_m,
            attributes=_continuous_attributes(data_client, las_files),
        ),
        holes=_hole_chunks(data_client, [len(las.index) for las in las_files]),
    )


def _pointset(
    data_client: ObjectDataClient,
    name: str,
    las_files: Sequence[LASFile],
    holes: Sequence[dict[str, Any]],
    crs: Crs,
    tags: dict[str, str],
) -> Pointset:
    """A point per LAS sample, located by interpolating the hole trajectory at the sample depth."""
    xyz = np.vstack(
        [
            _positions_at(h["collar"], h["survey"], h["final_depth"], las.depth_in_metres)
            for h, las in zip(holes, las_files)
        ]
    )
    mins, maxs = xyz.min(axis=0), xyz.max(axis=0)
    hole_keys = np.concatenate([np.full(len(las.index), i, dtype=np.int64) for i, las in enumerate(las_files)])
    holeid = CategoryAttribute(
        name="holeid",
        key=str(uuid.uuid4()),
        nan_description=NanCategorical(values=[]),
        table=LookupTable.from_dict(
            data_client.save_table(
                pa.table(
                    {
                        "key": pa.array(np.arange(len(las_files), dtype=np.int64), type=pa.int64()),
                        "value": pa.array([las.hole_id for las in las_files], type=pa.string()),
                    }
                )
            )
        ),
        values=IntegerArray1.from_dict(
            data_client.save_table(pa.table({"data": pa.array(hole_keys, type=pa.int64())}))
        ),
    )
    return Pointset(
        name=name,
        uuid=None,
        bounding_box=BoundingBox(
            min_x=float(mins[0]),
            max_x=float(maxs[0]),
            min_y=float(mins[1]),
            max_y=float(maxs[1]),
            min_z=float(mins[2]),
            max_z=float(maxs[2]),
        ),
        coordinate_reference_system=crs,
        tags=tags,
        locations=PointsetLocations(
            coordinates=_float_array_3(data_client, xyz, ("x", "y", "z")),
            attributes=[holeid, *_continuous_attributes(data_client, las_files)],
        ),
    )
