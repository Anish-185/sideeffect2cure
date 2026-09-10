"""Typed errors for the disease-intelligence service.

Every failure mode is explicit and deterministic. The service never falls back
to an unrelated disease.
"""

from __future__ import annotations

from app.models.disease import ResolutionResult


class DiseaseIntelligenceError(Exception):
    """Base class for all disease-intelligence failures."""


class UnknownDiseaseError(DiseaseIntelligenceError):
    """A disease id was requested that is not present in the processed data."""

    def __init__(self, disease_id: str) -> None:
        super().__init__(f"unknown disease id: {disease_id!r}")
        self.disease_id = disease_id


class DiseaseResolutionError(DiseaseIntelligenceError):
    """A query could not be resolved to exactly one supported disease.

    Carries the full :class:`ResolutionResult` so callers can inspect the
    status (empty / not supported / ambiguous), candidates and suggestions.
    """

    def __init__(self, result: ResolutionResult) -> None:
        super().__init__(f"could not resolve disease query {result.query!r}: {result.status.value}")
        self.result = result
