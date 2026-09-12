"""Tests for masks and measurement."""

from __future__ import annotations

import numpy as np
import pytest

from vatquant_core.errors import GeometryError
from vatquant_core.geometry import ImageGeometry
from vatquant_core.masks import combine_vat_mask, resample_label_nearest
from vatquant_core.measurement import measure_area, measure_volume


def test_spec_example_120000_voxels():
    """120,000 VAT voxels × 2 × 2 × 5 mm = 2,400 mL = 2.4 L."""
    # Use a compact shape but exact voxel count via a flat mask reshaped conceptually:
    # Build geometry for arbitrary shape with spacing 2x2x5 and a mask with 120000 True voxels.
    shape = (60, 50, 40)  # 120000 voxels total
    assert shape[0] * shape[1] * shape[2] == 120000
    geom = ImageGeometry.orthogonal(shape=shape, spacing=(2.0, 2.0, 5.0))
    mask = np.ones(shape, dtype=bool)
    result = measure_volume(mask, geom)
    assert result.voxel_count == 120000
    assert result.voxel_volume_mm3 == pytest.approx(20.0)
    assert result.volume_mL == pytest.approx(2400.0)
    assert result.volume_L == pytest.approx(2.4)


def test_combine_vat_mask():
    shape = (2, 4, 4)
    candidate = np.zeros(shape, dtype=bool)
    compartment = np.zeros(shape, dtype=bool)
    coverage = np.ones(shape, dtype=bool)
    exclusions = np.zeros(shape, dtype=bool)
    candidate[0, 1:3, 1:3] = True
    compartment[0, 0:3, 0:3] = True
    exclusions[0, 1, 1] = True
    vat = combine_vat_mask(candidate, compartment, coverage, exclusions)
    assert vat[0, 1, 1] is np.False_ or vat[0, 1, 1] == False
    assert vat[0, 1, 2] == True
    assert int(vat.sum()) == 3


def test_combine_shape_mismatch():
    with pytest.raises(GeometryError):
        combine_vat_mask(
            np.ones((2, 2, 2), dtype=bool),
            np.ones((2, 2, 3), dtype=bool),
            np.ones((2, 2, 2), dtype=bool),
        )


def test_measure_requires_geometry_match():
    geom = ImageGeometry.orthogonal(shape=(2, 2, 2), spacing=(1, 1, 1))
    with pytest.raises(GeometryError):
        measure_volume(np.ones((3, 2, 2), dtype=bool), geom)


def test_area_cm2():
    geom = ImageGeometry.orthogonal(shape=(5, 10, 10), spacing=(2.0, 2.0, 5.0))
    mask = np.zeros(geom.shape, dtype=bool)
    mask[2, :, :] = True  # 100 pixels
    area = measure_area(mask, geom, plane_index=2, plane_definition="synthetic mid-plane")
    assert area.pixel_count == 100
    assert area.area_cm2 == pytest.approx(100 * 4.0 / 100.0)


def test_resample_nearest_keeps_binary():
    src = ImageGeometry.orthogonal(shape=(4, 8, 8), spacing=(2, 2, 4))
    dst = ImageGeometry.orthogonal(shape=(4, 8, 8), spacing=(2, 2, 4), origin_lps=(0, 0, 0))
    mask = np.zeros(src.shape, dtype=bool)
    mask[1:3, 2:6, 2:6] = True
    out = resample_label_nearest(mask, src, dst)
    assert out.dtype == bool or out.dtype == np.bool_
    assert set(np.unique(out.astype(np.uint8)).tolist()).issubset({0, 1})
    assert int(out.sum()) == int(mask.sum())


def test_axis_flip_preserves_volume():
    geom = ImageGeometry.orthogonal(shape=(10, 12, 14), spacing=(2.0, 2.0, 5.0))
    rng = np.random.default_rng(0)
    mask = rng.random(geom.shape) > 0.7
    r1 = measure_volume(mask, geom)
    # Flip K direction cosine (mirror along Z) with adjusted origin so physical extent matches
    d = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0))
    # origin at former last slice centre in Z: z' = origin_z + (n-1)*dz when index 0 maps there with -K
    origin = (0.0, 0.0, (geom.shape[0] - 1) * geom.spacing[2])
    geom2 = ImageGeometry(shape=geom.shape, spacing=geom.spacing, origin_lps=origin, direction=d)
    mask2 = mask[::-1, :, :]
    r2 = measure_volume(mask2, geom2)
    assert r1.volume_mL == pytest.approx(r2.volume_mL)
