# VATQuant — Project Status Brief
## MRI Visceral Adipose Tissue (VAT) Quantification

**Document purpose:** Explain what this project is trying to achieve, what has been built so far, where we are now, and what comes next — for the project owner and for an independent second opinion.

| Field | Value |
| --- | --- |
| Document date | 12 September 2026 |
| Project name | VATQuant |
| Project location | `C:\Users\paul.joy\Projects\VATQuant` |
| Software status | Development / evaluation prototype |
| Clinical status | **Not clinically validated. Not approved for patient-care decisions.** |
| Current version | vatquant-core 0.1.0 + 3D Slicer scripted module (Phase 3) |

---

## 1. Mission and aim

### Mission
Build a **local, radiologist-supervised** software pathway to measure **visceral adipose tissue (VAT) volume** from abdominal MRI Dixon fat/water images — starting on **GE 1.5 T**, then validating **Siemens 0.55 T** separately.

### Aim
Replace informal or screenshot-based estimates with a **reproducible, geometry-correct volume** derived from:

1. Original DICOM fat-only and water-only images  
2. A reviewed VAT segmentation mask  
3. Verified voxel dimensions (mm → mL / L)

### What this project is *not*
- Not a liver-fat (PDFF) calculator  
- Not a fibrosis / disease-risk / “metabolic score” product  
- Not an LLM that guesses fat from screenshots  
- Not a claim of clinical clearance or CDSCO approval  
- Not a fully automatic, unattended clinical device (yet)

---

## 2. Final goal (end state we are working toward)

A practical in-house workflow where a trained operator / radiologist can:

1. Import paired Dixon **fat-only + water-only** DICOM  
2. Confirm image quality and series roles  
3. Obtain a **VAT segmentation** (assisted, then reviewed)  
4. Compute **protocol-defined abdominopelvic VAT volume** (mL / L)  
5. Optionally report **L3 VAT area (cm²)** as a separate endpoint  
6. Export mask + metrics + provenance for audit and follow-up comparison  

Longer-term (only after measurement process is trusted):

- Optional AI as a **segmentation initializer** (not the sole source of truth)  
- Possible later standalone interface / PACS integration  
- Formal validation and regulatory assessment before patient-care use in India  

---

## 3. Clinical / scientific problem we are solving

VAT volume matters for body-composition research and metabolic risk discussions, but:

- Counting “bright pixels” is not enough — fat must be **inside the visceral compartment**  
- Volumes are only meaningful with **correct DICOM geometry**  
- Published “VAT” methods are **not interchangeable** unless anatomical boundaries match  
- GE and Siemens (and 1.5 T vs 0.55 T) need **separate evaluation**

**Primary intended endpoint (proposed):**  
Protocol-defined abdominopelvic VAT volume from beneath the diaphragm to a defined superior femoral-head boundary (exact landmarks to be locked in a versioned ROI SOP by the supervising radiologist).

---

## 4. Recommended acquisition (what images are needed)

### Minimum for VAT-only

| Scanner | Sequence (if installed/activated) | Export |
| --- | --- | --- |
| GE SIGNA Creator 1.5 T | 3D LAVA Flex (after localizer) | Fat-only + water-only DICOM; keep in/opposed-phase if available |
| Siemens 0.55 T | 3D VIBE Dixon (after localizer) | Fat-only + water-only DICOM; keep other Dixon reconstructions if available |

### Starting protocol targets (for applications specialist optimization — not fixed presets)
- Noncontrast 3D Dixon, preferably axial  
- Coverage: diaphragmatic domes → femoral heads, adequate lateral coverage  
- ~2–3 mm in-plane, ~4–6 mm partition thickness, **no gaps** in the measurement region  
- Consistent breath-hold instruction  
- **Original DICOM only** — not JPEG/screenshots  

### Not required for this VAT-only product
IDEAL IQ, LiverLab, liver PDFF, T2*, DWI, MRCP, spectroscopy, contrast, elastography.

---

## 5. Original plan (how we intended to build it)

### Platform choice
Use **3D Slicer** (viewer, multiplanar review, Segment Editor) + a custom **Python module**, rather than building a viewer from scratch.

### Architecture
Keep a Slicer-independent measurement core (`vatquant_core`) for geometry, DICOM safety, mask math, QC, and export — so logic can be tested without the GUI.

### Phased plan

| Phase | Intent | Status |
| --- | --- | --- |
| **1** | Geometry + volume math + synthetic tests | **Done** |
| **2** | Classic DICOM load, fat/water pairing, QC states, JSON/CSV/NRRD export | **Done** |
| **3** | 3D Slicer scripted module UI wrapping the core | **Done** |
| **4** | Semi-automatic candidate fat proposal (threshold / signal-ratio assist) | **Not started** |
| **5** | Evaluation on de-identified local GE then Siemens cases | **Not started** (awaiting real images) |
| **6** | Optional AI initializers, DICOM SEG/PACS, standalone UI, regulatory path | **Later** |

### Guiding development sequence
**Manual / human-reviewed measurement → semi-automatic assistance → evaluate pretrained models → train local model only if justified.**

---

## 6. What has been built (current capability)

