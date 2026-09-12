"""VATQuant — 3D Slicer scripted module for MRI VAT measurement.

Development / evaluation only. Not clinically validated.
Wraps vatquant_core; reuses Slicer DICOM viewing and Segment Editor.
"""

from __future__ import annotations

import logging
import os
import sys

import numpy as np
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
    ScriptedLoadableModuleWidget,
)
from slicer.util import VTKObservationMixin

# ---------------------------------------------------------------------------
# Ensure repo root is importable so vatquant_core resolves next to this module
# ---------------------------------------------------------------------------
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_MODULE_DIR, os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from vatquant_core.errors import PairingError, QCBlockedError, VATQuantError  # noqa: E402
from vatquant_core.export import export_case_bundle  # noqa: E402
from vatquant_core.geometry import ImageGeometry  # noqa: E402
from vatquant_core.masks import combine_vat_mask  # noqa: E402
from vatquant_core.measurement import measure_volume  # noqa: E402
from vatquant_core.pairing import suggest_role, validate_pair  # noqa: E402
from vatquant_core.qc import AnalysisState, CaseRecord  # noqa: E402
from vatquant_core.version import ALGORITHM_VERSION, __version__  # noqa: E402

SEGMENT_NAMES = ("Candidate", "Compartment", "Coverage", "Exclusion", "VAT")


