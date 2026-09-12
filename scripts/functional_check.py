#!/usr/bin/env python
"""Functional check: VATQuant module discovery + end-to-end synthetic workflow in Slicer."""

from __future__ import annotations

import json
import os
import sys
import tempfile

REPO = r"C:\Users\paul.joy\Projects\VATQuant"
MODULE_DIR = os.path.join(REPO, "VATQuant")
# Insert module dir first so `import VATQuant` loads VATQuant.py (not the package folder)
if MODULE_DIR in sys.path:
    sys.path.remove(MODULE_DIR)
sys.path.insert(0, MODULE_DIR)
if REPO not in sys.path:
    sys.path.insert(1, REPO)


def main():
    import slicer

    results = {
        "slicer_version": slicer.app.applicationVersion,
        "module_factory_has_VATQuant": False,
        "logic_ok": False,
        "volume_match": False,
        "export_ok": False,
        "intended_use": None,
        "errors": [],
    }

    # 1) Module discovery
    factory = slicer.app.moduleManager().factoryManager()
    names = list(factory.registeredModuleNames())
    results["module_factory_has_VATQuant"] = "VATQuant" in names
    if not results["module_factory_has_VATQuant"]:
        results["errors"].append(
            "VATQuant not in registered modules (names sample: {})".format(names[:20])
        )

    try:
        import importlib

        # Prefer Slicer-loaded module object if available
        mod = sys.modules.get("VATQuant")
        if mod is None or not hasattr(mod, "VATQuantLogic"):
            if "VATQuant" in sys.modules:
                del sys.modules["VATQuant"]
            import VATQuant as mod  # loads MODULE_DIR/VATQuant.py
        if not hasattr(mod, "VATQuantLogic"):
            raise AttributeError(
                "VATQuant module keys: {}".format(
                    [k for k in dir(mod) if not k.startswith("_")][:40]
                )
            )
    except Exception as exc:
        results["errors"].append("import VATQuant failed: {}".format(exc))
        print(json.dumps(results, indent=2))
        raise SystemExit(1)

    logic = mod.VATQuantLogic()
    results["logic_ok"] = True

    # 2) End-to-end on synthetic Dixon pair
    from vatquant_core.synthetic import write_paired_case
    from vatquant_core.masks import combine_vat_mask
    from vatquant_core.measurement import measure_volume

    work = tempfile.mkdtemp(prefix="vatquant_func_")
    meta = write_paired_case(
        work, manufacturer="GE", shape=(10, 32, 32), spacing=(2.0, 2.0, 5.0), seed=77
    )
    phantom = meta["phantom"]
    expected = float(phantom.expected_vat_volume_mL)

    fat = logic.loadDicomFolderAsVolume(meta["fat_dir"], "Func_Fat")
    water = logic.loadDicomFolderAsVolume(meta["water_dir"], "Func_Water")
    report = logic.validateVolumes(
        fat,
        water,
        case_id="func-check-077",
        protocol_id="VAT-AP-v0.1-dev",
        roi="synthetic",
        retro="included",
    )
    logic.case.roles_confirmed = True

    seg = logic.ensureSegmentation(fat)
    for name, mask in (
        ("Candidate", phantom.candidate_mask),
        ("Compartment", phantom.compartment_mask),
        ("Coverage", phantom.coverage_mask),
        ("Exclusion", phantom.exclusion_mask),
    ):
        sid = seg.GetSegmentation().GetSegmentIdBySegmentName(name)
        logic._updateSegmentFromArray(sid, fat, mask.astype("uint8"))

    n = logic.composeVAT(fat)
    measured = logic.measureVAT(fat)
    logic.markReviewed("func-checker")
    paths = logic.exportBundle(fat, os.path.join(work, "export"))

    with open(paths["json"], "r", encoding="utf-8") as f:
        metrics = json.load(f)

    core_ml = measure_volume(
        combine_vat_mask(
            phantom.candidate_mask,
            phantom.compartment_mask,
            phantom.coverage_mask,
            phantom.exclusion_mask,
        ),
        phantom.geometry,
    ).volume_mL

    results["expected_mL"] = expected
    results["core_mL"] = core_ml
    results["module_mL"] = measured.volume_mL
    results["voxels"] = n
    results["volume_match"] = abs(measured.volume_mL - expected) < 1e-3
    results["export_ok"] = (
        metrics.get("intended_use_status") == "development_evaluation"
        and metrics.get("review_status") == "REVIEWED"
        and os.path.isfile(paths["mask"])
    )
    results["intended_use"] = metrics.get("intended_use_status")
    results["geometry_report_ok"] = "DICOM pairing: OK" in report
    results["ok"] = (
        results["logic_ok"]
        and results["volume_match"]
        and results["export_ok"]
        and results["geometry_report_ok"]
    )

    # 3) Try selecting the module in the factory (loads widget class)
    try:
        slicer.modules.vatquant
        results["slicer_modules_vatquant_attr"] = True
    except Exception as exc:
        results["slicer_modules_vatquant_attr"] = False
        results["errors"].append("slicer.modules.vatquant: {}".format(exc))

    print(json.dumps(results, indent=2))
    print("FUNCTIONAL CHECK PASS" if results["ok"] else "FUNCTIONAL CHECK FAIL")
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
