# VATQuant limitations (v0.1 core)

**Development / evaluation prototype. Not for clinical decision-making.**

## Supported in this version

- Classic single-frame MR DICOM (SOP Class `1.2.840.10008.5.1.4.1.1.4`)
- Single contiguous slab / uniform centre-to-centre spacing
- Paired fat-only and water-only series with matching geometry
- Manual / composed binary VAT labelmap volume and optional plane area
- Synthetic phantoms for software verification

## Explicitly not supported (fail closed)

- Enhanced MR Storage (`1.2.840.10008.5.1.4.1.1.4.1`)
- Multi-slab stitching or overlapping slabs
- Silent default voxel spacing when geometry is missing
- Filename / InstanceNumber-only slice ordering
- Double-counting multiple Dixon reconstructions of the same anatomy
- Automated clinical VAT without human review
- Liver PDFF, fibrosis, disease-risk scores, whole-body fat percentage
- LLM-based measurement estimation
- PACS write-back / DICOM SEG export (later phase)
- Pretrained AI models (FatSegNet, TotalSegmentator, nnU-Net) — later optional initialisers only

## Measurement caveats

- Volume is from the **binary voxel labelmap** and verified geometry, not a smoothed surface mesh.
- `F/(F+W)` is an optional candidate feature, **not** PDFF.
- Area at L3 is a separately named endpoint and must not be extrapolated to total VAT volume.
- GE and Siemens workflows require separate evaluation; success on one scanner does not validate the other.

## Regulatory

3D Slicer is a research platform. Building this module does not confer clinical authorization. Assess applicable CDSCO medical-device software requirements before patient-care use in India.