class VATQuant(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "VATQuant"
        self.parent.categories = ["Quantification"]
        self.parent.dependencies = []
        self.parent.contributors = ["VATQuant developers"]
        self.parent.helpText = (
            "MRI visceral adipose tissue (VAT) segmentation and geometric volume "
            "measurement. Development/evaluation only — not clinically validated.\n\n"
            "Load paired Dixon fat/water volumes, edit segments in Segment Editor, "
            "compose VAT, measure labelmap volume via vatquant_core, and export."
        )
        self.parent.acknowledgementText = (
            "Built on 3D Slicer and vatquant_core. Intended use status: development_evaluation."
        )


class VATQuantWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = None
        self._updating = False

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = VATQuantLogic()

        banner = qt.QLabel(
            "<b>DEVELOPMENT / EVALUATION ONLY</b> — not clinically validated. "
            "intended_use_status=development_evaluation"
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "QLabel { background:#fff3cd; color:#664d03; padding:8px; border:1px solid #ffecb5; }"
        )
        self.layout.addWidget(banner)

        # --- Case ---
        caseCollapsible = ctkCollapsibleButton("Case")
        self.layout.addWidget(caseCollapsible)
        caseForm = qt.QFormLayout(caseCollapsible)

        self.caseIdEdit = qt.QLineEdit("case-001")
        caseForm.addRow("Case ID", self.caseIdEdit)
        self.protocolEdit = qt.QLineEdit("VAT-AP-v0.1-dev")
        caseForm.addRow("Protocol ID", self.protocolEdit)
        self.roiDefEdit = qt.QLineEdit("protocol-defined abdominopelvic VAT")
        caseForm.addRow("ROI definition", self.roiDefEdit)
        self.retroEdit = qt.QLineEdit("include_per_SOP")
        caseForm.addRow("Retroperitoneal rule", self.retroEdit)
        self.reviewerEdit = qt.QLineEdit("operator")
        caseForm.addRow("Reviewer ID", self.reviewerEdit)

        # --- Volumes ---
        volCollapsible = ctkCollapsibleButton("Fat / water volumes")
        self.layout.addWidget(volCollapsible)
        volForm = qt.QFormLayout(volCollapsible)

        self.fatSelector = slicer.qMRMLNodeComboBox()
        self.fatSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.fatSelector.selectNodeUponCreation = True
        self.fatSelector.addEnabled = False
        self.fatSelector.removeEnabled = False
        self.fatSelector.noneEnabled = True
        self.fatSelector.showHidden = False
        self.fatSelector.setMRMLScene(slicer.mrmlScene)
        volForm.addRow("Fat-only volume", self.fatSelector)

        self.waterSelector = slicer.qMRMLNodeComboBox()
        self.waterSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.waterSelector.selectNodeUponCreation = True
        self.waterSelector.addEnabled = False
        self.waterSelector.removeEnabled = False
        self.waterSelector.noneEnabled = True
        self.waterSelector.showHidden = False
        self.waterSelector.setMRMLScene(slicer.mrmlScene)
        volForm.addRow("Water-only volume", self.waterSelector)

        loadRow = qt.QHBoxLayout()
        self.fatDirButton = qt.QPushButton("Load fat DICOM folder…")
        self.waterDirButton = qt.QPushButton("Load water DICOM folder…")
        loadRow.addWidget(self.fatDirButton)
        loadRow.addWidget(self.waterDirButton)
        volForm.addRow(loadRow)

        self.roleHintLabel = qt.QLabel("Role hints: (select volumes)")
        self.roleHintLabel.setWordWrap(True)
        volForm.addRow(self.roleHintLabel)

        self.confirmRolesCheck = qt.QCheckBox(
            "I confirm fat-only and water-only roles after visual preview"
        )
        volForm.addRow(self.confirmRolesCheck)

        self.validatePairButton = qt.QPushButton("Validate pair / geometry")
        volForm.addRow(self.validatePairButton)

        self.geometryReport = qt.QPlainTextEdit()
        self.geometryReport.setReadOnly(True)
        self.geometryReport.setMaximumHeight(140)
        volForm.addRow("Geometry report", self.geometryReport)

        # --- Segmentation ---
        segCollapsible = ctkCollapsibleButton("Segmentation")
        self.layout.addWidget(segCollapsible)
        segForm = qt.QFormLayout(segCollapsible)

        self.setupSegButton = qt.QPushButton("Create / reset VATQuant segments")
        segForm.addRow(self.setupSegButton)
        self.openEditorButton = qt.QPushButton("Open Segment Editor")
        segForm.addRow(self.openEditorButton)
        self.composeButton = qt.QPushButton("Compose VAT mask")
        segForm.addRow(self.composeButton)
        segHelp = qt.QLabel(
            "Edit Candidate, Compartment, Coverage, Exclusion in Segment Editor "
            "(paint / erase / threshold / Fill between slices), then Compose VAT."
        )
        segHelp.setWordWrap(True)
        segForm.addRow(segHelp)

        # --- Measure / QC / Export ---
        qcCollapsible = ctkCollapsibleButton("Measure, review, export")
        self.layout.addWidget(qcCollapsible)
        qcForm = qt.QFormLayout(qcCollapsible)

        self.measureButton = qt.QPushButton("Measure VAT volume (labelmap)")
        qcForm.addRow(self.measureButton)
        self.volumeLabel = qt.QLabel("Volume: —")
        qcForm.addRow(self.volumeLabel)
        self.stateLabel = qt.QLabel("State: IMPORTED")
        qcForm.addRow(self.stateLabel)
        self.markReviewedButton = qt.QPushButton("Mark reviewed")
        qcForm.addRow(self.markReviewedButton)
        self.exportButton = qt.QPushButton("Export JSON / CSV / NRRD…")
        qcForm.addRow(self.exportButton)

        self.layout.addStretch(1)

        # Connections
        self.fatDirButton.connect("clicked(bool)", self.onLoadFatDir)
        self.waterDirButton.connect("clicked(bool)", self.onLoadWaterDir)
        self.validatePairButton.connect("clicked(bool)", self.onValidatePair)
        self.confirmRolesCheck.connect("toggled(bool)", self.onConfirmRoles)
        self.setupSegButton.connect("clicked(bool)", self.onSetupSegments)
        self.openEditorButton.connect("clicked(bool)", self.onOpenSegmentEditor)
        self.composeButton.connect("clicked(bool)", self.onComposeVAT)
        self.measureButton.connect("clicked(bool)", self.onMeasure)
        self.markReviewedButton.connect("clicked(bool)", self.onMarkReviewed)
        self.exportButton.connect("clicked(bool)", self.onExport)
        self.fatSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onVolumeChanged)
        self.waterSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onVolumeChanged)

        self._refreshStateLabel()

    def cleanup(self):
        self.removeObservers()

    def _caseFields(self):
        return {
            "case_id": self.caseIdEdit.text.strip() or "case-unnamed",
            "protocol_id": self.protocolEdit.text.strip() or None,
            "roi": self.roiDefEdit.text.strip() or None,
            "retro": self.retroEdit.text.strip() or None,
            "reviewer": self.reviewerEdit.text.strip() or "operator",
        }

    def _refreshStateLabel(self):
        case = self.logic.case
        self.stateLabel.text = "State: {} | blockers: {}".format(
            case.state.value if case else "—",
            ", ".join(case.blockers) if case and case.blockers else "none",
        )

    def onVolumeChanged(self, _node=None):
        fat = self.fatSelector.currentNode()
        water = self.waterSelector.currentNode()
        hints = []
        if fat is not None:
            hints.append("Fat node: {}".format(fat.GetName()))
        if water is not None:
            hints.append("Water node: {}".format(water.GetName()))
        self.roleHintLabel.text = " | ".join(hints) if hints else "Role hints: (select volumes)"
        if self.logic.case and self.logic.case.roles_confirmed:
            self.logic.case.roles_confirmed = False
            self.confirmRolesCheck.setChecked(False)
            self.logic.case.mark_mask_edited()
            self._refreshStateLabel()

    def onLoadFatDir(self):
        path = qt.QFileDialog.getExistingDirectory(None, "Select fat-only DICOM folder")
        if not path:
            return
        try:
            node = self.logic.loadDicomFolderAsVolume(path, "VATQuant_Fat")
            self.fatSelector.setCurrentNode(node)
            slicer.util.infoDisplay("Loaded fat series from\n{}".format(path), windowTitle="VATQuant")
        except Exception as exc:
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")

    def onLoadWaterDir(self):
        path = qt.QFileDialog.getExistingDirectory(None, "Select water-only DICOM folder")
        if not path:
            return
        try:
            node = self.logic.loadDicomFolderAsVolume(path, "VATQuant_Water")
            self.waterSelector.setCurrentNode(node)
            slicer.util.infoDisplay("Loaded water series from\n{}".format(path), windowTitle="VATQuant")
        except Exception as exc:
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")

    def onValidatePair(self):
        fields = self._caseFields()
        try:
            report = self.logic.validateVolumes(
                self.fatSelector.currentNode(),
                self.waterSelector.currentNode(),
                case_id=fields["case_id"],
                protocol_id=fields["protocol_id"],
                roi=fields["roi"],
                retro=fields["retro"],
            )
            self.geometryReport.setPlainText(report)
            self.roleHintLabel.text = self.logic.last_role_hint_text
            self._refreshStateLabel()
        except Exception as exc:
            self.geometryReport.setPlainText(str(exc))
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")

    def onConfirmRoles(self, checked):
        if self.logic.case is None:
            if checked:
                self.confirmRolesCheck.setChecked(False)
                slicer.util.warningDisplay("Validate the fat/water pair first.", windowTitle="VATQuant")
            return
        self.logic.case.roles_confirmed = bool(checked)
        if checked:
            self.logic.case.state = AnalysisState.QC_PENDING
        self._refreshStateLabel()

    def onSetupSegments(self):
        fat = self.fatSelector.currentNode()
        if fat is None:
            slicer.util.warningDisplay("Select a fat-only volume first.", windowTitle="VATQuant")
            return
        try:
            segNode = self.logic.ensureSegmentation(fat)
            self.logic.showSegmentation(segNode, fat)
            slicer.util.infoDisplay(
                "Segments ready: {}".format(", ".join(SEGMENT_NAMES)),
                windowTitle="VATQuant",
            )
            self._refreshStateLabel()
        except Exception as exc:
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")

    def onOpenSegmentEditor(self):
        fat = self.fatSelector.currentNode()
        if fat is None or self.logic.segmentationNode is None:
            slicer.util.warningDisplay(
                "Create VATQuant segments first.", windowTitle="VATQuant"
            )
            return
        self.logic.showSegmentation(self.logic.segmentationNode, fat)
        slicer.util.selectModule("SegmentEditor")

    def onComposeVAT(self):
        try:
            n = self.logic.composeVAT(self.fatSelector.currentNode())
            slicer.util.infoDisplay(
                "Composed VAT segment ({} voxels). Review in Segment Editor, then Measure.".format(n),
                windowTitle="VATQuant",
            )
            self.volumeLabel.text = "Volume: (re-measure after compose)"
            self._refreshStateLabel()
        except Exception as exc:
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")

    def onMeasure(self):
        try:
            result = self.logic.measureVAT(self.fatSelector.currentNode())
            self.volumeLabel.text = "Volume: {:.3f} mL ({:.4f} L) | voxels={}".format(
                result.volume_mL, result.volume_L, result.voxel_count
            )
            self._refreshStateLabel()
        except Exception as exc:
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")

    def onMarkReviewed(self):
        fields = self._caseFields()
        try:
            self.logic.markReviewed(fields["reviewer"])
            self._refreshStateLabel()
            slicer.util.infoDisplay("Marked REVIEWED.", windowTitle="VATQuant")
        except Exception as exc:
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")

    def onExport(self):
        path = qt.QFileDialog.getExistingDirectory(None, "Select export folder")
        if not path:
            return
        try:
            paths = self.logic.exportBundle(self.fatSelector.currentNode(), path)
            slicer.util.infoDisplay(
                "Exported:\n{}".format("\n".join("{}: {}".format(k, v) for k, v in paths.items())),
                windowTitle="VATQuant",
            )
        except Exception as exc:
            slicer.util.errorDisplay(str(exc), windowTitle="VATQuant")


