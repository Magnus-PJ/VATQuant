# VATQuant — MRI visceral adipose tissue quantification

## Status and scope

Prepared 7 September 2026. This is an implementation specification, not implemented or clinically validated software. Requirements below are proposed engineering requirements. Scanner settings are starting targets for application-specialist optimization, not verified presets for the user's installations.

Build a local, radiologist-supervised application for measuring visceral adipose tissue (VAT) from reconstructed MRI images. Begin as a Python scripted module in 3D Slicer. Do not build a foundation model, an MRI reconstruction engine, a liver-PDFF product, a fibrosis estimator, or an autonomous medical report generator.

Coding agents may help implement and test the application. No language-model inference is required during patient analysis. Numerical results must be derived from reviewed segmentation masks and verified image geometry.

Initial use: engineering development and supervised evaluation. Assess clinical validation, institutional governance, and applicable Indian medical-device requirements before patient-care deployment. Open-source licensing and clinical authorization are separate matters. [5, 12]

## 1. Acquisition contract

### Scanner-specific acquisition

- GE SIGNA Creator 1.5 T: an installed 3D LAVA Flex or suitable IDEAL-based fat/water-separated acquisition. LAVA Flex provides fat-only, water-only, in-phase, and opposed-phase reconstructions. Availability on this particular scanner is not yet confirmed. [1]
- Siemens 0.55 T: an installed 3D VIBE Dixon acquisition. Free.Max and Free.Star product documentation describes VIBE Dixon; the user's exact model and installed options remain unconfirmed. [2, 3]
- A three-plane localizer precedes the Dixon acquisition.
- IDEAL IQ, LiverLab, PDFF, T2*, DWI, MRCP, contrast enhancement, spectroscopy, and elastography are not requirements of this VAT-only software specification.
- Fat-only and water-only are paired reconstructions of the same acquisition, not necessarily separate scan sequences. Multiple acquisition slabs may be necessary for coverage.

### Proposed acquisition targets

Use a noncontrast, contiguous 3D acquisition, preferably axial for the initial local workflow. Start protocol optimization around 2–3 mm acquired in-plane resolution and 4–6 mm acquired partition thickness, adjusted to the actual scanner, signal-to-noise ratio, patient size, and breath-hold ability. These are planning targets, not clinical acceptance limits. Do not equate interpolated reconstruction resolution with acquired resolution.

For the volumetric endpoint, acquire from above the diaphragmatic domes through the femoral heads, including the abdominal wall laterally. Use a documented respiratory instruction. Preserve complete coverage without gaps. If several slabs are required, account for overlap and respiratory displacement; simple summation of all slab volumes is prohibited.

Retain original DICOM fat-only and water-only series; retain in-phase and opposed-phase reconstructions when available for quality assessment. Screenshots, JPEGs, or secondary-capture images are not quantitative input.

### Analysis boundaries

Before analyzing patients, the supervising radiologist must approve a versioned anatomical SOP. Suggested initial full-coverage endpoint: protocol-defined abdominopelvic VAT beneath the diaphragm down to the superior femoral-head boundary. Specify the exact inferior landmark rule, the physical upper/lower limits, and inclusion of retroperitoneal/perirenal fat. This is a chosen endpoint, not a claim that all published VAT methods use these limits.

An abbreviated lumbar or liver acquisition may support a separately named regional endpoint. Never label it total abdominal VAT. An optional single-slice endpoint is VAT cross-sectional area at a precisely documented L3 plane. Area is not volume.

## 2. Architecture

Reuse 3D Slicer for DICOM import, image display, multiplanar navigation, Segment Editor, and segmentation storage. Keep geometry and quantitative computations in a separately testable Python core. Slicer provides a Python extension environment and built-in editing/statistics functionality. [4–6]

Proposed components:

