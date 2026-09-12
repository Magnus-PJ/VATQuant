"""Synthetic Dixon phantoms and classic-MR DICOM writers (no PHI)."""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from vatquant_core.geometry import ImageGeometry


@dataclass
class Phantom:
    """Synthetic fat/water volume with known ground-truth masks."""

    fat: np.ndarray
    water: np.ndarray
    geometry: ImageGeometry
    sat_mask: np.ndarray
    vat_mask: np.ndarray
    compartment_mask: np.ndarray
    coverage_mask: np.ndarray
    exclusion_mask: np.ndarray
    candidate_mask: np.ndarray
    expected_vat_voxels: int
    expected_vat_volume_mL: float
    manufacturer: str
    study_uid: str
    fat_series_uid: str
    water_series_uid: str
    frame_of_reference_uid: str


def make_phantom(
    shape: Tuple[int, int, int] = (40, 64, 64),
    spacing: Tuple[float, float, float] = (2.0, 2.0, 5.0),
    manufacturer: str = "GE",
    seed: int = 0,
) -> Phantom:
    """Build a deterministic abdominal Dixon-like phantom.

    Geometry is orthogonal LPS. Outer ring = SAT, inner ellipse blobs = VAT,
    central water organ, vertebral marrow exclusion.
    """
    rng = np.random.default_rng(seed)
    k, j, i = shape
    yy, xx = np.ogrid[:j, :i]
    cy, cx = (j - 1) / 2.0, (i - 1) / 2.0

    def _stack_2d(mask_2d: np.ndarray) -> np.ndarray:
        return np.broadcast_to(mask_2d.astype(bool), shape).copy()

    # Body ellipse (same on every slice)
    body_2d = ((yy - cy) / (j * 0.42)) ** 2 + ((xx - cx) / (i * 0.42)) ** 2 <= 1.0
    compartment_2d = ((yy - cy) / (j * 0.30)) ** 2 + ((xx - cx) / (i * 0.30)) ** 2 <= 1.0
    body = _stack_2d(body_2d)
    compartment = _stack_2d(compartment_2d)
    # SAT = body minus compartment
    sat = body & (~compartment)
    # Coverage = body voxels across the full stack
    coverage = body.copy()

    # VAT blobs inside compartment
    blob1_2d = ((yy - cy + j * 0.08) / (j * 0.10)) ** 2 + ((xx - cx - i * 0.05) / (i * 0.12)) ** 2 <= 1.0
    blob2_2d = ((yy - cy - j * 0.05) / (j * 0.08)) ** 2 + ((xx - cx + i * 0.08) / (i * 0.09)) ** 2 <= 1.0
    vat = _stack_2d((blob1_2d | blob2_2d) & compartment_2d)

    # Organ water region (should not be VAT)
    organ_2d = ((yy - cy) / (j * 0.08)) ** 2 + ((xx - cx) / (i * 0.08)) ** 2 <= 1.0
    organ = _stack_2d(organ_2d & compartment_2d)
    vat = vat & (~organ)

    # Vertebral marrow exclusion (bright fat-like but excluded)
    marrow_2d = (np.abs(yy - cy) < j * 0.04) & (np.abs(xx - cx) < i * 0.05) & body_2d
    marrow = _stack_2d(marrow_2d)
    exclusion = marrow | organ
    vat = vat & (~exclusion)

    # Candidate adipose = SAT + VAT + marrow (threshold-like proposal before exclusions)
    candidate = sat | vat | marrow

    fat = np.zeros(shape, dtype=np.float32)
    water = np.zeros(shape, dtype=np.float32)
    fat[sat | vat | marrow] = 800.0 + rng.normal(0, 5, size=np.count_nonzero(sat | vat | marrow)).astype(
        np.float32
    )
    water[organ] = 900.0
    water[body & ~(sat | vat | marrow | organ)] = 200.0
    # Background noise
    fat += rng.normal(0, 1, size=shape).astype(np.float32)
    water += rng.normal(0, 1, size=shape).astype(np.float32)
    fat = np.clip(fat, 0, None)
    water = np.clip(water, 0, None)

    geom = ImageGeometry.orthogonal(shape=shape, spacing=spacing, origin_lps=(0.0, 0.0, 0.0))
    n_vat = int(np.count_nonzero(vat))
    vol_ml = n_vat * geom.voxel_volume_mm3() / 1000.0

    uid_root = "2.25.{}".format(uuid.uuid4().int)
    return Phantom(
        fat=fat,
        water=water,
        geometry=geom,
        sat_mask=sat,
        vat_mask=vat,
        compartment_mask=compartment,
        coverage_mask=coverage,
        exclusion_mask=exclusion,
        candidate_mask=candidate,
        expected_vat_voxels=n_vat,
        expected_vat_volume_mL=vol_ml,
        manufacturer=manufacturer,
        study_uid=uid_root + ".1",
        fat_series_uid=uid_root + ".2",
        water_series_uid=uid_root + ".3",
        frame_of_reference_uid=uid_root + ".4",
    )


