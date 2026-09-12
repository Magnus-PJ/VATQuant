"""Tests for ImageGeometry."""

from __future__ import annotations

import numpy as np
import pytest

from vatquant_core.errors import GeometryError
from vatquant_core.geometry import ImageGeometry


def test_orthogonal_voxel_volume():
    g = ImageGeometry.orthogonal(shape=(10, 20, 30), spacing=(2.0, 2.0, 5.0))
    assert g.voxel_volume_mm3() == pytest.approx(20.0)


def test_rejects_nonpositive_spacing():
    with pytest.raises(GeometryError):
        ImageGeometry.orthogonal(shape=(2, 2, 2), spacing=(1.0, 0.0, 1.0))
    with pytest.raises(GeometryError):
        ImageGeometry.orthogonal(shape=(2, 2, 2), spacing=(1.0, -1.0, 1.0))


def test_rejects_bad_direction():
    bad = ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    with pytest.raises(GeometryError):
        ImageGeometry(shape=(2, 2, 2), spacing=(1, 1, 1), origin_lps=(0, 0, 0), direction=bad)


def test_oblique_uses_determinant_not_product():
    # 45-degree rotation in XY for I/J; K along Z
    a = np.pi / 4
    c, s = np.cos(a), np.sin(a)
    # columns = I, J, K
    d = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)
    direction = tuple(tuple(float(d[r, c]) for c in range(3)) for r in range(3))
    g = ImageGeometry(
        shape=(4, 4, 4),
        spacing=(2.0, 3.0, 5.0),
        origin_lps=(0.0, 0.0, 0.0),
        direction=direction,
    )
    expected = abs(np.linalg.det(g.affine_mm()[:3, :3]))
    assert g.voxel_volume_mm3() == pytest.approx(expected)
    assert g.voxel_volume_mm3() == pytest.approx(2.0 * 3.0 * 5.0)


def test_permute_axes_preserves_physical_volume_concept():
    g1 = ImageGeometry.orthogonal(shape=(10, 20, 30), spacing=(2.0, 3.0, 4.0))
    # Different shape/spacing assignment with same product
    g2 = ImageGeometry.orthogonal(shape=(30, 10, 20), spacing=(4.0, 2.0, 3.0))
    assert g1.voxel_volume_mm3() == pytest.approx(g2.voxel_volume_mm3())


def test_ijk_to_lps_and_ras():
    g = ImageGeometry.orthogonal(shape=(5, 5, 5), spacing=(2.0, 3.0, 4.0), origin_lps=(10, 20, 30))
    lps = g.ijk_to_lps((1, 0, 0))
    assert lps[0] == pytest.approx(12.0)
    ras = g.lps_to_ras(lps)
    assert ras[0] == pytest.approx(-12.0)
    assert ras[1] == pytest.approx(-20.0)
    assert ras[2] == pytest.approx(30.0)


def test_sitk_roundtrip():
    g = ImageGeometry.orthogonal(shape=(3, 4, 5), spacing=(1.5, 2.5, 3.5), origin_lps=(1, 2, 3))
    img = g.to_sitk()
    g2 = ImageGeometry.from_sitk(img)
    assert g.approx_equal(g2, tol=1e-6)


def test_approx_equal():
    a = ImageGeometry.orthogonal(shape=(2, 2, 2), spacing=(1, 1, 1))
    b = ImageGeometry.orthogonal(shape=(2, 2, 2), spacing=(1, 1, 1.0000001))
    c = ImageGeometry.orthogonal(shape=(2, 2, 2), spacing=(1, 1, 2))
    assert a.approx_equal(b, tol=1e-3)
    assert not a.approx_equal(c, tol=1e-3)


def test_pixel_area():
    g = ImageGeometry.orthogonal(shape=(2, 10, 10), spacing=(2.0, 3.0, 5.0))
    assert g.pixel_area_mm2() == pytest.approx(6.0)
