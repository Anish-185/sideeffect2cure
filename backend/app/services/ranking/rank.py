"""Phase 8 candidate ranking.

    EvidenceFusionResult[]  ->  rank_candidates(...)  ->  RankedCandidateResult

Pure ordering. No score is recalculated, no biology is touched, no dependency is
added. Deterministic: identical input list -> identical ranked output.

Rule:
  1. sort by ``repurposing_score`` descending
  2. ties broken by ``drug_id`` ascending (lexicographic) — stable & deterministic
  3. assign ``rank`` = 1..N by sorted position (ranks are always unique)

``top_n`` is an optional presentation slice applied AFTER ranking; it never
changes any score or the rank a candidate would have in the full list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import DISCLAIMER
from app.models.fusion import EvidenceFusionResult

if TYPE_CHECKING:
    from app.services.fusion.config import FusionConfig
from app.models.ranking import (
    RANKING_VERSION,
    RankedCandidate,
    RankedCandidateResult,
    RankingProvenance,
)
from app.services.ranking.errors import DuplicateCandidateError, InvalidTopNError


def _validate_top_n(top_n: int | None, n: int) -> int | None:
    if top_n is None:
        return None
    if isinstance(top_n, bool) or not isinstance(top_n, int):
        raise InvalidTopNError(f"top_n must be a positive int or None, got {top_n!r}")
    if top_n < 1:
        raise InvalidTopNError(f"top_n must be >= 1, got {top_n}")
    return min(top_n, n)


def _check_unique(results: list[EvidenceFusionResult]) -> None:
    seen: set[str] = set()
    dups: list[str] = []
    for r in results:
        if r.drug_id in seen:
            dups.append(r.drug_id)
        seen.add(r.drug_id)
    if dups:
        raise DuplicateCandidateError(dups)


def _to_ranked(result: EvidenceFusionResult, rank: int) -> RankedCandidate:
    return RankedCandidate(
        rank=rank,
        disease_id=result.disease_id,
        drug_id=result.drug_id,
        disease_name=result.disease_name,
        drug_name=result.drug_name,
        repurposing_score=result.repurposing_score,
        matched_gene_hgnc_ids=list(result.matched_gene_hgnc_ids),
        matched_disease_gene_ids=list(result.matched_disease_gene_ids),
        matched_drug_target_ids=list(result.matched_drug_target_ids),
        matched_pathway_reactome_ids=list(result.matched_pathway_reactome_ids),
        generation_methods=list(result.generation_methods),
        fusion=result,
    )


def rank_candidates(
    fusion_results: list[EvidenceFusionResult],
    *,
    top_n: int | None = None,
) -> RankedCandidateResult:
    """Order the Phase 7 results. Returns the full list unless ``top_n`` is given."""
    if not isinstance(fusion_results, list) or any(
        not isinstance(r, EvidenceFusionResult) for r in fusion_results
    ):
        raise TypeError("fusion_results must be a list[EvidenceFusionResult]")

    n_input = len(fusion_results)
    _check_unique(fusion_results)
    applied = _validate_top_n(top_n, n_input)

    ordered = sorted(fusion_results, key=lambda r: (-r.repurposing_score, r.drug_id))
    ranked = [_to_ranked(r, i + 1) for i, r in enumerate(ordered)]
    if applied is not None:
        ranked = ranked[:applied]

    disease_ids = {r.disease_id for r in fusion_results}
    disease_id = next(iter(disease_ids)) if len(disease_ids) == 1 else None
    disease_name = (
        fusion_results[0].disease_name if disease_id is not None and fusion_results else None
    )
    scoring_versions = {r.scoring_version for r in fusion_results}

    provenance = RankingProvenance(
        ranking_version=RANKING_VERSION,
        n_input=n_input,
        n_ranked=len(ranked),
        top_n_requested=top_n,
        top_n_applied=applied,
        scoring_version=next(iter(scoring_versions)) if len(scoring_versions) == 1 else None,
        disclaimer=DISCLAIMER,
    )
    return RankedCandidateResult(
        disease_id=disease_id,
        disease_name=disease_name,
        candidates=ranked,
        n_candidates=len(ranked),
        provenance=provenance,
    )


def rank_for_disease(
    disease_query: str,
    *,
    top_n: int | None = None,
    use_ml: bool = True,
    config: FusionConfig | None = None,
) -> RankedCandidateResult:
    """Convenience: run the whole pipeline for one disease and rank every candidate."""
    from app.services.fusion import fuse_for_disease

    fused = fuse_for_disease(disease_query, config=config, use_ml=use_ml)
    return rank_candidates(fused, top_n=top_n)
