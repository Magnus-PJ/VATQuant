#!/usr/bin/env python
"""Headless smoke test for VATQuant Slicer module + vatquant_core.

Run with Slicer's PythonSlicer.exe:

  & "C:\\Path\\To\\Slicer 5.12.3\\bin\\PythonSlicer.exe" scripts\\slicer_smoke_test.py

Or from a Slicer Python console after adding the module path.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

MODULE_DIR = os.path.join(REPO_ROOT, "VATQuant")
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)


def _require_slicer():
    try:
        import slicer  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "This script must run inside Slicer PythonSlicer.exe (slicer module missing): {}".format(
                exc
            )
        )


def main():
    _require_slicer()
    import slicer

    # Import module logic (loads vatquant_core)
    import VATQuant as vatquant_module

    logic = vatquant_module.VATQuantLogic()

    from vatquant_core.synthetic import write_paired_case
    from vatquant_core.masks import combine_vat_mask
    from vatquant_core.measurement import measure_volume

    work = tempfile.mkdtemp(prefix="vatquant_slicer_smoke_")
    meta = write_paired_case(
        work,
        manufacturer="GE",
        shape=(10, 32, 32),
        spacing=(2.0, 2.0, 5.0),
        seed=21,
    )
    phantom = meta["phantom"]
    expected = float(phantom.expected_vat_volume_mL)

    # Core reference measurement
    vat_gt = combine_vat_mask(
        phantom.candidate_mask,
        phantom.compartment_mask,
        phantom.coverage_mask,
        phantom.exclusion_mask,
    )
    core_ml = measure_volume(vat_gt, phantom.geometry).volume_mL

    fat_node = logic.loadDicomFolderAsVolume(meta["fat_dir"], "Smoke_Fat")
    water_node = logic.loadDicomFolderAsVolume(meta["water_dir"], "Smoke_Water")
    report = logic.validateVolumes(
        fat_node,
        water_node,
        case_id="slicer-smoke-021",
        protocol_id="VAT-AP-v0.1-dev",
        roi="synthetic compartment",
        retro="included",
    )
    logic.case.roles_confirmed = True
    print(report)

    seg = logic.ensureSegmentation(fat_node)
    # Fill segments from phantom ground truth
    cand_id = seg.GetSegmentation().GetSegmentIdBySegmentName("Candidate")
    comp_id = seg.GetSegmentation().GetSegmentIdBySegmentName("Compartment")
    cov_id = seg.GetSegmentation().GetSegmentIdBySegmentName("Coverage")
    excl_id = seg.GetSegmentation().GetSegmentIdBySegmentName("Exclusion")
    logic._updateSegmentFromArray(cand_id, fat_node, phantom.candidate_mask.astype("uint8"))
    logic._updateSegmentFromArray(comp_id, fat_node, phantom.compartment_mask.astype("uint8"))
    logic._updateSegmentFromArray(cov_id, fat_node, phantom.coverage_mask.astype("uint8"))
    logic._updateSegmentFromArray(excl_id, fat_node, phantom.exclusion_mask.astype("uint8"))

    n_vat = logic.composeVAT(fat_node)
    result = logic.measureVAT(fat_node)
    logic.markReviewed("smoke-tester")
    export_dir = os.path.join(work, "export")
    paths = logic.exportBundle(fat_node, export_dir)

    with open(paths["json"], "r", encoding="utf-8") as f:
        metrics = json.load(f)

    tol = 1e-3
    ok = (
        abs(result.volume_mL - expected) <= tol
        and abs(core_ml - expected) <= tol
        and metrics.get("intended_use_status") == "development_evaluation"
        and metrics.get("review_status") == "REVIEWED"
        and n_vat == phantom.expected_vat_voxels
    )
    summary = {
        "ok": ok,
        "expected_mL": expected,
        "core_mL": core_ml,
        "slicer_module_mL": result.volume_mL,
        "voxels": n_vat,
        "export": paths,
        "work": work,
    }
    print(json.dumps(summary, indent=2))
    if not ok:
        raise SystemExit(1)
    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