### Software location
- Code: `C:\Users\paul.joy\Projects\VATQuant`  
- Spec: `docs\VAT_Only_MRI_Developer_Specification.md`  
- Slicer (per-user, no admin): `C:\Users\paul.joy\AppData\Local\slicer.org\Slicer-5.12.3\`  
- Launch: Start Menu **“3D Slicer 5.12.3 (VATQuant)”** or `scripts\launch_slicer_vatquant.ps1`

### Working features today
1. Load classic single-frame MR DICOM fat/water folders  
2. Geometry validation (spacing, ordering, duplicates/gaps, Enhanced MR / multi-slab rejection)  
3. Fat/water role hints + mandatory operator confirmation  
4. Create editable segments: Candidate, Compartment, Coverage, Exclusion, VAT  
5. Compose final VAT = candidate ∩ compartment ∩ coverage − exclusions  
6. Measure **labelmap volume** (mL / L) from verified geometry — not a cosmetic 3D surface  
7. QC states (including review required before final export)  
8. Export JSON + CSV + NRRD mask with `intended_use_status: development_evaluation`  
9. Synthetic phantoms + automated tests (**34 core pytest tests**; Slicer functional check **PASS**)

### What the operator must still do manually (v1)
- Confirm fat vs water visually  
- Define / edit the internal visceral compartment  
- Exclude wall fat, marrow, organs, false positives  
- Review the final mask in axial/coronal/sagittal before accepting the number  

---

## 7. Where we have reached (honest checkpoint)

```text
[####------]  ~40% of the full product journey

DONE:     Correct measurement engine + Slicer UI + synthetic verification
NOW:      Waiting for first real de-identified Dixon case(s)
NEXT:     Real-case dry run → automate candidate proposal → validate GE → validate Siemens
LATER:    Optional AI assist + integration + regulatory assessment
```

**We have a working prototype laboratory tool.**  
**We do not yet have a validated clinical measurement service.**

---

## 8. What we still need from the imaging side

### For the next milestone
One complete **GE** paired case:

```text
Desktop\VAT_GE_case01\
  FAT\      (fat-only DICOM files)
  WATER\    (water-only DICOM files)
```

Prefer de-identified DICOM. Do **not** put identifiable patient data into chat uploads or the git repository.

The coding agent on this PC **can read a Desktop folder path** if you provide it (e.g. `C:\Users\paul.joy\Desktop\VAT_GE_case01`).

### For meaningful validation later
- ~10 GE cases for workflow + reference annotations  
- Separate Siemens set  
- Versioned ROI SOP signed by supervising radiologist  
- Agreement / repeatability analysis (not correlation alone)

---

## 9. Further automation possible (maximum practical path)

| Level | What it does | Human still required? |
| --- | --- | --- |
| **Current (v1)** | Viewer + compose + exact volume | Yes — draw/edit VAT |
| **Next (Phase 4)** | Auto-propose adipose candidate; faster editing | Yes — correct + approve |
| **Batch runner** | Folder-in → validate → draft measure → export | Yes — review drafts |
| **AI initializer (later)** | FatSegNet / TotalSegmentator as starting mask | Yes — never unattended clinical |
| **Fully automatic clinical VAT** | No review | **Not appropriate** without major validation + regulatory work |

**Maximum honest automation:** auto-propose → human confirm → locked volume + audit trail.

---

## 10. Risks, limitations, and second-opinion notes

1. **3D Slicer is a research platform**, not itself a clinical approval.  
2. Building a module does **not** equal CDSCO clearance.  
3. Success on synthetic data ≠ success on real GE/Siemens patients.  
4. GE success ≠ Siemens interchangeability.  
5. Do not call Dixon signal ratio “PDFF” or invent a visceral-fat “score.”  
6. Multi-slab / Enhanced MR are rejected in v1 by design (fail closed).  
7. Patient privacy: keep identifiable DICOM out of repos, chats, and logs.

Independent reviewers should ask:
- Is the anatomical VAT definition versioned and clinically acceptable?  
- Is the measurement engine geometry-safe? *(synthetic tests say yes)*  
- Has performance been shown on *this site’s* scanners and body habitus? *(not yet)*  
- Is intended use clearly limited to development/evaluation until validated?

---

## 11. Success criteria for the next 90 days (proposed)

1. Import ≥1 real GE fat/water case with correct geometry  
2. Complete ≥1 full human-reviewed measurement + export  
3. Approve ROI SOP v0.1  
4. Implement Phase 4 candidate automation  
5. Process a small GE pilot set with independent reference masks  
6. Decide whether Siemens pilot can start with the same software  

---

## 12. Key documents in the project

| Document | Path |
| --- | --- |
| Developer specification | `docs\VAT_Only_MRI_Developer_Specification.md` |
| Install notes | `docs\INSTALL.md` |
| Limitations | `docs\LIMITATIONS.md` |
| ROI SOP template | `docs\ROI_SOP_TEMPLATE.md` |
| Validation worksheet | `docs\VALIDATION_WORKSHEET.md` |
| Operator guide (Slicer) | `docs\OPERATOR_GUIDE.md` |
| Phase 3 Slicer notes | `docs\PHASE3_SLICER.md` |
| This status brief | `docs\PROJECT_STATUS_BRIEF.md` (and Desktop copy) |

---

## 13. One-paragraph summary (for email / second opinion)

> VATQuant is an in-progress, radiologist-supervised MRI visceral fat volumetry prototype. We intentionally avoided liver-PDFF and screenshot/LLM estimation. We built a tested Python measurement core and a 3D Slicer module that imports paired Dixon fat/water DICOM, enforces geometry safety, supports human-edited VAT segmentation, and exports volume with provenance — verified on synthetic data only. The immediate next step is a real de-identified GE Dixon case; further automation (auto fat proposal, batching, optional AI initializers) comes after that. The software is for development/evaluation until site validation and regulatory assessment support clinical use.

---

## 14. Contact / ownership (fill in)

| Role | Name |
| --- | --- |
| Project owner | |
| Supervising radiologist | |
| Technical lead / developer support | Cursor-assisted local build on owner workstation |
| Intended second-opinion reviewer | |

---

*End of brief. Generated for internal understanding and independent review. Not a clinical manual and not a regulatory submission.*