| Component | Responsibility |
|---|---|
| Case manager | Local case identity, study/series selection, protocol version, analysis status |
| DICOM adapter | Import, paired-series identification, original metadata and source references |
| Geometry validator | Spacing/orientation/position, frame ordering, duplication, coverage and pairing checks |
| Segmentation initializer | Propose fat candidate mask; optional validated MRI model adapter later |
| Anatomical editor | Abdominal compartment ROI, exclusions, VAT correction, undo/redo |
| Measurement core | Area and volume from reviewed binary labelmaps with physical geometry |
| Quality controller | Technical warnings, required review tasks, export blockers |
| Provenance/export | Masks, metrics, QC snapshots, software versions, source identifiers and audit record |

Do not rewrite a DICOM viewer, implement a PACS server, or introduce a cloud dependency for the first version. Use NumPy for array calculations and Slicer/ITK/SimpleITK for spatial operations. A later standalone interface can reuse the tested core.

## 3. Input and geometry safety

1. Group by study/series and actual image/frame metadata. Do not assume SeriesDescription alone identifies fat versus water.
2. Let the operator confirm the fat-only and water-only roles using image previews. Reject ambiguous or mismatched pairs.
3. Verify patient/study compatibility and spatial alignment, including FrameOfReferenceUID where applicable. A shared UID alone is not sufficient proof of identical geometry.
4. Preserve voxel dimensions, origin, direction cosines, dimensions, and source references. Apply documented intensity transforms as appropriate; keep originals immutable.
5. For classic parallel slices, order using ImagePositionPatient projected onto the slice normal from ImageOrientationPatient. Do not use filename, InstanceNumber, or SliceLocation alone.
6. Detect repeated slices, repeated temporal phases, mixed echoes, orientation changes, missing slices, inconsistent spacing, and inconsistent fat/water coverage.
7. Implement and test Enhanced MR per-frame/shared functional-group handling before claiming support. Otherwise reject that input format explicitly with a useful message.
8. Never silently substitute 1 mm spacing when geometry is missing.
9. Distinguish acquired slice thickness from reconstructed centre-to-centre spacing. For regular reconstructed 3D grids, use the actual validated voxel transform for measurement. [7, 8]
10. Do not add a 3D mask volume from each of four Dixon contrasts; they represent the same anatomy.
11. Reject unsupported irregular or missing-slice data for volumetric reporting. Supporting sampled-slice estimation later requires a separately named, validated method.
12. Detect slab overlap before combining slabs. Initial release may explicitly reject multislab stitching and instead accept only verified, correctly assembled volumes. Do not crop, interpolate, or add slabs silently.
13. When resampling masks is necessary, use label-preserving interpolation, preserve transforms, and return final masks to the defined measurement grid. Image interpolation and labelmap interpolation are different operations.
14. Preserve consistent coordinate conventions. Test conversions between DICOM LPS, Slicer RAS/IJK, and NumPy KJI indexing. [8]

## 4. Semi-automatic segmentation baseline

Begin with a human-supervised baseline. No training dataset is required to implement this baseline.

### Working masks

- Valid anatomical coverage mask.
- Candidate adipose-tissue mask.
- Radiologist-defined internal abdominal/pelvic compartment mask.
- Exclusion mask for non-VAT structures or false positives.
- Final VAT mask.

SAT output is optional and out of the first version's required report. It may still be useful visually to understand the abdominal-wall boundary.

### Workflow

1. Display matched fat-only and water-only images with linked cursors.
2. Inspect for swaps, motion, wraparound, clipping, and incomplete coverage.
3. Propose a candidate adipose mask using an adjustable, per-acquisition classifier or threshold based on the fat-only image. Start with a transparent method; preview its effect and permit correction.
4. Let the operator draw the internal compartment boundaries on appropriate slices; allow contour interpolation to reduce effort. Interpolation must be reviewed, not treated as anatomical truth.
5. Exclude abdominal-wall and paraspinal muscle fat, vertebral marrow, organ parenchyma, intraluminal contents, and other non-VAT signal. Record the chosen treatment of retroperitoneal/perirenal fat in the SOP.
6. Combine masks: `VAT = candidate_adipose AND approved_compartment AND valid_coverage AND NOT exclusions`.
7. Permit direct painting, erasing, contour editing, and rollback of the final VAT labelmap. Review the full volume in orthogonal views.
8. Save proposed and corrected masks separately when evaluating an algorithm.

