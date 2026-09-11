"""Phase 9 orchestration: ``RankedCandidate`` -> ``CandidateExplanation``.

    RankedCandidate -> build_explanation_context(...) -> provider.explain(...)
        -> CandidateExplanation

Tries the configured provider (DeepSeek via Featherless, if an API key is
configured) first; on ANY provider or validation failure it falls back to the
deterministic provider, so the pipeline never depends on the explanation
layer being reachable. The LLM is only ever called for explicitly requested
candidates (one, or an explicit top-N) — never automatically for a whole
ranked list.
"""

from __future__ import annotations

import functools
import logging

from app.core.config import get_settings
from app.models.explanation import CandidateExplanation
from app.models.ranking import RankedCandidate, RankedCandidateResult
from app.services.explanation import cache as _cache
from app.services.explanation.context import build_explanation_context
from app.services.explanation.deepseek_provider import DeepSeekFeatherlessProvider
from app.services.explanation.deterministic import DeterministicExplanationProvider
from app.services.explanation.errors import ExplanationProviderError, ExplanationValidationError
from app.services.explanation.provider import ExplanationProvider

logger = logging.getLogger(__name__)

_deterministic_provider = DeterministicExplanationProvider()


@functools.cache
def _default_llm_provider() -> DeepSeekFeatherlessProvider:
    return DeepSeekFeatherlessProvider()


def reset_default_provider() -> None:
    """Test/CLI hook: forget the cached LLM provider (e.g. after changing env)."""
    _default_llm_provider.cache_clear()


def default_provider() -> ExplanationProvider:
    """The configured LLM provider if ``FEATHERLESS_API_KEY`` is set, else the
    deterministic provider directly (skips a guaranteed-to-fail network call)."""
    if get_settings().featherless_api_key:
        return _default_llm_provider()
    return _deterministic_provider


def explain_candidate(
    candidate: RankedCandidate,
    *,
    provider: ExplanationProvider | None = None,
    use_cache: bool = True,
) -> CandidateExplanation:
    """Explain one ranked candidate.

    Never raises for a provider/validation failure — falls back to the
    deterministic explanation instead, with ``provenance.fallback_reason`` set.
    """
    context = build_explanation_context(candidate)
    prov = provider or default_provider()

    if use_cache:
        cached = _cache.get(context, prov.name)
        if cached is not None:
            return cached

    if prov is _deterministic_provider:
        explanation = _deterministic_provider.explain(candidate, context)
    else:
        try:
            explanation = prov.explain(candidate, context)
        except (ExplanationProviderError, ExplanationValidationError) as exc:
            logger.warning(
                "explanation provider %r failed (%s); falling back to deterministic provider",
                prov.name,
                type(exc).__name__,
            )
            explanation = _deterministic_provider.explain(
                candidate, context, fallback_reason=f"{type(exc).__name__}: {exc}"
            )

    if use_cache:
        _cache.put(context, prov.name, explanation)
    return explanation


def explain_top_n(
    ranked: RankedCandidateResult,
    n: int = 3,
    *,
    provider: ExplanationProvider | None = None,
    use_cache: bool = True,
) -> list[CandidateExplanation]:
    """Explain the top ``n`` ranked candidates only — never the whole list
    automatically. Order matches ``ranked.top(n)``; ranks are untouched."""
    return [
        explain_candidate(c, provider=provider, use_cache=use_cache) for c in ranked.top(n)
    ]


def explain_for_disease(
    disease_query: str,
    *,
    top_n: int = 3,
    provider: ExplanationProvider | None = None,
    use_ml: bool = True,
) -> tuple[RankedCandidateResult, list[CandidateExplanation]]:
    """Convenience: run the full pipeline for one disease and explain its
    top-N ranked candidates."""
    from app.services.ranking import rank_for_disease

    ranked = rank_for_disease(disease_query, top_n=top_n, use_ml=use_ml)
    explanations = explain_top_n(ranked, top_n, provider=provider)
    return ranked, explanations
