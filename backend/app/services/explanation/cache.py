"""Lightweight process-local cache for ``CandidateExplanation``.

Deterministic key: disease + drug + repurposing_score + scoring_version +
ranking_version + provider. No database, no disk persistence — just enough
that repeated dashboard/demo requests for the same candidate don't re-call the
LLM within one process lifetime. Cleared on process restart, which is fine:
nothing here is a source of truth (the deterministic pipeline output is).
"""

from __future__ import annotations

from app.models.explanation import CandidateExplanation, ExplanationContext

CacheKey = tuple[str, str, float, str, str, str]

_cache: dict[CacheKey, CandidateExplanation] = {}


def cache_key(context: ExplanationContext, provider_name: str) -> CacheKey:
    return (
        context.disease_id,
        context.drug_id,
        round(context.repurposing_score, 4),
        context.scoring_version,
        context.ranking_version,
        provider_name,
    )


def get(context: ExplanationContext, provider_name: str) -> CandidateExplanation | None:
    return _cache.get(cache_key(context, provider_name))


def put(context: ExplanationContext, provider_name: str, explanation: CandidateExplanation) -> None:
    _cache[cache_key(context, provider_name)] = explanation


def clear() -> None:
    _cache.clear()


def size() -> int:
    return len(_cache)
