"""VAT mask composition and label-preserving resampling."""

from __future__ import annotations

from typing import Optional

import numpy as np
import SimpleITK as sitk

from vatquant_core.errors import GeometryError
from vatquant_core.geometry import ImageGeometry


def _as_bool_mask(arr: np.ndarray, name: str) -> np.ndarray:
    a = np.asarray(arr)
    if a.dtype != np.bool_ and not np.issubdtype(a.dtype, np.integer):
        raise GeometryError("{} must be a boolean or integer labelmap".format(name))
    return a.astype(bool, copy=False)


def combine_vat_mask(
    candidate: np.ndarray,
    compartment: np.ndarray,
    coverage: np.ndarray,
    exclusions: Optional[np.ndarray] = None,
) -> np.ndarray:
    """VAT = candidate AND compartment AND coverage AND NOT exclusions."""
    cand = _as_bool_mask(candidate, "candidate")
    comp = _as_bool_mask(compartment, "compartment")
    cov = _as_bool_mask(coverage, "coverage")
    if cand.shape != comp.shape or cand.shape != cov.shape:
        raise GeometryError(
            "mask shapes must match: candidate {}, compartment {}, coverage {}".format(
                cand.shape, comp.shape, cov.shape
            )
        )
    vat = cand & comp & cov
    if exclusions is not None:
        excl = _as_bool_mask(exclusions, "exclusions")
        if excl.shape != cand.shape:
            raise GeometryError(
                "exclusions shape {} does not match candidate {}".format(excl.shape, cand.shape)
            )
        vat = vat & (~excl)
    return vat


def numpy_to_sitk(mask: np.ndarray, geometry: ImageGeometry) -> sitk.Image:
    """Convert a (K,J,I) numpy labelmap to a SimpleITK image with geometry."""
    if mask.shape != geometry.shape:
        raise GeometryError(
            "mask shape {} does not match geometry shape {}".format(mask.shape, geometry.shape)
        )
    # SimpleITK GetArrayFromImage returns (K,J,I); SetArray works the same way.
    img = sitk.GetImageFromArray(mask.astype(np.uint8, copy=False))
    img.SetSpacing((float(geometry.spacing[0]), float(geometry.spacing[1]), float(geometry.spacing[2])))
    img.SetOrigin(tuple(float(x) for x in geometry.origin_lps))
    d = geometry.direction_array
    img.SetDirection(tuple(float(x) for x in d.reshape(-1)))
    return img


def sitk_to_numpy(image: sitk.Image) -> np.ndarray:
    return np.asarray(sitk.GetArrayFromImage(image))


def resample_label_nearest(
    mask: np.ndarray,
    src_geom: ImageGeometry,
    dst_geom: ImageGeometry,
) -> np.ndarray:
    """Resample a labelmap with nearest-neighbour interpolation only."""
    src = numpy_to_sitk(mask.astype(np.uint8, copy=False), src_geom)
    ref = dst_geom.to_sitk()
    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(ref)
    resampler.SetInterpolator(sitk.sitkNearestNeighbor)
    resampler.SetDefaultPixelValue(0)
    resampler.SetTransform(sitk.Transform())
    out = resampler.Execute(src)
    arr = sitk_to_numpy(out).astype(bool)
    # Ensure binary labels (nearest neighbour of 0/1 should stay 0/1)
    return arr
