"""VAT volume and area measurement from reviewed binary labelmaps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from vatquant_core.errors import GeometryError
from vatquant_core.geometry import ImageGeometry


@dataclass(frozen=True)
class VolumeResult:
    voxel_count: int
    voxel_volume_mm3: float
    volume_mL: float
    volume_L: float
    geometry_hash: str


@dataclass(frozen=True)
class AreaResult:
    pixel_count: int
    pixel_area_mm2: float
    area_cm2: float
    plane_index: int
    plane_definition: str
    geometry_hash: str


def measure_volume(mask: np.ndarray, geometry: ImageGeometry) -> VolumeResult:
    """Compute VAT volume from a binary labelmap and verified geometry."""
    if geometry is None:
        raise GeometryError("geometry is required; refusing to assume unit spacing")
    arr = np.asarray(mask)
    if arr.shape != geometry.shape:
        raise GeometryError(
            "mask shape {} does not match geometry shape {}".format(arr.shape, geometry.shape)
        )
    if arr.dtype != np.bool_ and not np.issubdtype(arr.dtype, np.integer):
        raise GeometryError("mask must be boolean or integer labelmap")
    count = int(np.count_nonzero(arr))
    vv = geometry.voxel_volume_mm3()
    vol_ml = count * vv / 1000.0
    return VolumeResult(
        voxel_count=count,
        voxel_volume_mm3=vv,
        volume_mL=vol_ml,
        volume_L=vol_ml / 1000.0,
        geometry_hash=geometry.geometry_hash(),
    )


def measure_area(
    mask: np.ndarray,
    geometry: ImageGeometry,
    plane_index: int,
    plane_definition: str,
    mask_is_2d: bool = False,
) -> AreaResult:
    """Compute VAT area on a defined axial plane (cm^2)."""
    if geometry is None:
        raise GeometryError("geometry is required; refusing to assume unit spacing")
    arr = np.asarray(mask)
    if mask_is_2d:
        if arr.ndim != 2:
            raise GeometryError("2D mask required when mask_is_2d=True")
        expected_2d = (geometry.shape[1], geometry.shape[2])
        if arr.shape != expected_2d:
            raise GeometryError(
                "2D mask shape {} does not match geometry rows/cols {}".format(arr.shape, expected_2d)
            )
        plane = arr
        if plane_index < 0 or plane_index >= geometry.shape[0]:
            raise GeometryError("plane_index out of range for geometry")
    else:
        if arr.shape != geometry.shape:
            raise GeometryError(
                "mask shape {} does not match geometry shape {}".format(arr.shape, geometry.shape)
            )
        if plane_index < 0 or plane_index >= arr.shape[0]:
            raise GeometryError("plane_index out of range")
        plane = arr[plane_index]
    if not plane_definition:
        raise GeometryError("plane_definition is required for area reporting")
    count = int(np.count_nonzero(plane))
    pa = geometry.pixel_area_mm2()
    return AreaResult(
        pixel_count=count,
        pixel_area_mm2=pa,
        area_cm2=count * pa / 100.0,
        plane_index=plane_index,
        plane_definition=plane_definition,
        geometry_hash=geometry.geometry_hash(),
    )
