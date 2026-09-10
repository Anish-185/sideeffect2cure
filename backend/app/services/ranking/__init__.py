"""Candidate Ranking (Phase 8).

    EvidenceFusionResult[]  ->  rank_candidates(...)  ->  RankedCandidateResult

Deterministically orders the Phase 7 results by ``repurposing_score`` (higher
first; ties by ``drug_id``), assigns ``rank``, and supports an optional
``top_n`` presentation slice. It embeds the full ``EvidenceFusionResult`` in
every ranked candidate so no evidence is lost.

No score is recalculated, no biology is touched, no AI/LLM, no new dependency.
Ranking is based on the computational ``repurposing_score`` — it does NOT
establish clinical efficacy, treatment suitability, or safety.
"""

from app.models.ranking import (
    RANKING_VERSION,
    RankedCandidate,
    RankedCandidateResult,
    RankingProvenance,
)
from app.services.ranking.errors import (
    DuplicateCandidateError,
    InvalidTopNError,
    RankingError,
)
from app.services.ranking.rank import rank_candidates, rank_for_disease

__all__ = [
    "RANKING_VERSION",
    "DuplicateCandidateError",
    "InvalidTopNError",
    "RankedCandidate",
    "RankedCandidateResult",
    "RankingError",
    "RankingProvenance",
    "rank_candidates",
    "rank_for_disease",
]
