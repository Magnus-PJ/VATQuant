# VATQuant install (Phases 1–2 core)

**Intended use: development / evaluation only. Not clinically validated.**

## Requirements

- Python 3.9+ (development tested on system Python 3.13; code must remain 3.9-compatible for future 3D Slicer)
- Windows PowerShell (or any shell)
- Git (optional)

## Setup

```powershell
cd C:\Users\paul.joy\Projects\VATQuant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Verify

```powershell
pytest
python scripts\check_py39_syntax.py
python scripts\make_synthetic_case.py --out tmp\synthetic_case
```

## Runtime data (not in the repo)

Keep de-identified evaluation DICOM outside the project tree, for example:

```text
C:\VATQuant_runtime\
  ge_cases\
  siemens_cases\
```

Never commit real patient DICOM to this repository.

## Phase 3 — 3D Slicer (per-user, no admin)

Slicer **5.12.3** is installed for this user only at:

```text
C:\Users\paul.joy\AppData\Local\slicer.org\Slicer-5.12.3\
```

Launch with the VATQuant module path:

```powershell
C:\Users\paul.joy\Projects\VATQuant\scripts\launch_slicer_vatquant.ps1
```

Or open **3D Slicer 5.12.3 (VATQuant)** from the Start Menu. Details: [PHASE3_SLICER.md](PHASE3_SLICER.md), [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md).
