#!/usr/bin/env python
"""Write a synthetic paired Dixon DICOM case for manual inspection / e2e demos."""

from __future__ import annotations

import argparse
import json
import os
import sys

# Allow running without install
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from vatquant_core.dicom_series import load_series_from_directory
from vatquant_core.export import export_case_bundle
from vatquant_core.masks import combine_vat_mask
from vatquant_core.measurement import measure_volume
from vatquant_core.pairing import suggest_role, validate_pair
from vatquant_core.qc import CaseRecord
from vatquant_core.synthetic import write_paired_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Create synthetic VATQuant case")
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT, "tmp", "synthetic_case"),
        help="output directory",
    )
    parser.add_argument("--manufacturer", default="GE", choices=["GE", "Siemens"])
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    meta = write_paired_case(
        args.out,
        manufacturer=args.manufacturer,
        shape=(16, 40, 40),
        spacing=(2.0, 2.0, 5.0),
        seed=42,
    )
    phantom = meta["phantom"]
    fat = load_series_from_directory(meta["fat_dir"])
    water = load_series_from_directory(meta["water_dir"])
    validate_pair(fat, water)
    print("Fat role hint:", suggest_role(fat))
    print("Water role hint:", suggest_role(water))

    vat = combine_vat_mask(
        phantom.candidate_mask,
        phantom.compartment_mask,
        phantom.coverage_mask,
        phantom.exclusion_mask,
    )
    result = measure_volume(vat, fat.geometry)
    print(
        "VAT voxels={} volume_mL={:.6f} expected_mL={:.6f}".format(
            result.voxel_count, result.volume_mL, phantom.expected_vat_volume_mL
        )
    )

    case = CaseRecord(case_id="synthetic-demo-042")
    case.roles_confirmed = True
    case.protocol_id = "VAT-AP-v0.1-dev"
    case.analysis_roi_definition = "synthetic full-coverage compartment"
    case.retroperitoneal_fat_rule = "included_in_compartment"
    case.volume_result = result
    case.scanner = {
        "manufacturer": fat.source_refs.manufacturer,
        "model": fat.source_refs.model,
        "field_strength_T": fat.source_refs.field_strength_T,
    }
    case.source_series = [
        {"role": "fat", "series_uid": fat.source_refs.series_uid},
        {"role": "water", "series_uid": water.source_refs.series_uid},
    ]
    case.mark_reviewed("synthetic-operator")
    export_dir = os.path.join(args.out, "export")
    paths = export_case_bundle(case, fat.geometry, vat, export_dir)
    summary = {
        "case_dir": args.out,
        "expected_vat_volume_mL": phantom.expected_vat_volume_mL,
        "measured_vat_volume_mL": result.volume_mL,
        "exports": paths,
        "intended_use_status": "development_evaluation",
    }
    summary_path = os.path.join(args.out, "demo_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")
    print("Wrote", summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
