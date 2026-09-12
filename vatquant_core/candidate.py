"""Candidate adipose-tissue proposal (threshold / optional fat-fraction feature).

This is a segmentation *proposal*, not PDFF and not a final VAT measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from vatquant_core.errors import GeometryError


@dataclass
class CandidateResult:
    mask: np.ndarray
    parameters: Dict[str, Any]


def fat_signal_ratio(
    fat: np.ndarray,
    water: np.ndarray,
    eps: float = 1e-6,
    signal_floor: float = 10.0,
) -> np.ndarray:
    """Compute F/(F+W+eps) on signal-bearing voxels; others set to 0.

    Not PDFF. Do not sum this ratio and call it VAT volume.
    """
    f = np.asarray(fat, dtype=np.float64)
    w = np.asarray(water, dtype=np.float64)
    if f.shape != w.shape:
        raise GeometryError("fat and water shapes must match for signal ratio")
    total = f + w
    ratio = f / (total + eps)
    ratio[total < signal_floor] = 0.0
    return ratio


def propose_candidate_threshold(
    fat: np.ndarray,
    threshold: float,
    use_ratio: bool = False,
    water: Optional[np.ndarray] = None,
    ratio_threshold: float = 0.5,
    signal_floor: float = 10.0,
) -> CandidateResult:
    """Propose candidate adipose mask from fat-only threshold and optional ratio."""
    f = np.asarray(fat, dtype=np.float64)
    mask = f >= float(threshold)
    params: Dict[str, Any] = {
        "method": "fat_threshold",
        "threshold": float(threshold),
        "use_ratio": bool(use_ratio),
        "note": "proposal_only_not_PDFF",
    }
    if use_ratio:
        if water is None:
            raise GeometryError("water image required when use_ratio=True")
        ratio = fat_signal_ratio(f, water, signal_floor=signal_floor)
        mask = mask & (ratio >= float(ratio_threshold))
        params["ratio_threshold"] = float(ratio_threshold)
        params["signal_floor"] = float(signal_floor)
        params["method"] = "fat_threshold_and_signal_ratio"
    return CandidateResult(mask=mask.astype(bool), parameters=params)
