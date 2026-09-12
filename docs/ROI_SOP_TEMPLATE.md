# Anatomical ROI SOP template (versioned)

Fill and version this document before analysing evaluation cases. Published VAT methods are not interchangeable solely because they share the label “VAT.”

| Field | Value |
| --- | --- |
| Protocol ID | VAT-AP-v0.1 |
| Effective date | |
| Supervising radiologist | |
| Superior boundary rule | e.g. beneath the diaphragmatic domes |
| Inferior boundary rule | e.g. superior femoral-head boundary (specify exact landmark rule) |
| Coverage | abdominopelvic, contiguous, no gaps in measurement region |
| Retroperitoneal / perirenal fat | Include / Exclude (choose one and justify) |
| Abdominal-wall / SAT | Excluded from VAT |
| Paraspinal intramuscular fat | Excluded |
| Vertebral marrow | Excluded |
| Organ parenchyma fat signal | Excluded |
| Intraluminal / bowel contents | Excluded |
| Primary endpoint | Protocol-defined abdominopelvic VAT volume (mL / L) |
| Optional secondary endpoint | VAT area at documented L3 plane (cm²) — separately named |
| Acquisition notes (GE) | 3D LAVA Flex fat/water when available |
| Acquisition notes (Siemens) | 3D VIBE Dixon fat/water when available |
| Software version pinned | vatquant-core 0.1.0 |
| Change log | |

## Operator confirmation checklist

1. Fat-only and water-only roles confirmed by preview (not description alone).
2. Geometry validation passed (spacing, orientation, no duplicates/gaps).
3. Compartment and exclusions reviewed in axial, coronal, and sagittal.
4. Final VAT mask reviewed before approval.
5. Export marked `development_evaluation` until clinical validation is complete.
