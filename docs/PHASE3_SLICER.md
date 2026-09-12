# Phase 3 — 3D Slicer scripted module

## Status

**Implemented (per-user install, no admin required).**

3D Slicer **5.12.3** was extracted to:

```text
C:\Users\paul.joy\AppData\Local\slicer.org\Slicer-5.12.3\
```

- `Slicer.exe` — GUI application  
- `bin\PythonSlicer.exe` — Slicer Python 3.12.10  

The VATQuant scripted module lives at [`VATQuant/VATQuant.py`](../VATQuant/VATQuant.py). User settings `AdditionalPaths` point at `C:/Users/paul.joy/Projects/VATQuant/VATQuant` (the folder that contains `VATQuant.py`).

## Launch

**Option A — Start Menu:** `3D Slicer 5.12.3 (VATQuant)`  

**Option B — PowerShell launcher:**

```powershell
C:\Users\paul.joy\Projects\VATQuant\scripts\launch_slicer_vatquant.ps1
```

**Option C — Direct:**

```powershell
& "C:\Users\paul.joy\AppData\Local\slicer.org\Slicer-5.12.3\Slicer.exe" --additional-module-path "C:\Users\paul.joy\Projects\VATQuant\VATQuant"
```

Then open module **VATQuant** (Quantification).

## Operator guide

See [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md).

## Smoke test

```powershell
& "C:\Users\paul.joy\AppData\Local\slicer.org\Slicer-5.12.3\Slicer.exe" `
  --no-main-window --no-splash `
  --additional-module-path "C:\Users\paul.joy\Projects\VATQuant\VATQuant" `
  --python-script "C:\Users\paul.joy\Projects\VATQuant\scripts\slicer_smoke_test.py" `
  --exit-after-startup
```

Expect console output containing `SMOKE PASS`.

## Notes

- This is a **portable / extracted** layout under the user profile — no machine-wide install, no admin elevation.
- Keep identifiable DICOM outside the git repo.
- Prototype outputs remain `development_evaluation` only.