def ctkCollapsibleButton(title):
    """Create a collapsible group without requiring ctk Python bindings name quirks."""
    try:
        import ctk

        w = ctk.ctkCollapsibleButton()
        w.text = title
        w.collapsed = False
        return w
    except Exception:
        box = qt.QGroupBox(title)
        return box


class VATQuantLogic(ScriptedLoadableModuleLogic):
    def __init__(self):
        ScriptedLoadableModuleLogic.__init__(self)
        self.case = None  # type: CaseRecord | None
        self.segmentationNode = None
        self.last_role_hint_text = ""
        self._fat_loaded = None  # LoadedSeries if from DICOM folder
        self._water_loaded = None
        self._geometry = None  # ImageGeometry

    def loadDicomFolderAsVolume(self, folder, nodeName):
        from vatquant_core.dicom_series import load_series_from_directory

        loaded = load_series_from_directory(folder)
        node = self._pushArrayAsVolume(loaded.array, loaded.geometry, nodeName)
        role = suggest_role(loaded)
        node.SetAttribute("VATQuant.RoleHint", role.suggested_role or "")
        node.SetAttribute("VATQuant.SeriesUID", loaded.source_refs.series_uid or "")
        node.SetAttribute("VATQuant.StudyUID", loaded.source_refs.study_uid or "")
        if "fat" in nodeName.lower() or (role.suggested_role == "fat"):
            self._fat_loaded = loaded
        if "water" in nodeName.lower() or (role.suggested_role == "water"):
            self._water_loaded = loaded
        return node

    def _pushArrayAsVolume(self, array, geometry, nodeName):
        # array is (K,J,I); Slicer/vtk expects Fortran-order volume via updateVolumeFromArray
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", nodeName)
        # Build RAS geometry from LPS ImageGeometry
        affine_lps = geometry.affine_mm()
        lps_to_ras = np.diag([-1.0, -1.0, 1.0, 1.0])
        ijk_to_ras = lps_to_ras @ affine_lps
        slicer.util.updateVolumeFromArray(node, array.astype(np.float32, copy=False))
        rasToIjk = vtk.vtkMatrix4x4()
        ijkToRas = vtk.vtkMatrix4x4()
        for r in range(4):
            for c in range(4):
                ijkToRas.SetElement(r, c, float(ijk_to_ras[r, c]))
        vtk.vtkMatrix4x4.Invert(ijkToRas, rasToIjk)
        node.SetIJKToRASMatrix(ijkToRas)
        node.CreateDefaultDisplayNodes()
        return node

    def geometryFromVolumeNode(self, volumeNode):
        """Derive ImageGeometry (LPS) from a Slicer volume node."""
        if volumeNode is None:
            raise VATQuantError("volume node is required")
        ijkToRas = vtk.vtkMatrix4x4()
        volumeNode.GetIJKToRASMatrix(ijkToRas)
        m = np.eye(4)
        for r in range(4):
            for c in range(4):
                m[r, c] = ijkToRas.GetElement(r, c)
        ras_to_lps = np.diag([-1.0, -1.0, 1.0, 1.0])
        affine_lps = ras_to_lps @ m
        linear = affine_lps[:3, :3]
        spacing = tuple(float(np.linalg.norm(linear[:, ax])) for ax in range(3))
        if min(spacing) <= 0:
            raise VATQuantError("invalid spacing derived from volume node")
        direction = np.zeros((3, 3), dtype=np.float64)
        for ax in range(3):
            direction[:, ax] = linear[:, ax] / spacing[ax]
        origin = tuple(float(x) for x in affine_lps[:3, 3])
        arr = slicer.util.arrayFromVolume(volumeNode)
        shape = tuple(int(x) for x in arr.shape)
        direction_t = tuple(tuple(float(direction[r, c]) for c in range(3)) for r in range(3))
        return ImageGeometry(
            shape=shape,
            spacing=spacing,
            origin_lps=origin,
            direction=direction_t,
        )

    def validateVolumes(self, fatNode, waterNode, case_id, protocol_id, roi, retro):
        if fatNode is None or waterNode is None:
            raise VATQuantError("select both fat and water volume nodes")
        if fatNode == waterNode:
            raise VATQuantError("fat and water must be different volume nodes")

        fat_geom = self.geometryFromVolumeNode(fatNode)
        water_geom = self.geometryFromVolumeNode(waterNode)
        if not fat_geom.approx_equal(water_geom, tol=1e-2):
            raise PairingError(
                "fat/water geometries are not approximately equal "
                "(spacing/origin/direction/shape mismatch)"
            )

        # If both were loaded via core DICOM adapter, run full validate_pair
        lines = []
        if self._fat_loaded is not None and self._water_loaded is not None:
            validate_pair(self._fat_loaded, self._water_loaded, geometry_tol=1e-2)
            rf = suggest_role(self._fat_loaded)
            rw = suggest_role(self._water_loaded)
            self.last_role_hint_text = "Fat hint: {} ({}) | Water hint: {} ({})".format(
                rf.suggested_role, rf.confidence, rw.suggested_role, rw.confidence
            )
            lines.append("DICOM pairing: OK")
            lines.append(
                "Fat series: {}".format(self._fat_loaded.source_refs.series_description)
            )
            lines.append(
                "Water series: {}".format(self._water_loaded.source_refs.series_description)
            )
            c2c = self._fat_loaded.source_refs.centre_to_centre_spacing_mm
            thick = self._fat_loaded.source_refs.slice_thickness_mm
            lines.append("Centre-to-centre spacing: {} mm".format(c2c))
            lines.append("SliceThickness tag: {} mm".format(thick))
            scanner = {
                "manufacturer": self._fat_loaded.source_refs.manufacturer,
                "model": self._fat_loaded.source_refs.model,
                "field_strength_T": self._fat_loaded.source_refs.field_strength_T,
            }
            source_series = [
                {
                    "role": "fat",
                    "series_uid": self._fat_loaded.source_refs.series_uid,
                    "sop_uids": self._fat_loaded.source_refs.sop_uids,
                },
                {
                    "role": "water",
                    "series_uid": self._water_loaded.source_refs.series_uid,
                    "sop_uids": self._water_loaded.source_refs.sop_uids,
                },
            ]
        else:
            self.last_role_hint_text = (
                "Volumes from scene (not core DICOM folders). "
                "Confirm roles visually; geometry compared via IJKToRAS."
            )
            scanner = {"manufacturer": None, "model": None, "field_strength_T": None}
            source_series = [
                {"role": "fat", "node": fatNode.GetName()},
                {"role": "water", "node": waterNode.GetName()},
            ]
            lines.append("Scene volume pairing: geometry approx_equal OK")

        lines.append("Shape (K,J,I): {}".format(fat_geom.shape))
        lines.append("Spacing (dx,dy,dz) mm: {}".format(fat_geom.spacing))
        lines.append("Voxel volume mm³: {:.6f}".format(fat_geom.voxel_volume_mm3()))
        lines.append("Geometry hash: {}".format(fat_geom.geometry_hash()))
        lines.append("vatquant_core {} / algo {}".format(__version__, ALGORITHM_VERSION))

        self._geometry = fat_geom
        self.case = CaseRecord(case_id=case_id)
        self.case.protocol_id = protocol_id
        self.case.analysis_roi_definition = roi
        self.case.retroperitoneal_fat_rule = retro
        self.case.scanner = scanner
        self.case.source_series = source_series
        self.case.state = AnalysisState.QC_PENDING
        self.case.roles_confirmed = False
        return "\n".join(lines)

    def ensureSegmentation(self, referenceVolumeNode):
        if referenceVolumeNode is None:
            raise VATQuantError("reference volume required")
        if self.segmentationNode is None or not slicer.mrmlScene.IsNodePresent(
            self.segmentationNode
        ):
            self.segmentationNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLSegmentationNode", "VATQuant_Segmentation"
            )
            self.segmentationNode.CreateDefaultDisplayNodes()
        self.segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(
            referenceVolumeNode
        )
        seg = self.segmentationNode.GetSegmentation()
        for name in SEGMENT_NAMES:
            existing = seg.GetSegmentIdBySegmentName(name)
            if not existing:
                seg.AddEmptySegment(name, name)
        # Default Coverage to full FOV if empty
        cov_id = seg.GetSegmentIdBySegmentName("Coverage")
        cov = slicer.util.arrayFromSegmentBinaryLabelmap(
            self.segmentationNode, cov_id, referenceVolumeNode
        )
        if int(np.count_nonzero(cov)) == 0:
            full = np.ones(cov.shape, dtype=np.uint8)
            self._updateSegmentFromArray(cov_id, referenceVolumeNode, full)
        if self.case is not None:
            self.case.state = AnalysisState.SEGMENTATION_DRAFT
            self.case.mark_mask_edited()
        return self.segmentationNode

    def showSegmentation(self, segmentationNode, volumeNode):
        segmentationNode.CreateDefaultDisplayNodes()
        displayNode = segmentationNode.GetDisplayNode()
        if displayNode:
            displayNode.SetVisibility(True)
        # Set fat as background
        slicer.util.setSliceViewerLayers(background=volumeNode, fit=True)

    def _segmentArray(self, name, referenceVolumeNode):
        seg = self.segmentationNode.GetSegmentation()
        sid = seg.GetSegmentIdBySegmentName(name)
        if not sid:
            raise VATQuantError("missing segment: {}".format(name))
        return slicer.util.arrayFromSegmentBinaryLabelmap(
            self.segmentationNode, sid, referenceVolumeNode
        ).astype(bool)

    def _updateSegmentFromArray(self, segmentId, referenceVolumeNode, array_uint8):
        slicer.util.updateSegmentBinaryLabelmapFromArray(
            np.asarray(array_uint8, dtype=np.uint8),
            self.segmentationNode,
            segmentId,
            referenceVolumeNode,
        )

    def composeVAT(self, referenceVolumeNode):
        if self.segmentationNode is None:
            raise VATQuantError("create segments first")
        if referenceVolumeNode is None:
            raise VATQuantError("fat volume required as reference")
        candidate = self._segmentArray("Candidate", referenceVolumeNode)
        compartment = self._segmentArray("Compartment", referenceVolumeNode)
        coverage = self._segmentArray("Coverage", referenceVolumeNode)
        exclusion = self._segmentArray("Exclusion", referenceVolumeNode)
        vat = combine_vat_mask(candidate, compartment, coverage, exclusion)
        vat_id = self.segmentationNode.GetSegmentation().GetSegmentIdBySegmentName("VAT")
        self._updateSegmentFromArray(vat_id, referenceVolumeNode, vat.astype(np.uint8))
        if self.case is not None:
            self.case.state = AnalysisState.REVIEW_REQUIRED
            self.case.mark_mask_edited()
            # mark_mask_edited clears metrics and may set SEGMENTATION_DRAFT; force review required
            self.case.state = AnalysisState.REVIEW_REQUIRED
        return int(np.count_nonzero(vat))

    def measureVAT(self, referenceVolumeNode):
        if self.case is None:
            raise VATQuantError("validate pair before measuring")
        if not self.case.roles_confirmed:
            raise QCBlockedError("confirm fat/water roles before measuring")
        if referenceVolumeNode is None or self.segmentationNode is None:
            raise VATQuantError("volume and segmentation required")
        geom = self._geometry or self.geometryFromVolumeNode(referenceVolumeNode)
        vat = self._segmentArray("VAT", referenceVolumeNode)
        if vat.shape != geom.shape:
            # Prefer geometry matching the labelmap array
            geom = self.geometryFromVolumeNode(referenceVolumeNode)
        result = measure_volume(vat, geom)
        self.case.volume_result = result
        self.case.state = AnalysisState.REVIEW_REQUIRED
        self._geometry = geom
        return result

    def markReviewed(self, reviewer_id):
        if self.case is None:
            raise VATQuantError("no active case")
        self.case.mark_reviewed(reviewer_id)
        return self.case

    def exportBundle(self, referenceVolumeNode, out_dir):
        if self.case is None:
            raise VATQuantError("no active case")
        self.case.require_export_final()
        geom = self._geometry or self.geometryFromVolumeNode(referenceVolumeNode)
        vat = self._segmentArray("VAT", referenceVolumeNode)
        return export_case_bundle(self.case, geom, vat, out_dir, require_final=True)


class VATQuantTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        self.setUp()
        self.test_module_loads()

    def test_module_loads(self):
        self.delayDisplay("VATQuant module import / logic smoke")
        logic = VATQuantLogic()
        self.assertIsNotNone(logic)
        from vatquant_core.synthetic import make_phantom
        from vatquant_core.masks import combine_vat_mask
        from vatquant_core.measurement import measure_volume

        p = make_phantom(shape=(8, 24, 24), spacing=(2.0, 2.0, 5.0), seed=99)
        vat = combine_vat_mask(
            p.candidate_mask, p.compartment_mask, p.coverage_mask, p.exclusion_mask
        )
        result = measure_volume(vat, p.geometry)
        self.assertEqual(result.voxel_count, p.expected_vat_voxels)
        self.delayDisplay("VATQuant core measure OK: {:.3f} mL".format(result.volume_mL))
