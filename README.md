# VATQuant

**Status: development / evaluation only — not clinically validated.**

Local Python core for measuring visceral adipose tissue (VAT) volume from paired Dixon MRI fat-only and water-only images. Measurements come from reviewed binary labelmaps and verified physical geometry. No LLM estimation. No liver-PDFF, fibrosis, disease-risk, or whole-body fat percentage features.

This repository currently implements **Phases 1–2** of the developer specification: a Slicer-independent `vatquant_core` package with geometry validation, classic DICOM loading, mask composition, volume/area measurement, QC states, and JSON/CSV/NRRD export — verified on **synthetic** data only.

Phase 3 Slicer module is available: launch via `scripts\launch_slicer_vatquant.ps1` or the Start Menu shortcut **3D Slicer 5.12.3 (VATQuant)**. See [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md).

## Quick start

```powershell
cd C:\Users\paul.joy\Projects\VATQuant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
python scripts\make_synthetic_case.py
python scripts\check_py39_syntax.py
```

## Privacy

Do not place identifiable patient DICOM in this repository, chats, logs, or test fixtures. Use synthetic phantoms or appropriately de-identified data stored outside the project tree (e.g. `C:\VATQuant_runtime\`).

## Documentation

- [Developer specification](docs/VAT_Only_MRI_Developer_Specification.md)
- [Install](docs/INSTALL.md)
- [Limitations](docs/LIMITATIONS.md)
- [ROI SOP template](docs/ROI_SOP_TEMPLATE.md)
- [Validation worksheet](docs/VALIDATION_WORKSHEET.md)
- [Operator guide (Slicer)](docs/OPERATOR_GUIDE.md)
- [Phase 3 Slicer notes](docs/PHASE3_SLICER.md)
- [Operator guide (Slicer)](docs/OPERATOR_GUIDE.md)
- [Phase 3 Slicer notes](docs/PHASE3_SLICER.md)
