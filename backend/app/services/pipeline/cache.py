"""Lightweight process-local cache of a pipeline run, keyed by disease_id.

The dashboard's flow is: run the pipeline once for a disease (candidate
generation through ranking — the expensive, multi-stage part), then let the
user open several candidates' explanations/graphs without re-running Levels
2-8 for each click. No database — a plain dict, same pattern as
``app.services.explanation.cache``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.candidate import CandidateDrug
from app.models.disease import DiseaseProfile
from app.models.ranking import RankedCandidateResult


@dataclass(frozen=True)
class CachedRun:
    disease_profile: DiseaseProfile
    candidate_count: int
    counts_by_method: dict[str, int]
    ranked: RankedCandidateResult
    generation_by_drug: dict[str, CandidateDrug]


_cache: dict[str, CachedRun] = {}


def put(run: CachedRun) -> None:
    _cache[run.disease_profile.disease_id] = run


def get(disease_id: str) -> CachedRun | None:
    return _cache.get(disease_id)


def clear() -> None:
    _cache.clear()
