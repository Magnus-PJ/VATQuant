"""Tests for synthetic phantoms."""

from __future__ import annotations

import numpy as np
import pytest

from vatquant_core.masks import combine_vat_mask
from vatquant_core.measurement import measure_volume
from vatquant_core.synthetic import make_phantom


def test_phantom_expected_volume_matches_measurement():
    p = make_phantom(shape=(20, 48, 48), spacing=(2.0, 2.0, 5.0), seed=1)
    vat = combine_vat_mask(p.candidate_mask, p.compartment_mask, p.coverage_mask, p.exclusion_mask)
    # Ground-truth vat_mask should equal composed mask for this phantom design
    assert np.array_equal(vat, p.vat_mask)
    result = measure_volume(vat, p.geometry)
    assert result.voxel_count == p.expected_vat_voxels
    assert result.volume_mL == pytest.approx(p.expected_vat_volume_mL)
    assert result.voxel_count > 0
