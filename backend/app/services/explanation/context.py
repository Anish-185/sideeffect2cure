"""Phase 8 ``RankedCandidate`` -> Phase 9 ``ExplanationContext``.

Pure projection: every field already exists on the ranked candidate / its
embedded ``EvidenceFusionResult``. Nothing is computed, fetched, or fabricated
here — this module only decides what subset is compact enough to hand to an
LLM.
"""

from __future__ import annotations

from app.models.explanation import ExplanationContext
from app.models.ranking import RANKING_VERSION, RankedCandidate


def build_explanation_context(candidate: RankedCandidate) -> ExplanationContext:
    fusion = candidate.fusion
    return ExplanationContext(
        disease_id=candidate.disease_id,
        disease_name=candidate.disease_name,
        drug_id=candidate.drug_id,
        drug_name=candidate.drug_name,
        rank=candidate.rank,
        repurposing_score=candidate.repurposing_score,
        score_scale=fusion.score_scale,
        generation_methods=list(candidate.generation_methods),
        matched_gene_hgnc_ids=list(candidate.matched_gene_hgnc_ids),
        matched_disease_gene_ids=list(candidate.matched_disease_gene_ids),
        matched_drug_target_ids=list(candidate.matched_drug_target_ids),
        matched_pathway_reactome_ids=list(candidate.matched_pathway_reactome_ids),
        components=list(fusion.components),
        drug_characterization=fusion.drug_characterization,
        side_effect_context=fusion.side_effect_context,
        ml_model_name=fusion.ml_model_name,
        ml_model_output=fusion.ml_model_output,
        ml_baseline_output=fusion.ml_baseline_output,
        weights_configured=dict(fusion.weights_configured),
        scoring_version=fusion.scoring_version,
        ranking_version=RANKING_VERSION,
        disclaimer=fusion.provenance.disclaimer,
    )
