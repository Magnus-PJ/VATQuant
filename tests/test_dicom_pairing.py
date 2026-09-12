"""Tests for DICOM loading, pairing, and corrupt variants."""

from __future__ import annotations

import numpy as np
import pytest

from vatquant_core.dicom_series import load_series_from_directory
from vatquant_core.errors import PairingError, SeriesIntegrityError, UnsupportedInputError
from vatquant_core.pairing import suggest_role, validate_pair
from vatquant_core.synthetic import make_phantom, write_paired_case, write_synthetic_dicom_series


@pytest.fixture
def phantom():
    return make_phantom(shape=(12, 32, 32), spacing=(2.0, 2.0, 5.0), manufacturer="GE", seed=2)


def test_load_shuffled_and_reversed_same_volume(tmp_path, phantom):
    d1 = tmp_path / "normal"
    d2 = tmp_path / "reversed"
    d3 = tmp_path / "shuffled"
    write_synthetic_dicom_series(phantom, str(d1), channel="fat")
    write_synthetic_dicom_series(phantom, str(d2), channel="fat", reverse_order=True)
    write_synthetic_dicom_series(phantom, str(d3), channel="fat", shuffle_names=True)

    s1 = load_series_from_directory(str(d1))
    s2 = load_series_from_directory(str(d2))
    s3 = load_series_from_directory(str(d3))

    assert s1.array.shape == s2.array.shape == s3.array.shape
    assert np.allclose(s1.array, s2.array, atol=1e-5)
    assert np.allclose(s1.array, s3.array, atol=1e-5)
    assert s1.geometry.approx_equal(s2.geometry, tol=1e-3)
    assert s1.geometry.approx_equal(s3.geometry, tol=1e-3)


def test_drop_slice_raises(tmp_path, phantom):
    d = tmp_path / "drop"
    write_synthetic_dicom_series(phantom, str(d), channel="fat", drop_slice_index=5)
    with pytest.raises((SeriesIntegrityError, UnsupportedInputError)):
        load_series_from_directory(str(d))


def test_duplicate_slice_raises(tmp_path, phantom):
    d = tmp_path / "dup"
    write_synthetic_dicom_series(phantom, str(d), channel="fat", duplicate_slice_index=3)
    with pytest.raises(SeriesIntegrityError):
        load_series_from_directory(str(d))


def test_mixed_echo_raises(tmp_path, phantom):
    d = tmp_path / "echo"
    write_synthetic_dicom_series(phantom, str(d), channel="fat", mixed_echo_on_slice=4)
    with pytest.raises(SeriesIntegrityError):
        load_series_from_directory(str(d))


def test_enhanced_mr_rejected(tmp_path, phantom):
    d = tmp_path / "enh"
    write_synthetic_dicom_series(phantom, str(d), channel="fat", enhanced_mr=True)
    with pytest.raises(UnsupportedInputError):
        load_series_from_directory(str(d))


def test_overlapping_slabs_rejected(tmp_path, phantom):
    d = tmp_path / "slabs"
    write_synthetic_dicom_series(phantom, str(d), channel="fat", filename_prefix="A")
    write_synthetic_dicom_series(
        phantom,
        str(d),
        channel="fat",
        filename_prefix="B",
        slab_offset_mm=phantom.geometry.spacing[2] * 2,
        series_uid_override=phantom.fat_series_uid,
    )
    with pytest.raises((SeriesIntegrityError, UnsupportedInputError)):
        load_series_from_directory(str(d))


def test_valid_pair_and_role_hints(tmp_path):
    meta = write_paired_case(str(tmp_path / "case"), manufacturer="GE", shape=(10, 32, 32), seed=3)
    fat = load_series_from_directory(meta["fat_dir"])
    water = load_series_from_directory(meta["water_dir"])
    validate_pair(fat, water)
    assert suggest_role(fat).suggested_role == "fat"
    assert suggest_role(water).suggested_role == "water"


def test_siemens_role_hints(tmp_path):
    meta = write_paired_case(
        str(tmp_path / "case"), manufacturer="Siemens", shape=(8, 32, 32), seed=4
    )
    fat = load_series_from_directory(meta["fat_dir"])
    water = load_series_from_directory(meta["water_dir"])
    assert suggest_role(fat).suggested_role == "fat"
    assert suggest_role(water).suggested_role == "water"
    validate_pair(fat, water)


def test_mismatched_geometry_pair_fails(tmp_path, phantom):
    fat_dir = tmp_path / "fat"
    water_dir = tmp_path / "water"
    write_synthetic_dicom_series(phantom, str(fat_dir), channel="fat")
    write_synthetic_dicom_series(
        phantom,
        str(water_dir),
        channel="water",
        spacing_override=(2.0, 2.0, 6.0),
    )
    fat = load_series_from_directory(str(fat_dir))
    water = load_series_from_directory(str(water_dir))
    with pytest.raises(PairingError):
        validate_pair(fat, water)


def test_thickness_vs_centre_spacing_reported(tmp_path, phantom):
    d = tmp_path / "fat"
    write_synthetic_dicom_series(phantom, str(d), channel="fat")
    series = load_series_from_directory(str(d))
    assert series.source_refs.centre_to_centre_spacing_mm == pytest.approx(5.0)
    assert series.source_refs.slice_thickness_mm == pytest.approx(5.0)
