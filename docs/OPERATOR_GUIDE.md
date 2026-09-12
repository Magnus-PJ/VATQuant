# VATQuant operator guide (3D Slicer module)

**Status: development / evaluation only — not clinically validated.**  
All exports use `intended_use_status: development_evaluation`.

## Prerequisites

1. Stable **3D Slicer 5.12.x** installed.
2. This repository at `C:\Users\paul.joy\Projects\VATQuant` with `vatquant_core` present (no need to activate the project venv inside Slicer; the module adds the repo root to `sys.path`).
3. Optional: generate a synthetic paired Dixon case for practice:

```powershell
cd C:\Users\paul.joy\Projects\VATQuant
.\.venv\Scripts\Activate.ps1
python scripts\make_synthetic_case.py --out tmp\synthetic_case
```

## Enable the module

1. Start 3D Slicer.
2. **Edit → Application Settings → Modules**.
3. Under **Additional module paths**, add:

```text
C:\Users\paul.joy\Projects\VATQuant\VATQuant
```

(This folder must contain `VATQuant.py`.)

4. Restart Slicer.
5. Open module **VATQuant** (category: Quantification), or search “VATQuant” in the module finder.

## Workflow

1. **Case panel** — enter Case ID, Protocol ID, ROI definition, retroperitoneal rule, Reviewer ID.
2. **Load volumes**
   - Preferred for verified classic MR folders: **Load fat DICOM folder…** / **Load water DICOM folder…** (uses `vatquant_core` integrity checks), **or**
   - Load via Slicer’s DICOM browser / Add Data, then pick the volume nodes in the fat/water selectors.
3. **Validate pair / geometry** — review the geometry report (spacing, centre-to-centre vs SliceThickness when available). Fix or reject bad data; do not proceed on failures.
4. **Confirm roles** — visually confirm fat-only vs water-only, then check the confirmation box.
5. **Create / reset VATQuant segments** — creates `Candidate`, `Compartment`, `Coverage`, `Exclusion`, `VAT`. Coverage defaults to full FOV if empty.
6. **Open Segment Editor** — edit Candidate (threshold on fat), Compartment (anatomical cavity), Exclusions. Use paint, erase, threshold, Fill between slices. Review axial/coronal/sagittal.
7. **Compose VAT mask** — computes  
   `VAT = Candidate AND Compartment AND Coverage AND NOT Exclusion` via `vatquant_core`.
8. **Measure VAT volume (labelmap)** — physical volume from verified geometry (not a closed surface).
9. **Mark reviewed** — only after roles confirmed, volume measured, and no blockers.
10. **Export JSON / CSV / NRRD…** — writes metrics + final VAT mask. Review status must be `REVIEWED`.

## Quality rules (v1)

- Classic single-frame MR only when loading via VATQuant DICOM folders.
- Multi-slab / Enhanced MR / duplicate or missing slices are rejected by the core.
- Editing segments after review invalidates approval; re-measure and re-review.
- Do not treat `F/(F+W)` (if used later) as PDFF or as VAT volume.

## Headless smoke test

With `PythonSlicer.exe` from the Slicer install:

```powershell
& "<SlicerInstall>\bin\PythonSlicer.exe" C:\Users\paul.joy\Projects\VATQuant\scripts\slicer_smoke_test.py
```

Expect `SMOKE PASS` and matching synthetic volume.

## Privacy

Keep identifiable patient DICOM outside the git repository (e.g. `C:\VATQuant_runtime\`). Never upload PHI to chats or commit it.
