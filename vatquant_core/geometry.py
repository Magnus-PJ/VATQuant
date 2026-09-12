"""Physical image geometry: affine, voxel volume, LPS/RAS/IJK conversions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

import numpy as np

from vatquant_core.errors import GeometryError

# LPS <-> RAS flip on first two axes
_LPS_TO_RAS = np.diag([-1.0, -1.0, 1.0])


def _as_float_array(values: Sequence[float], length: int, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    if arr.size != length:
        raise GeometryError("{} must have length {}, got {}".format(name, length, arr.size))
    if not np.all(np.isfinite(arr)):
        raise GeometryError("{} contains non-finite values".format(name))
    return arr


def _validate_direction(direction: np.ndarray) -> np.ndarray:
    d = np.asarray(direction, dtype=np.float64).reshape(3, 3)
    if not np.all(np.isfinite(d)):
        raise GeometryError("direction matrix contains non-finite values")
    # Columns should be unit and mutually orthogonal (right- or left-handed OK)
    for col in range(3):
        n = np.linalg.norm(d[:, col])
        if n < 1e-6:
            raise GeometryError("direction column {} has near-zero length".format(col))
        d[:, col] = d[:, col] / n
    # Re-orthonormalize check (allow small numerical error after normalize)
    gram = d.T @ d
    if not np.allclose(gram, np.eye(3), atol=1e-3):
        raise GeometryError("direction matrix columns are not orthonormal")
    return d


@dataclass(frozen=True)
class ImageGeometry:
    """Physical geometry of a 3D image volume.

    shape is (K, J, I) = (slices, rows, columns) matching NumPy array layout
    after stacking classic DICOM slices along axis 0.
    spacing is (dx, dy, dz) in millimetres along I, J, K index axes.
    origin_lps is the LPS coordinates of voxel index (0, 0, 0) centre.
    direction is a 3x3 matrix whose columns are LPS direction cosines of
    the I, J, K axes (DICOM Image Orientation Patient style for I and J;
    K is the slice-normal direction).
    """

    shape: Tuple[int, int, int]
    spacing: Tuple[float, float, float]
    origin_lps: Tuple[float, float, float]
    direction: Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]

    def __post_init__(self) -> None:
        if len(self.shape) != 3:
            raise GeometryError("shape must be length 3 (K, J, I)")
        for s in self.shape:
            if int(s) < 1:
                raise GeometryError("shape dimensions must be positive integers")
        sp = _as_float_array(self.spacing, 3, "spacing")
        if np.any(sp <= 0):
            raise GeometryError("spacing must be strictly positive; refusing silent defaults")
        _as_float_array(self.origin_lps, 3, "origin_lps")
        d = np.asarray(self.direction, dtype=np.float64)
        if d.shape != (3, 3):
            raise GeometryError("direction must be a 3x3 matrix")
        _validate_direction(d)

    @property
    def spacing_array(self) -> np.ndarray:
        return np.asarray(self.spacing, dtype=np.float64)

    @property
    def origin_array(self) -> np.ndarray:
        return np.asarray(self.origin_lps, dtype=np.float64)

    @property
    def direction_array(self) -> np.ndarray:
        return np.asarray(self.direction, dtype=np.float64).reshape(3, 3)

    def affine_mm(self) -> np.ndarray:
        """4x4 affine mapping voxel index (i, j, k, 1) to LPS millimetres.

        Index order in the homogeneous vector is (i, j, k) matching DICOM
        column/row/slice indexing. NumPy arrays are stored (k, j, i).
        """
        d = self.direction_array
        sp = self.spacing_array
        # Columns of linear part: direction_I * dx, direction_J * dy, direction_K * dz
        linear = np.column_stack(
            [
                d[:, 0] * sp[0],
                d[:, 1] * sp[1],
                d[:, 2] * sp[2],
            ]
        )
        affine = np.eye(4, dtype=np.float64)
        affine[:3, :3] = linear
        affine[:3, 3] = self.origin_array
        return affine

    def voxel_volume_mm3(self) -> float:
        """Absolute determinant of the IJK->mm linear transform."""
        return float(abs(np.linalg.det(self.affine_mm()[:3, :3])))

    def pixel_area_mm2(self) -> float:
        """In-plane pixel area from the I and J axes (ignores K spacing)."""
        d = self.direction_array
        sp = self.spacing_array
        v_i = d[:, 0] * sp[0]
        v_j = d[:, 1] * sp[1]
        return float(np.linalg.norm(np.cross(v_i, v_j)))

    def is_orthogonal(self, atol: float = 1e-5) -> bool:
        d = self.direction_array
        return bool(np.allclose(np.abs(d), np.eye(3), atol=atol) or np.allclose(d.T @ d, np.eye(3), atol=atol))

    def approx_equal(self, other: "ImageGeometry", tol: float = 1e-3) -> bool:
        if self.shape != other.shape:
            return False
        if not np.allclose(self.spacing_array, other.spacing_array, atol=tol, rtol=0):
            return False
        if not np.allclose(self.origin_array, other.origin_array, atol=tol, rtol=0):
            return False
        if not np.allclose(self.direction_array, other.direction_array, atol=tol, rtol=0):
            return False
        return True

    def ijk_to_lps(self, ijk: Sequence[float]) -> np.ndarray:
        vec = np.asarray(list(ijk) + [1.0], dtype=np.float64)
        if vec.size != 4:
            raise GeometryError("ijk must have length 3")
        return (self.affine_mm() @ vec)[:3]

    def lps_to_ras(self, lps: Sequence[float]) -> np.ndarray:
        return _LPS_TO_RAS @ np.asarray(lps, dtype=np.float64)

    def ijk_to_ras(self, ijk: Sequence[float]) -> np.ndarray:
        return self.lps_to_ras(self.ijk_to_lps(ijk))

    def geometry_hash(self) -> str:
        payload = {
            "shape": list(self.shape),
            "spacing": [float(x) for x in self.spacing],
            "origin_lps": [float(x) for x in self.origin_lps],
            "direction": [list(row) for row in self.direction],
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]

    def to_sitk(self) -> Any:
        """Return a SimpleITK image of zeros with this geometry (uint8)."""
        import SimpleITK as sitk

        # SimpleITK size is (I, J, K)
        size = (int(self.shape[2]), int(self.shape[1]), int(self.shape[0]))
        img = sitk.Image(size, sitk.sitkUInt8)
        img.SetSpacing((float(self.spacing[0]), float(self.spacing[1]), float(self.spacing[2])))
        img.SetOrigin(tuple(float(x) for x in self.origin_lps))
        # SimpleITK direction is row-major flattened 3x3 (direction cosines of I,J,K)
        d = self.direction_array
        img.SetDirection(tuple(float(x) for x in d.T.reshape(-1)))
        # Note: SimpleITK SetDirection expects direction matrix in column-major
        # flattened form matching ITK: elements of direction matrix D such that
        # physical = origin + D * diag(spacing) * index.
        # ITK stores direction as the matrix whose *columns* are direction cosines;
        # SetDirection takes the matrix in row-major order of that matrix.
        # Re-set correctly:
        img.SetDirection(tuple(float(x) for x in d.reshape(-1)))
        return img

    @classmethod
    def from_sitk(cls, image: Any) -> "ImageGeometry":
        import SimpleITK as sitk

        if not isinstance(image, sitk.Image):
            raise GeometryError("from_sitk expects a SimpleITK Image")
        size = image.GetSize()  # (I, J, K)
        if len(size) != 3:
            raise GeometryError("from_sitk requires a 3D image")
        spacing = image.GetSpacing()
        origin = image.GetOrigin()
        direction = np.array(image.GetDirection(), dtype=np.float64).reshape(3, 3)
        return cls(
            shape=(int(size[2]), int(size[1]), int(size[0])),
            spacing=(float(spacing[0]), float(spacing[1]), float(spacing[2])),
            origin_lps=(float(origin[0]), float(origin[1]), float(origin[2])),
            direction=tuple(tuple(float(x) for x in row) for row in direction),
        )

    @classmethod
    def orthogonal(
        cls,
        shape: Tuple[int, int, int],
        spacing: Tuple[float, float, float],
        origin_lps: Optional[Tuple[float, float, float]] = None,
    ) -> "ImageGeometry":
        """Convenience constructor for axis-aligned LPS geometry."""
        if origin_lps is None:
            origin_lps = (0.0, 0.0, 0.0)
        identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        return cls(shape=shape, spacing=spacing, origin_lps=origin_lps, direction=identity)
