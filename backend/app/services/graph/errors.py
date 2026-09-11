"""Typed errors for Phase 10 evidence-graph construction."""

from __future__ import annotations


class EvidenceGraphError(Exception):
    """Base class for all evidence-graph failures."""


class InconsistentGraphInputError(EvidenceGraphError):
    """The ranked candidates / generation candidates / explanations do not
    refer to the same disease, or a ranked candidate's ``CandidateDrug`` is
    missing, or a supplied pair does not refer to the same (disease, drug)."""
