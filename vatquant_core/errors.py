"""Typed errors for VATQuant. Fail closed — never silent defaults."""

from __future__ import annotations


class VATQuantError(Exception):
    """Base error for all VATQuant failures."""


class GeometryError(VATQuantError):
    """Missing, invalid, or inconsistent image geometry."""


class SeriesIntegrityError(VATQuantError):
    """DICOM series fails ordering, spacing, duplicate, or integrity checks."""


class PairingError(VATQuantError):
    """Fat/water series pair is ambiguous or mismatched."""


class UnsupportedInputError(VATQuantError):
    """Input format or configuration is not supported in this version."""


class QCBlockedError(VATQuantError):
    """Operation blocked by quality-control state or unresolved blockers."""
