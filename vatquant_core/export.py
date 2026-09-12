"""JSON/CSV metrics export and mask I/O with provenance."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import SimpleITK as sitk

from vatquant_core.errors import GeometryError, QCBlockedError
from vatquant_core.geometry import ImageGeometry
from vatquant_core.masks import numpy_to_sitk, sitk_to_numpy
from vatquant_core.qc import CaseRecord
from vatquant_core.version import ALGORITHM_VERSION, __version__


@dataclass
class MetricsRecord:
    schema_version: str = "1.0"
    case_id: Optional[str] = None
    source_series: List[Dict[str, Any]] = field(default_factory=list)
    scanner: Dict[str, Any] = field(default_factory=lambda: {
        "manufacturer": None,
        "model": None,
        "field_strength_T": None,
    })
    protocol_id: Optional[str] = None
    acquisition_coverage: Optional[str] = None
    analysis_roi_definition: Optional[str] = None
    retroperitoneal_fat_rule: Optional[str] = None
    measurement_grid: Dict[str, Any] = field(default_factory=lambda: {
        "shape": None,
        "affine_mm": None,
    })
    vat_volume_mL: Optional[float] = None
    vat_volume_L: Optional[float] = None
    vat_area_L3_cm2: Optional[float] = None
    l3_plane_definition: Optional[str] = None
    qc_flags: List[str] = field(default_factory=list)
    review_status: str = "QC_PENDING"
    reviewer_id: Optional[str] = None
    review_timestamp: Optional[str] = None
    software_version: Optional[str] = None
    algorithm_version: Optional[str] = None
    model_weights_hash: Optional[str] = None
    analysis_parameters: Dict[str, Any] = field(default_factory=dict)
    intended_use_status: str = "development_evaluation"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def metrics_from_case(
    case: CaseRecord,
    geometry: Optional[ImageGeometry] = None,
    acquisition_coverage: Optional[str] = None,
) -> MetricsRecord:
    grid: Dict[str, Any] = {"shape": None, "affine_mm": None}
    if geometry is not None:
        grid = {
            "shape": list(geometry.shape),
            "affine_mm": geometry.affine_mm().tolist(),
        }
    vol_ml = case.volume_result.volume_mL if case.volume_result else None
    vol_l = case.volume_result.volume_L if case.volume_result else None
    area = case.area_result.area_cm2 if case.area_result else None
    l3_def = case.area_result.plane_definition if case.area_result else None
    return MetricsRecord(
        case_id=case.case_id,
        source_series=list(case.source_series),
        scanner=dict(case.scanner) if case.scanner else {
            "manufacturer": None,
            "model": None,
            "field_strength_T": None,
        },
        protocol_id=case.protocol_id,
        acquisition_coverage=acquisition_coverage,
        analysis_roi_definition=case.analysis_roi_definition,
        retroperitoneal_fat_rule=case.retroperitoneal_fat_rule,
        measurement_grid=grid,
        vat_volume_mL=vol_ml,
        vat_volume_L=vol_l,
        vat_area_L3_cm2=area,
        l3_plane_definition=l3_def,
        qc_flags=list(case.qc_flags),
        review_status=case.state.value,
        reviewer_id=case.reviewer_id,
        review_timestamp=case.review_timestamp,
        software_version=__version__,
        algorithm_version=ALGORITHM_VERSION,
        model_weights_hash=None,
        analysis_parameters=dict(case.analysis_parameters),
        intended_use_status="development_evaluation",
    )


def write_json(record: MetricsRecord, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record.to_dict(), f, indent=2, allow_nan=False)
        f.write("\n")


def read_json(path: str) -> MetricsRecord:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return MetricsRecord(**data)


def write_csv_row(record: MetricsRecord, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    row = {
        "case_id": record.case_id,
        "vat_volume_mL": record.vat_volume_mL,
        "vat_volume_L": record.vat_volume_L,
        "vat_area_L3_cm2": record.vat_area_L3_cm2,
        "review_status": record.review_status,
        "reviewer_id": record.reviewer_id,
        "software_version": record.software_version,
        "algorithm_version": record.algorithm_version,
        "intended_use_status": record.intended_use_status,
        "protocol_id": record.protocol_id,
    }
    write_header = not os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def save_mask_nrrd(mask: np.ndarray, geometry: ImageGeometry, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    img = numpy_to_sitk(mask.astype(np.uint8, copy=False), geometry)
    sitk.WriteImage(img, path)


def save_mask_nifti(mask: np.ndarray, geometry: ImageGeometry, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    img = numpy_to_sitk(mask.astype(np.uint8, copy=False), geometry)
    sitk.WriteImage(img, path)


def load_mask(path: str) -> Tuple[np.ndarray, ImageGeometry]:
    img = sitk.ReadImage(path)
    geom = ImageGeometry.from_sitk(img)
    arr = sitk_to_numpy(img).astype(bool)
    if arr.shape != geom.shape:
        raise GeometryError("loaded mask shape does not match geometry")
    return arr, geom


def export_case_bundle(
    case: CaseRecord,
    geometry: ImageGeometry,
    vat_mask: np.ndarray,
    out_dir: str,
    require_final: bool = True,
) -> Dict[str, str]:
    """Write JSON, CSV, and NRRD mask for a case."""
    if require_final:
        case.require_export_final()
    os.makedirs(out_dir, exist_ok=True)
    record = metrics_from_case(case, geometry=geometry)
    json_path = os.path.join(out_dir, "{}_metrics.json".format(case.case_id))
    csv_path = os.path.join(out_dir, "{}_summary.csv".format(case.case_id))
    mask_path = os.path.join(out_dir, "{}_vat.nrrd".format(case.case_id))
    write_json(record, json_path)
    write_csv_row(record, csv_path)
    save_mask_nrrd(vat_mask, geometry, mask_path)
    return {"json": json_path, "csv": csv_path, "mask": mask_path}
