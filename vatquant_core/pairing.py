"""Fat/water series role hints and pair validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from vatquant_core.dicom_series import LoadedSeries
from vatquant_core.errors import PairingError


@dataclass
class RoleSuggestion:
    series_uid: str
    suggested_role: Optional[str]  # "fat", "water", or None
    confidence: str  # "high", "low", "none"
    rationale: str


def _text_blob(series: LoadedSeries) -> str:
    parts = []
    if series.source_refs.series_description:
        parts.append(series.source_refs.series_description)
    parts.extend(series.source_refs.image_type)
    return " ".join(parts).upper()


def suggest_role(series: LoadedSeries) -> RoleSuggestion:
    """Suggest fat/water role from ImageType / SeriesDescription hints only."""
    blob = _text_blob(series)
    image_type = [t.upper() for t in series.source_refs.image_type]

    if "FAT" in image_type or "FAT" in blob.split():
        # Prefer ImageType token
        if "FAT" in image_type and "WATER" not in image_type:
            return RoleSuggestion(
                series_uid=series.source_refs.series_uid,
                suggested_role="fat",
                confidence="high",
                rationale="ImageType contains FAT",
            )
        if "FAT" in blob and "WATER" not in blob:
            return RoleSuggestion(
                series_uid=series.source_refs.series_uid,
                suggested_role="fat",
                confidence="low",
                rationale="SeriesDescription/ImageType text suggests FAT",
            )

    if "WATER" in image_type or "WATER" in blob.split():
        if "WATER" in image_type and "FAT" not in image_type:
            return RoleSuggestion(
                series_uid=series.source_refs.series_uid,
                suggested_role="water",
                confidence="high",
                rationale="ImageType contains WATER",
            )
        if "WATER" in blob and "FAT" not in blob:
            return RoleSuggestion(
                series_uid=series.source_refs.series_uid,
                suggested_role="water",
                confidence="low",
                rationale="SeriesDescription/ImageType text suggests WATER",
            )

    # GE / Siemens description heuristics
    if "FAT" in blob and "WATER" not in blob:
        return RoleSuggestion(
            series_uid=series.source_refs.series_uid,
            suggested_role="fat",
            confidence="low",
            rationale="description contains FAT",
        )
    if "WATER" in blob and "FAT" not in blob:
        return RoleSuggestion(
            series_uid=series.source_refs.series_uid,
            suggested_role="water",
            confidence="low",
            rationale="description contains WATER",
        )

    return RoleSuggestion(
        series_uid=series.source_refs.series_uid,
        suggested_role=None,
        confidence="none",
        rationale="no reliable fat/water hint; operator must confirm",
    )


def suggest_roles(series_list: Sequence[LoadedSeries]) -> List[RoleSuggestion]:
    return [suggest_role(s) for s in series_list]


def validate_pair(
    fat: LoadedSeries,
    water: LoadedSeries,
    require_same_frame_of_reference: bool = True,
    geometry_tol: float = 1e-3,
) -> None:
    """Validate that fat and water form a usable paired Dixon pair.

    Raises PairingError on mismatch. Does not imply operator confirmation.
    """
    if fat.source_refs.study_uid != water.source_refs.study_uid:
        raise PairingError("fat and water series must share StudyInstanceUID")
    if fat.source_refs.series_uid == water.source_refs.series_uid:
        raise PairingError("fat and water must be different SeriesInstanceUID values")
    if require_same_frame_of_reference:
        if not fat.source_refs.frame_of_reference_uid or not water.source_refs.frame_of_reference_uid:
            raise PairingError("FrameOfReferenceUID required on both series for pairing")
        if fat.source_refs.frame_of_reference_uid != water.source_refs.frame_of_reference_uid:
            raise PairingError("fat and water FrameOfReferenceUID differ")
    if fat.array.shape != water.array.shape:
        raise PairingError(
            "fat/water array shapes differ: {} vs {}".format(fat.array.shape, water.array.shape)
        )
    if not fat.geometry.approx_equal(water.geometry, tol=geometry_tol):
        raise PairingError("fat/water geometries are not approximately equal")
