"""Deterministic explanation provider — no network dependency.

Builds a ``CandidateExplanation`` directly from the structured evidence using
the shared description builders in ``descriptions.py``. This is the required
fallback so the pipeline never depends on the LLM being available: missing
API key, network failure, timeout, malformed response, or a response that
fails grounding validation all land here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import DISCLAIMER
from app.models.explanation import CandidateExplanation, ExplanationContext, ExplanationProvenance
from app.models.ranking import RankedCandidate
from app.services.explanation import descriptions as _d


class DeterministicExplanationProvider:
    """``ExplanationProvider`` that never calls a network service."""

    name = "deterministic_fallback"

    def explain(
        self,
        candidate: RankedCandidate,
        context: ExplanationContext,
        *,
        fallback_reason: str | None = None,
    ) -> CandidateExplanation:
        return CandidateExplanation(
            disease_id=candidate.disease_id,
            drug_id=candidate.drug_id,
            disease_name=candidate.disease_name,
            drug_name=candidate.drug_name,
            rank=candidate.rank,
            repurposing_score=candidate.repurposing_score,
            summary=_d.deterministic_summary(candidate),
            biological_evidence=_d.biological_evidence_items(candidate),
            model_evidence=_d.model_evidence_item(candidate),
            limitations=_d.deterministic_limitations(candidate),
            provenance=ExplanationProvenance(
                provider=self.name,
                model_name=None,
                generated_at=datetime.now(UTC).isoformat(),
                scoring_version=context.scoring_version,
                ranking_version=context.ranking_version,
                fallback_reason=fallback_reason,
                validation_notes=["deterministic provider — no external validation needed"],
                disclaimer=DISCLAIMER,
            ),
        )
