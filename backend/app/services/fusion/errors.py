"""Typed errors for Phase 7 evidence fusion."""

from __future__ import annotations


class EvidenceFusionError(Exception):
    """Base class for evidence-fusion failures."""


class InconsistentFusionInputError(EvidenceFusionError):
    """The candidate / feature vector / prediction do not refer to the same
    (disease, drug) pair."""