A large circle around the abdomen is not a valid compartment model. Thresholding alone identifies bright signal, not its anatomical depot. Connected-component filtering or smoothing must not silently delete small genuine mesenteric fat deposits or fill intervening organs/bowel.

### Fat/water signal ratio

An optional feature is `F / (F + W + epsilon)`, limited to adequately signal-bearing tissue with documented compatible channel scaling. It is a signal-based classifier feature, NOT automatically proton-density fat fraction. Do not independently normalize fat and water and then interpret the ratio quantitatively. Do not sum this ratio over the abdomen and call the result VAT. No universal fixed MRI intensity or fat-ratio threshold should be treated as validated across both scanners.

Do not use CT Hounsfield-unit thresholds for MRI.

## 5. Measurement specification

The measurement engine consumes an approved binary VAT mask and its verified geometry; it does not consume an LLM's estimate.

For a regular 3D voxel grid with transform matrix `A` mapping voxel-index increments to millimetres:

`voxel_volume_mm3 = abs(det(A[:3, :3]))`

`VAT_volume_mL = count_nonzero(VAT) * voxel_volume_mm3 / 1000`

`VAT_volume_L = VAT_volume_mL / 1000`

For an orthogonal grid the determinant is equivalent to `dx * dy * dz`. Nonlinear transformed masks must be mapped back to the chosen native measurement grid or handled by a separately validated volume method.

For a supported single-slice plane:

`VAT_area_cm2 = count_nonzero(VAT_on_plane) * pixel_area_mm2 / 100`

Record the exact plane, its physical transform, landmark definition, and whether it is native axial or a resampled anatomical axial plane. Do not label an arbitrary oblique acquired plane as standardized L3 axial area.

Example: 120,000 VAT voxels with dimensions 2 × 2 × 5 mm produce 2,400 mL = 2.4 L. This is a mathematical test example, not a patient result.

Report geometric adipose-tissue volume. Do not report lipid mass, hepatic PDFF, a bioimpedance-style visceral-fat score, whole-body fat percentage, or disease risk from these calculations. Do not multiply single-slice area by an arbitrary abdominal length to invent a total volume.

Primary measurements must use the binary voxel labelmap rather than a cosmetically smoothed rendering mesh. [6]

## 6. Quality gates and review

Analysis states: `IMPORTED`, `QC_PENDING`, `SEGMENTATION_DRAFT`, `REVIEW_REQUIRED`, `REVIEWED`, `REJECTED`.

All prototype exports must remain marked as development/evaluation results. Reviewer approval does not itself establish clinical authorization.

Block a final volumetric result for missing/invalid geometry, unsupported input, unresolved duplicate/missing slices, mismatched channels, incomplete intended VAT coverage, unresolved slab combination, or unreviewed segmentation. Permit storage of rejected cases and preliminary masks so failures are not lost.

Require reviewer assessment of fat/water swaps, motion, wraparound, abdominal-wall boundaries, and exclusion of non-VAT structures. In the first version, these may be human checks rather than claimed automatic detectors. Reacquisition or validated correction is preferable to silently guessing swapped anatomy.

A field-of-view problem affecting SAT alone does not necessarily make all VAT unmeasurable, but the reviewer must determine whether internal VAT coverage and artifact-free imaging remain adequate. Record limitations; do not silently change the endpoint.

For follow-up comparisons require compatible acquisition, ROI definition, anatomical coverage, and analysis version. Otherwise display non-comparability, not an unqualified percentage change.

## 7. Output contract

Save:

- Original source references and a pseudonymous analysis identifier.
- Final VAT labelmap in `.seg.nrrd` and/or NIfTI with physical geometry.
- Optional candidate/cavity/exclusion masks for reproducibility.
- JSON metrics and provenance; CSV summary.
- QC images for review, clearly distinguished from quantitative source data.
- A templated human-readable evaluation report.

