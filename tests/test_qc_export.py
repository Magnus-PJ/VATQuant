"""Tests for QC states and export round-trips."""

from __future__ import annotations

import json

import numpy as np
import pytest

from vatquant_core.errors import QCBlockedError
from vatquant_core.export import (
    export_case_bundle,
    load_mask,
    metrics_from_case,
    read_json,
    save_mask_nifti,
    write_json,
)
from vatquant_core.geometry import ImageGeometry
from vatquant_core.measurement import measure_volume
from vatquant_core.qc import AnalysisState, CaseRecord
from vatquant_core.synthetic import make_phantom


def test_edit_resets_review():
    case = CaseRecord(case_id="synth-001")
    case.roles_confirmed = True
    geom = ImageGeometry.orthogonal(shape=(2, 2, 2), spacing=(1, 1, 1))
    mask = np.ones(geom.shape, dtype=bool)
    case.volume_result = measure_volume(mask, geom)
    case.mark_reviewed("reviewer-a")
    assert case.state == AnalysisState.REVIEWED
    case.mark_mask_edited()
    assert case.state == AnalysisState.REVIEW_REQUIRED
    assert case.volume_result is None
    assert case.reviewer_id is None


def test_export_blocked_until_reviewed():
    case = CaseRecord(case_id="synth-002")
    case.roles_confirmed = True
    with pytest.raises(QCBlockedError):
        case.require_export_final()


def test_json_roundtrip_null_not_zero():
    case = CaseRecord(case_id="synth-003", state=AnalysisState.QC_PENDING)
    record = metrics_from_case(case)
    assert record.vat_volume_mL is None
    assert record.intended_use_status == "development_evaluation"
    # as dict for JSON
    d = record.to_dict()
    assert d["vat_volume_mL"] is None


def test_mask_nrrd_roundtrip_preserves_volume(tmp_path):
    p = make_phantom(shape=(8, 24, 24), spacing=(2.0, 2.0, 5.0), seed=5)
    path = str(tmp_path / "vat.nrrd")
    from vatquant_core.export import save_mask_nrrd

    save_mask_nrrd(p.vat_mask, p.geometry, path)
    loaded, geom = load_mask(path)
    assert np.array_equal(loaded, p.vat_mask)
    assert geom.approx_equal(p.geometry, tol=1e-5)
    r1 = measure_volume(p.vat_mask, p.geometry)
    r2 = measure_volume(loaded, geom)
    assert r1.volume_mL == pytest.approx(r2.volume_mL)


def test_nifti_roundtrip(tmp_path):
    p = make_phantom(shape=(6, 16, 16), spacing=(2.0, 2.0, 5.0), seed=6)
    path = str(tmp_path / "vat.nii.gz")
    save_mask_nifti(p.vat_mask, p.geometry, path)
    loaded, geom = load_mask(path)
    assert int(loaded.sum()) == int(p.vat_mask.sum())


def test_export_bundle(tmp_path):
    p = make_phantom(shape=(8, 24, 24), spacing=(2.0, 2.0, 5.0), seed=7)
    case = CaseRecord(case_id="synth-007")
    case.roles_confirmed = True
    case.protocol_id = "VAT-AP-v0.1"
    case.analysis_roi_definition = "synthetic compartment"
    case.volume_result = measure_volume(p.vat_mask, p.geometry)
    case.scanner = {
        "manufacturer": p.manufacturer,
        "model": "SYNTHETIC",
        "field_strength_T": 1.5,
    }
    case.mark_reviewed("dev-reviewer")
    out = export_case_bundle(case, p.geometry, p.vat_mask, str(tmp_path / "out"))
    data = read_json(out["json"]).to_dict()
    assert data["vat_volume_mL"] == pytest.approx(p.expected_vat_volume_mL)
    assert data["intended_use_status"] == "development_evaluation"
    assert data["review_status"] == "REVIEWED"
