# Validation worksheet

Use one row per examination. Keep identifiable DICOM outside the repository. This worksheet does **not** by itself establish clinical validation.

## Software verification (synthetic) — complete in CI / local pytest

| Check | Pass? | Notes |
| --- | --- | --- |
| Known mask × spacing → exact mL/L | | |
| mm³↔mL↔L and mm²↔cm² conversions | | |
| Filename shuffle / reverse order unchanged | | |
| Missing geometry fails closed | | |
| Duplicates / missing slices / mixed echoes fail | | |
| Enhanced MR rejected | | |
| Multi-slab / overlap rejected | | |
| Fat/water mismatch rejected | | |
| Mask save/reload preserves volume | | |
| Edit resets REVIEWED status | | |

## Anatomical evaluation (de-identified local cases)

Separate tables for **GE** and **Siemens**. Do not pool as interchangeability evidence.

| Case ID (pseudo) | Scanner | Field (T) | Coverage OK? | Ref volume mL | Software volume mL | Abs error mL | % error | Dice/overlap | Correction time (min) | QC | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | GE / Siemens | | | | | | | | | | |

## Agreement / repeatability (when available)

| Metric | Result | Notes |
| --- | --- | --- |
| Bias (signed mL) | | |
| Bland–Altman limits | | |
| Intra-reader | | |
| Inter-reader | | |
| Scan–rescan (repositioned) | | |

## Decision gate

- [ ] Software verification tests green
- [ ] ROI SOP approved and versioned
- [ ] ≥ planned GE evaluation set reviewed against independent references
- [ ] ≥ planned Siemens evaluation set reviewed separately
- [ ] Limitations documented; outputs still labelled development/evaluation
- [ ] Regulatory / governance review before any patient-care claim
