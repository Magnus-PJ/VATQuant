"""Classic single-frame MR DICOM series loading and integrity checks."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from vatquant_core.errors import SeriesIntegrityError, UnsupportedInputError
from vatquant_core.geometry import ImageGeometry

ENHANCED_MR_SOP_CLASS = "1.2.840.10008.5.1.4.1.1.4.1"
CLASSIC_MR_SOP_CLASS = "1.2.840.10008.5.1.4.1.1.4"


@dataclass
class SeriesHeader:
    path: str
    study_uid: str
    series_uid: str
    sop_uid: str
    sop_class_uid: str
    frame_of_reference_uid: Optional[str]
    manufacturer: Optional[str]
    model: Optional[str]
    field_strength_T: Optional[float]
    series_description: Optional[str]
    image_type: Tuple[str, ...]
    rows: Optional[int]
    columns: Optional[int]
    instance_number: Optional[int]


@dataclass
class SourceRefs:
    study_uid: str
    series_uid: str
    sop_uids: List[str]
    frame_of_reference_uid: Optional[str]
    manufacturer: Optional[str]
    model: Optional[str]
    field_strength_T: Optional[float]
    series_description: Optional[str]
    image_type: Tuple[str, ...]
    file_paths: List[str]
    slice_thickness_mm: Optional[float]
    centre_to_centre_spacing_mm: Optional[float]


@dataclass
class LoadedSeries:
    array: np.ndarray  # (K, J, I) float64 after rescale
    geometry: ImageGeometry
    source_refs: SourceRefs


def _read_header(path: str) -> Tuple[Any, SeriesHeader]:
    import pydicom

    ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
    image_type = tuple(str(x) for x in (getattr(ds, "ImageType", None) or ()))
    fs = getattr(ds, "MagneticFieldStrength", None)
    try:
        fs_f = float(fs) if fs is not None else None
    except (TypeError, ValueError):
        fs_f = None
    header = SeriesHeader(
        path=path,
        study_uid=str(getattr(ds, "StudyInstanceUID", "") or ""),
        series_uid=str(getattr(ds, "SeriesInstanceUID", "") or ""),
        sop_uid=str(getattr(ds, "SOPInstanceUID", "") or ""),
        sop_class_uid=str(getattr(ds, "SOPClassUID", "") or ""),
        frame_of_reference_uid=str(getattr(ds, "FrameOfReferenceUID", "") or "") or None,
        manufacturer=str(getattr(ds, "Manufacturer", "") or "") or None,
        model=str(getattr(ds, "ManufacturerModelName", "") or "") or None,
        field_strength_T=fs_f,
        series_description=str(getattr(ds, "SeriesDescription", "") or "") or None,
        image_type=image_type,
        rows=int(ds.Rows) if hasattr(ds, "Rows") else None,
        columns=int(ds.Columns) if hasattr(ds, "Columns") else None,
        instance_number=int(ds.InstanceNumber) if getattr(ds, "InstanceNumber", None) is not None else None,
    )
    return ds, header


def scan_directory(path: str) -> Dict[str, List[SeriesHeader]]:
    """Group DICOM files under path by SeriesInstanceUID (headers only)."""
    if not os.path.isdir(path):
        raise SeriesIntegrityError("path is not a directory: {}".format(path))
    groups: Dict[str, List[SeriesHeader]] = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            fpath = os.path.join(root, name)
            try:
                _ds, header = _read_header(fpath)
            except Exception:
                continue
            if not header.series_uid:
                continue
            groups.setdefault(header.series_uid, []).append(header)
    return groups


def _iop_normal(iop: Sequence[float]) -> np.ndarray:
    row = np.asarray(iop[:3], dtype=np.float64)
    col = np.asarray(iop[3:6], dtype=np.float64)
    n = np.cross(row, col)
    norm = np.linalg.norm(n)
    if norm < 1e-8:
        raise SeriesIntegrityError("ImageOrientationPatient yields degenerate slice normal")
    return n / norm


def _require_tag(ds: Any, name: str) -> Any:
    if not hasattr(ds, name) or getattr(ds, name) is None:
        raise SeriesIntegrityError("missing required DICOM attribute: {}".format(name))
    return getattr(ds, name)


def load_classic_series(files: Sequence[str]) -> LoadedSeries:
    """Load a classic single-frame MR series with geometry integrity checks."""
    import pydicom

    if not files:
        raise SeriesIntegrityError("no files provided")

    datasets = []
    for fpath in files:
        ds = pydicom.dcmread(fpath, force=True)
        sop_class = str(getattr(ds, "SOPClassUID", "") or "")
        if sop_class == ENHANCED_MR_SOP_CLASS:
            raise UnsupportedInputError(
                "Enhanced MR SOP Class UID is not supported in v1; "
                "provide classic single-frame MR (1.2.840.10008.5.1.4.1.1.4). File: {}".format(fpath)
            )
        datasets.append((fpath, ds))

    # Basic consistency
    study_uids = {str(getattr(ds, "StudyInstanceUID", "")) for _, ds in datasets}
    series_uids = {str(getattr(ds, "SeriesInstanceUID", "")) for _, ds in datasets}
    if len(study_uids) != 1 or not next(iter(study_uids)):
        raise SeriesIntegrityError("files do not share a single StudyInstanceUID")
    if len(series_uids) != 1 or not next(iter(series_uids)):
        raise SeriesIntegrityError("files do not share a single SeriesInstanceUID")

    parsed = []
    for fpath, ds in datasets:
        ipp = np.asarray([float(x) for x in _require_tag(ds, "ImagePositionPatient")], dtype=np.float64)
        iop = [float(x) for x in _require_tag(ds, "ImageOrientationPatient")]
        if len(iop) != 6:
            raise SeriesIntegrityError("ImageOrientationPatient must have 6 elements")
        pixsp = [float(x) for x in _require_tag(ds, "PixelSpacing")]
        if len(pixsp) != 2:
            raise SeriesIntegrityError("PixelSpacing must have 2 elements")
        rows = int(_require_tag(ds, "Rows"))
        cols = int(_require_tag(ds, "Columns"))
        normal = _iop_normal(iop)
        proj = float(np.dot(ipp, normal))
        echo = str(getattr(ds, "EchoNumbers", "") or "")
        acq = getattr(ds, "AcquisitionNumber", None)
        temp = getattr(ds, "TemporalPositionIdentifier", None)
        thickness = float(ds.SliceThickness) if getattr(ds, "SliceThickness", None) is not None else None
        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        pixels = ds.pixel_array.astype(np.float64) * slope + intercept
        parsed.append(
            {
                "path": fpath,
                "ds": ds,
                "ipp": ipp,
                "iop": iop,
                "normal": normal,
                "proj": proj,
                "pixel_spacing": pixsp,
                "rows": rows,
                "cols": cols,
                "echo": echo,
                "acq": acq,
                "temp": temp,
                "thickness": thickness,
                "pixels": pixels,
                "sop_uid": str(getattr(ds, "SOPInstanceUID", "") or ""),
            }
        )

    # Orientation consistency
    ref_iop = np.asarray(parsed[0]["iop"], dtype=np.float64)
    ref_normal = parsed[0]["normal"]
    for p in parsed[1:]:
        if not np.allclose(p["iop"], ref_iop, atol=1e-4):
            raise SeriesIntegrityError("inconsistent ImageOrientationPatient within series")
        if not np.allclose(p["normal"], ref_normal, atol=1e-4):
            raise SeriesIntegrityError("inconsistent slice normals within series")
        if p["rows"] != parsed[0]["rows"] or p["cols"] != parsed[0]["cols"]:
            raise SeriesIntegrityError("inconsistent Rows/Columns within series")
        if not np.allclose(p["pixel_spacing"], parsed[0]["pixel_spacing"], atol=1e-5):
            raise SeriesIntegrityError("inconsistent PixelSpacing within series")

    # Sort by projection along slice normal
    parsed.sort(key=lambda p: p["proj"])

    # Duplicate positions
    projs = [p["proj"] for p in parsed]
    for a, b in zip(projs, projs[1:]):
        if abs(a - b) < 1e-4:
            # Check if mixed echo/phase at same position
            raise SeriesIntegrityError(
                "duplicate or overlapping slice positions detected "
                "(possible mixed echoes/phases or duplicate instances)"
            )

    # Mixed echoes/phases across series (different echo at different positions also flagged)
    echoes = {p["echo"] for p in parsed}
    acqs = {p["acq"] for p in parsed}
    temps = {p["temp"] for p in parsed}
    if len(echoes) > 1:
        raise SeriesIntegrityError("mixed EchoNumbers within series; refusing to load")
    if len(acqs) > 1:
        raise SeriesIntegrityError("mixed AcquisitionNumber within series; refusing to load")
    if len(temps) > 1:
        raise SeriesIntegrityError("mixed TemporalPositionIdentifier within series; refusing to load")

    # Spacing uniformity / missing slices / multi-slab jumps
    if len(parsed) >= 2:
        deltas = np.diff(np.asarray(projs, dtype=np.float64))
        med = float(np.median(deltas))
        if med <= 0:
            raise SeriesIntegrityError("non-positive centre-to-centre spacing")
        # Detect large jumps suggesting multi-slab or missing slices
        for d in deltas:
            if abs(d - med) > max(0.5 * abs(med), 0.5):
                # Large discontinuity
                if d > 1.5 * abs(med):
                    raise UnsupportedInputError(
                        "slice-position discontinuity suggests missing slices or multi-slab "
                        "acquisition; multi-slab stitching is not supported in v1 "
                        "(median step={:.4f} mm, observed={:.4f} mm)".format(med, d)
                    )
                raise SeriesIntegrityError(
                    "non-uniform slice spacing (median={:.4f} mm, observed={:.4f} mm)".format(med, d)
                )
        # Overlapping slab heuristic: negative steps already sorted out; near-zero caught as duplicate
        c2c = abs(med)
    else:
        # Single slice: use SliceThickness if present, else refuse volumetric claims later
        c2c = parsed[0]["thickness"]
        if c2c is None or c2c <= 0:
            raise SeriesIntegrityError(
                "single-slice series lacks usable SliceThickness for K spacing"
            )

    thickness_report = parsed[0]["thickness"]
    dy, dx = parsed[0]["pixel_spacing"]  # row, col
    dz = float(c2c)

    # Direction from IOP: I = row? DICOM IOP: first 3 = row direction (X increasing along columns? )
    # ImageOrientationPatient: direction cosines of the first row (along columns increasing i)
    # and first column (along rows increasing j).
    iop = parsed[0]["iop"]
    dir_i = np.asarray(iop[0:3], dtype=np.float64)
    dir_j = np.asarray(iop[3:6], dtype=np.float64)
    dir_k = _iop_normal(iop)
    # Ensure dir_k points in the direction of increasing projection
    if len(parsed) >= 2:
        delta_ipp = parsed[1]["ipp"] - parsed[0]["ipp"]
        if np.dot(delta_ipp, dir_k) < 0:
            dir_k = -dir_k

    direction = (
        (float(dir_i[0]), float(dir_i[1]), float(dir_i[2])),
        (float(dir_j[0]), float(dir_j[1]), float(dir_j[2])),
        (float(dir_k[0]), float(dir_k[1]), float(dir_k[2])),
    )
    # Orthonormalize columns for ImageGeometry (direction columns = I,J,K)
    dmat = np.column_stack([dir_i, dir_j, dir_k])
    direction = tuple(tuple(float(x) for x in dmat[r, :]) for r in range(3))
    # Wait - ImageGeometry stores direction as rows being the three vectors?
    # In geometry.py: direction columns are I, J, K direction cosines.
    # We stored as Tuple of rows of the matrix D where D[:,0]=I, etc.
    # So direction should be:
    direction = tuple(tuple(float(dmat[r, c]) for c in range(3)) for r in range(3))

    origin = tuple(float(x) for x in parsed[0]["ipp"])
    shape = (len(parsed), parsed[0]["rows"], parsed[0]["cols"])
    spacing = (float(dx), float(dy), float(dz))

    try:
        geometry = ImageGeometry(
            shape=shape,
            spacing=spacing,
            origin_lps=origin,
            direction=direction,
        )
    except Exception as exc:
        raise SeriesIntegrityError("failed to build geometry: {}".format(exc)) from exc

    volume = np.stack([p["pixels"] for p in parsed], axis=0)

    first = datasets[0][1]
    refs = SourceRefs(
        study_uid=str(getattr(first, "StudyInstanceUID", "")),
        series_uid=str(getattr(first, "SeriesInstanceUID", "")),
        sop_uids=[p["sop_uid"] for p in parsed],
        frame_of_reference_uid=str(getattr(first, "FrameOfReferenceUID", "") or "") or None,
        manufacturer=str(getattr(first, "Manufacturer", "") or "") or None,
        model=str(getattr(first, "ManufacturerModelName", "") or "") or None,
        field_strength_T=float(first.MagneticFieldStrength)
        if getattr(first, "MagneticFieldStrength", None) is not None
        else None,
        series_description=str(getattr(first, "SeriesDescription", "") or "") or None,
        image_type=tuple(str(x) for x in (getattr(first, "ImageType", None) or ())),
        file_paths=[p["path"] for p in parsed],
        slice_thickness_mm=thickness_report,
        centre_to_centre_spacing_mm=float(dz),
    )
    return LoadedSeries(array=volume, geometry=geometry, source_refs=refs)


def load_series_from_directory(path: str) -> LoadedSeries:
    """Scan a directory that should contain exactly one classic MR series and load it."""
    groups = scan_directory(path)
    if not groups:
        raise SeriesIntegrityError("no DICOM series found in {}".format(path))
    if len(groups) != 1:
        raise SeriesIntegrityError(
            "expected exactly one series in {}, found {}".format(path, len(groups))
        )
    headers = next(iter(groups.values()))
    return load_classic_series([h.path for h in headers])