def _base_ds(
    *,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
    frame_uid: str,
    manufacturer: str,
    series_description: str,
    image_type: Sequence[str],
    rows: int,
    cols: int,
    spacing: Tuple[float, float, float],
    ipp: Tuple[float, float, float],
    iop: Sequence[float],
    instance_number: int,
    slice_thickness: float,
    echo_number: int = 1,
    acquisition_number: int = 1,
    temporal_position: int = 1,
    sop_class_uid: str = "1.2.840.10008.5.1.4.1.1.4",
    model_name: str = "SYNTHETIC_VATQUANT",
    field_strength: float = 1.5,
):
    import pydicom
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = Dataset()
    ds.file_meta = file_meta
    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.FrameOfReferenceUID = frame_uid
    ds.Modality = "MR"
    ds.Manufacturer = manufacturer
    ds.ManufacturerModelName = model_name
    ds.MagneticFieldStrength = field_strength
    ds.PatientName = "VATQUANT^SYNTHETIC"
    ds.PatientID = "SYNTH-0000"
    ds.PatientBirthDate = ""
    ds.PatientSex = "O"
    ds.StudyDate = "20260101"
    ds.SeriesDate = "20260101"
    ds.ContentDate = "20260101"
    ds.StudyTime = "120000"
    ds.SeriesTime = "120000"
    ds.ContentTime = "120000"
    ds.SeriesDescription = series_description
    ds.SeriesNumber = 1
    ds.InstanceNumber = instance_number
    ds.ImageType = list(image_type)
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelSpacing = [float(spacing[1]), float(spacing[0])]  # row, col = dy, dx
    ds.SliceThickness = float(slice_thickness)
    ds.ImagePositionPatient = [float(x) for x in ipp]
    ds.ImageOrientationPatient = [float(x) for x in iop]
    ds.EchoNumbers = str(echo_number)
    ds.AcquisitionNumber = acquisition_number
    ds.TemporalPositionIdentifier = temporal_position
    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = 0.0
    ds.SpecificCharacterSet = "ISO_IR 100"
    return ds