Suggested JSON fields:

```json
{
  "schema_version": "1.0",
  "case_id": "pseudonymous-example",
  "source_series": [],
  "scanner": {"manufacturer": null, "model": null, "field_strength_T": null},
  "protocol_id": null,
  "acquisition_coverage": null,
  "analysis_roi_definition": null,
  "retroperitoneal_fat_rule": null,
  "measurement_grid": {"shape": null, "affine_mm": null},
  "vat_volume_mL": null,
  "vat_volume_L": null,
  "vat_area_L3_cm2": null,
  "l3_plane_definition": null,
  "qc_flags": [],
  "review_status": "QC_PENDING",
  "reviewer_id": null,
  "review_timestamp": null,
  "software_version": null,
  "algorithm_version": null,
  "model_weights_hash": null,
  "analysis_parameters": {},
  "intended_use_status": "development_evaluation"
}
```

Do not store null/failed measurements as zero. Any segmentation edit invalidates previous review status and triggers recalculation.

DICOM SEG export with source-image references can be a later integration requirement. `highdicom` supports building these objects; verify PACS compatibility separately. [9]

## 8. Optional automation, after the baseline works

### FatSegNet

Research pipeline for VAT/SAT segmentation on Dixon MRI. The repository carries an Apache-2.0 code license and expects paired fat/water NIfTI inputs in its workflow. Inspect dependencies, weights, orientation, anatomical coverage, and all model-related terms before reuse. Critically, its documented fixed-size crop/pad behavior can truncate a different acquisition; do not deploy it unchanged without checking that all intended anatomy survives preprocessing. [10]

### TotalSegmentator MRI

The `tissue_types_mr` task can produce `subcutaneous_fat`, `torso_fat`, and `skeletal_muscle`; the developer recommends Dixon fat-only input for fat classes. This task has licensing requirements separate from the freely available general tasks. Obtain the appropriate commercial terms for a commercial service. `torso_fat` is not automatically the application's SOP-defined VAT: apply validated anatomical restriction and review. The repository states it is not itself intended for clinical use. [11]

### A locally trained model

A two-channel fat/water nnU-Net segmentation model is a possible later project. Training requires accurately annotated cases; the first ten patients are an engineering pilot, not evidence of generalization across two field strengths. Keep every scan/slice of one patient within one data partition. Save independent held-out test cases and test scanners separately. Freeze and version model weights. [13]

## 9. Verification and validation plan

### Deterministic unit tests

- Known binary masks and known voxel transforms return the exact mathematical volume.
- Millimetre cubed to mL/L and square millimetre to square centimetre conversions are correct.
- Reversed file order does not alter results.
- Rotating or permuting a grid with consistent geometry does not alter physical volume.
- Missing geometry raises an error rather than assuming unit spacing.
- Duplicates, missing slices, mixed contrasts/timepoints, and mismatched channels fail safely.
- Both supported classic and enhanced DICOM test fixtures load correctly; unsupported fixtures are rejected.
- Save/reload preserves mask, geometry, metric and provenance.
- Native-to-model-to-native transformations have quantified geometric effects.
- Overlapping slabs cannot be double-counted.
- Display window/level changes do not alter a saved mask's volume.
- Edited masks reset reviewer approval.
- Tests and logs contain no real patient identifiers.

### Anatomical and clinical performance evaluation

Use the initial ten scans to test import, image quality, annotation usability, and corrections. Compare masks and measurements against independently created expert references. Evaluate both uncorrected algorithm output and the final human-reviewed workflow when applicable.

Measure absolute volume error, relative error when meaningful, signed bias, Bland–Altman limits, segmentation overlap, failure rate, and correction time. Assess intra-/inter-reader variation and scan-rescan repeatability with patient repositioning in a suitable evaluation subset. Establish intended-use performance requirements prospectively rather than choosing them after seeing results.

