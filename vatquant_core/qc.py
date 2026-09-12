"""Analysis QC states and case records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from vatquant_core.errors import QCBlockedError
from vatquant_core.measurement import AreaResult, VolumeResult


class AnalysisState(str, Enum):
    IMPORTED = "IMPORTED"
    QC_PENDING = "QC_PENDING"
    SEGMENTATION_DRAFT = "SEGMENTATION_DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWED = "REVIEWED"
    REJECTED = "REJECTED"


@dataclass
class CaseRecord:
    case_id: str
    protocol_id: Optional[str] = None
    state: AnalysisState = AnalysisState.IMPORTED
    qc_flags: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    reviewer_id: Optional[str] = None
    review_timestamp: Optional[str] = None
    roles_confirmed: bool = False
    analysis_roi_definition: Optional[str] = None
    retroperitoneal_fat_rule: Optional[str] = None
    volume_result: Optional[VolumeResult] = None
    area_result: Optional[AreaResult] = None
    analysis_parameters: Dict[str, Any] = field(default_factory=dict)
    source_series: List[Dict[str, Any]] = field(default_factory=list)
    scanner: Dict[str, Any] = field(default_factory=dict)

    def add_blocker(self, message: str) -> None:
        if message not in self.blockers:
            self.blockers.append(message)

    def clear_blocker(self, message: str) -> None:
        self.blockers = [b for b in self.blockers if b != message]

    def mark_mask_edited(self) -> None:
        """Any segmentation edit invalidates prior review and metrics."""
        self.volume_result = None
        self.area_result = None
        self.reviewer_id = None
        self.review_timestamp = None
        if self.state == AnalysisState.REVIEWED:
            self.state = AnalysisState.REVIEW_REQUIRED
        elif self.state not in (AnalysisState.REJECTED, AnalysisState.IMPORTED):
            self.state = AnalysisState.SEGMENTATION_DRAFT

    def mark_reviewed(self, reviewer_id: str) -> None:
        if self.blockers:
            raise QCBlockedError("cannot mark reviewed while blockers remain: {}".format(self.blockers))
        if not self.roles_confirmed:
            raise QCBlockedError("operator must confirm fat/water roles before review")
        if self.volume_result is None:
            raise QCBlockedError("volume measurement required before review approval")
        self.reviewer_id = reviewer_id
        self.review_timestamp = datetime.now(timezone.utc).isoformat()
        self.state = AnalysisState.REVIEWED

    def can_export_final(self) -> bool:
        return (
            self.state == AnalysisState.REVIEWED
            and not self.blockers
            and self.roles_confirmed
            and self.volume_result is not None
        )

    def require_export_final(self) -> None:
        if not self.can_export_final():
            raise QCBlockedError(
                "final export blocked: state={}, blockers={}, roles_confirmed={}, has_volume={}".format(
                    self.state.value,
                    self.blockers,
                    self.roles_confirmed,
                    self.volume_result is not None,
                )
            )
