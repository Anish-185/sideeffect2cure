"""Typed errors for Phase 8 candidate ranking."""

from __future__ import annotations


class RankingError(Exception):
    """Base class for ranking failures."""


class InvalidTopNError(RankingError, ValueError):
    """top_n was not a positive integer."""


class DuplicateCandidateError(RankingError):
    """The same drug appears more than once for the same disease.

    Candidates are unique per (disease_id, drug_id) in Levels 4-7, so a duplicate
    signals a bug upstream. Ranking refuses rather than assign two ranks to one
    drug.
    """

    def __init__(self, duplicates: list[str]) -> None:
        super().__init__(f"duplicate candidate drug_id(s): {sorted(set(duplicates))}")
        self.duplicates = sorted(set(duplicates))