Validate the GE and Siemens workflows separately; cross-scanner interchangeability needs paired evidence. Include representative body habitus and challenging anatomy. Ten successfully processed examinations and a high correlation coefficient alone are not sufficient proof of clinical reliability.

Assess applicable CDSCO medical-device software requirements, quality/risk management, evidence, privacy controls, labeling and release governance. This specification does not assign a device class or establish an exemption. [12]

## 10. Development and privacy constraints

Develop using synthetic images and appropriately de-identified local evaluation data. Keep identifiable clinical DICOM outside the coding-agent project tree, chat uploads, source repository, issue reports, and logs. Inspect headers and burned-in pixel identifiers before any approved external transfer.

Disable outbound analysis traffic by design. Store runtime data in a separate restricted directory. Add access controls, encrypted storage where appropriate, local audit trails, backup/restore tests, and explicit retention rules. Review any tool telemetry or model-weight downloads before clinical deployment.

Pin the chosen stable dependencies and document tested versions. Do not equate package installation success with validation. Optional GPU inference is a later feature; the semi-automatic baseline should support a normal local workstation without an inference GPU requirement.

## 11. Recommended implementation order

1. Create module skeleton and synthetic fixtures; implement and test geometry and metric core.
2. Implement import of the site's verified de-identified DICOM formats and explicit series pairing.
3. Add manual VAT editing and exact labelmap-based measurements.
4. Add semi-automatic candidate segmentation and compartment-mask workflow.
5. Add QC states, immutable source references, structured exports, and review audit.
6. Evaluate local patient cases against independent expert reference masks.
7. Only then evaluate pretrained model adapters, DICOM SEG/PACS integration, and a standalone interface.

Deliver source code, installation instructions, test fixtures without patient data, test results, an operator guide, an algorithm/ROI definition document, a limitations list, and a validation worksheet. Do not describe unfinished or unvalidated capabilities as clinical features.

## Source documents checked

The specifications and acceptance requirements above are proposed design choices. The following primary/official sources support the named acquisition/software capabilities and regulatory context; none establishes that this proposed application is validated.

[1] GE LAVA Flex:
https://www.gehealthcare.com/en/products/magnetic-resonance-imaging/applications/lava-flex-body

[2] Siemens MAGNETOM Free.Max:
https://www.siemens-healthineers.com/magnetic-resonance-imaging/high-v-mri/magnetom-free-max

[3] Siemens MAGNETOM Free.Star:
https://www.siemens-healthineers.com/magnetic-resonance-imaging/high-v-mri/magnetom-free-star

[4] Slicer Segment Editor:
https://slicer.readthedocs.io/en/latest/user_guide/modules/segmenteditor.html

[5] Slicer licensing/intended use:
https://slicer.readthedocs.io/en/latest/user_guide/about.html

[6] Slicer Segment Statistics:
https://slicer.readthedocs.io/en/latest/user_guide/modules/segmentstatistics.html

[7] DICOM Image Plane Module:
https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.6.2.html

[8] SimpleITK physical image geometry:
https://simpleitk.readthedocs.io/en/master/fundamentalConcepts.html

[9] highdicom quick start:
https://highdicom.readthedocs.io/en/latest/quickstart.html

[10] FatSegNet repository:
https://github.com/deep-mi/FatSegNet

[11] TotalSegmentator repository, task and licensing documentation:
https://github.com/wasserth/TotalSegmentator

[12] CDSCO 2026 Guidance Document on Medical Device Software:
https://cdsco.gov.in/opencms/export/sites/CDSCO_WEB/Pdf-documents/Guidance-document-on-Medical-Device-Software-under-MDR-2017.pdf

[13] nnU-Net:
https://github.com/MIC-DKFZ/nnUNet

Additional methodological references:
- Nowak et al., automated volumetric and single-slice body-composition MRI:
  https://link.springer.com/article/10.1007/s00261-025-05170-w
- Nayak et al., body-composition profiling at 0.55 T:
  https://pubmed.ncbi.nlm.nih.gov/37125645/
- Slicer Python examples:
  https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html
