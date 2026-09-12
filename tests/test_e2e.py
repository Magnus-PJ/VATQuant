"""End-to-end: synthetic DICOM -> load -> pair -> compose -> measure -> export."""

from __future__ import annotations

import numpy as np
import pytest

from vatquant_core.dicom_series import load_series_from_directory
from vatquant_core.export import export_case_bundle, load_mask, read_json
from vatquant_core.masks import combine_vat_mask
from vatquant_core.measurement import measure_volume
from vatquant_core.pairing import validate_pair
from vatquant_core.qc import CaseRecord
from vatquant_core.synthetic import write_paired_case


def test_e2e_synthetic_case(tmp_path):
    case_dir = tmp_path / "case"
    meta = write_paired_case(
        str(case_dir),
        manufacturer="GE",
        shape=(12, 32, 32),
        spacing=(2.0, 2.0, 5.0),
        seed=11,
    )
    phantom = meta["phantom"]
    fat = load_series_from_directory(meta["fat_dir"])
    water = load_series_from_directory(meta["water_dir"])
    validate_pair(fat, water)

    gt = np.load(str(case_dir / "ground_truth.npz"))
    vat = combine_vat_mask(
        gt["candidate"],
        gt["compartment"],
        gt["coverage"],
        gt["exclusion"],
    )
    assert np.array_equal(vat, phantom.vat_mask)

    result = measure_volume(vat, fat.geometry)
    assert result.voxel_count == meta["expected_vat_voxels"]
    assert result.volume_mL == pytest.approx(meta["expected_vat_volume_mL"])

    record = CaseRecord(case_id="e2e-synth-011")
    record.roles_confirmed = True
    record.protocol_id = "VAT-AP-v0.1-dev"
    record.analysis_roi_definition = "synthetic full-coverage compartment"
    record.retroperitoneal_fat_rule = "included_in_compartment"
    record.volume_result = result
    record.source_series = [
        {
            "role": "fat",
            "series_uid": fat.source_refs.series_uid,
            "sop_uids": fat.source_refs.sop_uids,
        },
        {
            "role": "water",
            "series_uid": water.source_refs.series_uid,
            "sop_uids": water.source_refs.sop_uids,
        },
    ]
    record.scanner = {
        "manufacturer": fat.source_refs.manufacturer,
        "model": fat.source_refs.model,
        "field_strength_T": fat.source_refs.field_strength_T,
    }
    record.mark_reviewed("e2e-reviewer")

    out_dir = tmp_path / "export"
    paths = export_case_bundle(record, fat.geometry, vat, str(out_dir))
    metrics = read_json(paths["json"])
    assert metrics.vat_volume_mL == pytest.approx(meta["expected_vat_volume_mL"])
    assert metrics.vat_volume_L == pytest.approx(meta["expected_vat_volume_mL"] / 1000.0)
    loaded, geom = load_mask(paths["mask"])
    assert measure_volume(loaded, geom).volume_mL == pytest.approx(result.volume_mL)
