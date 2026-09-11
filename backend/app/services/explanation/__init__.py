"""Grounded AI-Powered Candidate Explanation (Phase 9).

    RankedCandidate -> ExplanationContext -> DeepSeek V4 Flash (Featherless)
        -> validated CandidateExplanation

The LLM is an EXPLANATION layer only: it narrates the evidence Phases 4-8
already computed. It never recalculates the ``repurposing_score``, never
reranks, never generates new features, and never introduces a gene / target /
pathway / mechanism / study that was not in the supplied evidence.

If ``FEATHERLESS_API_KEY`` is missing, the request fails, times out, or the
response fails grounding validation, the pipeline falls back to a
deterministic, template-based explanation built from the same structured
evidence (``DeterministicExplanationProvider``) — the pipeline never depends
on the LLM being reachable. See ``docs/ai-explanation.md``.
"""

from app.models.explanation import (
    EXPLANATION_SCHEMA_VERSION,
    GROUNDING_NOTE,
    BiologicalEvidenceItem,
    CandidateExplanation,
    ExplanationContext,
    ExplanationProvenance,
    ModelEvidence,
)
from app.services.explanation.context import build_explanation_context
from app.services.explanation.deepseek_provider import DeepSeekFeatherlessProvider
from app.services.explanation.deterministic import DeterministicExplanationProvider
from app.services.explanation.errors import (
    ExplanationError,
    ExplanationHTTPError,
    ExplanationNetworkError,
    ExplanationProviderError,
    ExplanationTimeoutError,
    ExplanationValidationError,
    MalformedResponseError,
    MissingAPIKeyError,
)
from app.services.explanation.provider import ExplanationProvider
from app.services.explanation.service import (
    default_provider,
    explain_candidate,
    explain_for_disease,
    explain_top_n,
    reset_default_provider,
)

__all__ = [
    "EXPLANATION_SCHEMA_VERSION",
    "GROUNDING_NOTE",
    "BiologicalEvidenceItem",
    "CandidateExplanation",
    "DeepSeekFeatherlessProvider",
    "DeterministicExplanationProvider",
    "ExplanationContext",
    "ExplanationError",
    "ExplanationHTTPError",
    "ExplanationNetworkError",
    "ExplanationProvenance",
    "ExplanationProvider",
    "ExplanationProviderError",
    "ExplanationTimeoutError",
    "ExplanationValidationError",
    "MalformedResponseError",
    "MissingAPIKeyError",
    "ModelEvidence",
    "build_explanation_context",
    "default_provider",
    "explain_candidate",
    "explain_for_disease",
    "explain_top_n",
    "reset_default_provider",
]
