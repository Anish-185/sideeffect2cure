"""Typed errors for the drug-intelligence service.

Every failure mode is explicit and deterministic. The service never falls back
to an unrelated drug.
"""

from __future__ import annotations

from app.models.drug import DrugResolutionResult


class DrugIntelligenceError(Exception):
    """Base class for all drug-intelligence failures."""


class UnknownDrugError(DrugIntelligenceError):
    """A drug id was requested that is not present in the processed data."""

    def __init__(self, drug_id: str) -> None:
        super().__init__(f"unknown drug id: {drug_id!r}")
        self.drug_id = drug_id


class DrugResolutionError(DrugIntelligenceError):
    """A query could not be resolved to exactly one supported drug.

    Carries the full :class:`DrugResolutionResult` (status / candidates /
    suggestions) so the caller can decide what to do.
    """

    def __init__(self, result: DrugResolutionResult) -> None:
        super().__init__(f"could not resolve drug query {result.query!r}: {result.status.value}")
        self.result = result