def write_synthetic_dicom_series(
    phantom: Phantom,
    out_dir: str,
    channel: str = "fat",
    filename_prefix: str = "IM",
    reverse_order: bool = False,
    shuffle_names: bool = False,
    drop_slice_index: Optional[int] = None,
    duplicate_slice_index: Optional[int] = None,
    mixed_echo_on_slice: Optional[int] = None,
    enhanced_mr: bool = False,
    slab_offset_mm: Optional[float] = None,
    spacing_override: Optional[Tuple[float, float, float]] = None,
    series_uid_override: Optional[str] = None,
    study_uid_override: Optional[str] = None,
    frame_uid_override: Optional[str] = None,
) -> List[str]:
    """Write a classic single-frame MR series from a phantom channel.

    Returns list of written file paths.
    """
    import pydicom

    os.makedirs(out_dir, exist_ok=True)
    if channel == "fat":
        vol = phantom.fat
        series_uid = series_uid_override or phantom.fat_series_uid
        desc = "LAVA Flex FAT" if phantom.manufacturer.upper().startswith("GE") else "VIBE Dixon FAT"
        image_type = ["DERIVED", "PRIMARY", "FAT"]
    elif channel == "water":
        vol = phantom.water
        series_uid = series_uid_override or phantom.water_series_uid
        desc = "LAVA Flex WATER" if phantom.manufacturer.upper().startswith("GE") else "VIBE Dixon WATER"
        image_type = ["DERIVED", "PRIMARY", "WATER"]
    else:
        raise ValueError("channel must be 'fat' or 'water'")

    spacing = spacing_override or phantom.geometry.spacing
    study_uid = study_uid_override or phantom.study_uid
    frame_uid = frame_uid_override or phantom.frame_of_reference_uid
    k, j, i = vol.shape
    iop = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    sop_class = (
        "1.2.840.10008.5.1.4.1.1.4.1" if enhanced_mr else "1.2.840.10008.5.1.4.1.1.4"
    )

    indices = list(range(k))
    if reverse_order:
        indices = list(reversed(indices))

    paths: List[str] = []
    written_meta: List[Tuple[int, str]] = []

    for write_n, slice_idx in enumerate(indices):
        if drop_slice_index is not None and slice_idx == drop_slice_index:
            continue
        z = float(slice_idx) * float(spacing[2])
        if slab_offset_mm is not None:
            z = z + float(slab_offset_mm)
        ipp = (0.0, 0.0, z)
        sop_uid = "2.25.{}".format(uuid.uuid4().int)
        echo = 2 if (mixed_echo_on_slice is not None and slice_idx == mixed_echo_on_slice) else 1
        ds = _base_ds(
            study_uid=study_uid,
            series_uid=series_uid,
            sop_uid=sop_uid,
            frame_uid=frame_uid,
            manufacturer=phantom.manufacturer,
            series_description=desc,
            image_type=image_type,
            rows=j,
            cols=i,
            spacing=spacing,
            ipp=ipp,
            iop=iop,
            instance_number=write_n + 1,
            slice_thickness=float(spacing[2]),
            echo_number=echo,
            sop_class_uid=sop_class,
            field_strength=1.5 if phantom.manufacturer.upper().startswith("GE") else 0.55,
            model_name="SIGNA Creator" if phantom.manufacturer.upper().startswith("GE") else "MAGNETOM Free.Max",
        )
        pixels = np.clip(vol[slice_idx], 0, 65535).astype(np.uint16)
        ds.PixelData = pixels.tobytes()
        fname = "{}_{:04d}.dcm".format(filename_prefix, write_n)
        fpath = os.path.join(out_dir, fname)
        ds.save_as(fpath, enforce_file_format=True)
        paths.append(fpath)
        written_meta.append((slice_idx, fpath))

        if duplicate_slice_index is not None and slice_idx == duplicate_slice_index:
            sop_uid2 = "2.25.{}".format(uuid.uuid4().int)
            ds2 = _base_ds(
                study_uid=study_uid,
                series_uid=series_uid,
                sop_uid=sop_uid2,
                frame_uid=frame_uid,
                manufacturer=phantom.manufacturer,
                series_description=desc,
                image_type=image_type,
                rows=j,
                cols=i,
                spacing=spacing,
                ipp=ipp,
                iop=iop,
                instance_number=write_n + 1000,
                slice_thickness=float(spacing[2]),
                echo_number=1,
                sop_class_uid=sop_class,
            )
            ds2.PixelData = pixels.tobytes()
            fpath2 = os.path.join(out_dir, "{}_{:04d}_dup.dcm".format(filename_prefix, write_n))
            ds2.save_as(fpath2, enforce_file_format=True)
            paths.append(fpath2)

    if shuffle_names:
        # Rename files so InstanceNumber / filename order differs from spatial order
        tmp_dir = out_dir + "_shuffle_tmp"
        os.makedirs(tmp_dir, exist_ok=True)
        rng = np.random.default_rng(42)
        order = rng.permutation(len(paths))
        new_paths = []
        for new_i, old_i in enumerate(order):
            src = paths[old_i]
            dst = os.path.join(out_dir, "SHUF_{:04d}.dcm".format(new_i))
            # Move via temp to avoid overwrite collisions
            mid = os.path.join(tmp_dir, os.path.basename(src))
            shutil.move(src, mid)
            shutil.move(mid, dst)
            new_paths.append(dst)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # Remove any leftover original names
        for p in list(paths):
            if os.path.isfile(p) and p not in new_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
        paths = new_paths

    return paths


def write_paired_case(
    out_root: str,
    manufacturer: str = "GE",
    shape: Tuple[int, int, int] = (20, 48, 48),
    spacing: Tuple[float, float, float] = (2.0, 2.0, 5.0),
    seed: int = 0,
) -> Dict[str, object]:
    """Write a paired fat/water synthetic DICOM case. Returns metadata dict."""
    phantom = make_phantom(shape=shape, spacing=spacing, manufacturer=manufacturer, seed=seed)
    fat_dir = os.path.join(out_root, "FAT")
    water_dir = os.path.join(out_root, "WATER")
    fat_files = write_synthetic_dicom_series(phantom, fat_dir, channel="fat")
    water_files = write_synthetic_dicom_series(phantom, water_dir, channel="water")
    # Save ground-truth masks as npy for e2e tests
    np.savez_compressed(
        os.path.join(out_root, "ground_truth.npz"),
        vat=phantom.vat_mask,
        candidate=phantom.candidate_mask,
        compartment=phantom.compartment_mask,
        coverage=phantom.coverage_mask,
        exclusion=phantom.exclusion_mask,
        fat=phantom.fat,
        water=phantom.water,
    )
    meta = {
        "phantom": phantom,
        "fat_dir": fat_dir,
        "water_dir": water_dir,
        "fat_files": fat_files,
        "water_files": water_files,
        "expected_vat_voxels": phantom.expected_vat_voxels,
        "expected_vat_volume_mL": phantom.expected_vat_volume_mL,
    }
    return meta
