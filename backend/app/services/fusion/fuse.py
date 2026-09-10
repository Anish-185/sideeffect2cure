"""Phase 7 evidence fusion.

    CandidateDrug + FeatureVector + (optional) PredictionResult + FusionConfig
        -> EvidenceFusionResult (repurposing_score 0-100 + full component breakdown)

Deterministic. No randomness, no LLM, no live API. The score is an **internal
research prioritization score**, never a clinical claim.
"""

from __future__ import annotations

from app.core.config import DISCLAIMER
from app.models.candidate import CandidateDrug
from app.models.feature import FeatureVector
from app.models.fusion import (
    DrugCharacterizationContext,
    EvidenceComponent,
    EvidenceFusionResult,
    FusionProvenance,
    SideEffectContext,
)
from app.models.prediction import PredictionResult
from app.services.fusion.components import (
    gene_target_component,
    ml_component,
    pathway_component,
)
from app.services.fusion.config import DEFAULT_CONFIG, FusionConfig
from app.services.fusion.errors import InconsistentFusionInputError

_NORMALIZATION_NOTE = (
    "Every component is mapped to [0,1]. Match counts use a saturating cap "
    "(min(count, cap)/cap); ratios/probabilities are used directly (clipped to "
    "[0,1]). The score is 100 * weighted mean of the AVAILABLE components, with "
    "weights renormalized to sum to 1 over those components."
)


def _check_consistency(
    candidate: CandidateDrug, fv: FeatureVector, prediction: PredictionResult | None
) -> None:
    if not isinstance(candidate, CandidateDrug):
        raise InconsistentFusionInputError("candidate must be a CandidateDrug")
    if not isinstance(fv, FeatureVector):
        raise InconsistentFusionInputError("feature_vector must be a FeatureVector")
    if (candidate.drug_id, candidate.disease_id) != (fv.drug_id, fv.disease_id):
        raise InconsistentFusionInputError(
            f"candidate {(candidate.disease_id, candidate.drug_id)} != "
            f"feature vector {(fv.disease_id, fv.drug_id)}"
        )
    if prediction is not None and (prediction.drug_id, prediction.disease_id) != (
        fv.drug_id,
        fv.disease_id,
    ):
        raise InconsistentFusionInputError(
            f"prediction {(prediction.disease_id, prediction.drug_id)} != "
            f"feature vector {(fv.disease_id, fv.drug_id)}"
        )


def _fuse_components(
    components: list[EvidenceComponent],
) -> tuple[float, bool]:
    """Return (repurposing_score 0-100, weights_were_renormalized).

    Missing components are excluded; the remaining weights are renormalized.
    An available component with value 0.0 is kept (assessed, no support).
    """
    available = [c for c in components if c.available and c.value is not None]
    if not available:
        return 0.0, False

    total_w = sum(c.configured_weight for c in available)
    weighted = 0.0
    for c in available:
        eff = c.configured_weight / total_w
        c.effective_weight = round(eff, 6)
        c.contribution_points = round(c.value * eff * 100.0, 4)
        weighted += c.value * eff

    score = round(100.0 * weighted, 4)
    score = max(0.0, min(100.0, score))  # hard bounds guard
    renormalized = len(available) != len(components)
    return score, renormalized


def fuse_evidence(
    candidate: CandidateDrug,
    feature_vector: FeatureVector,
    prediction: PredictionResult | None = None,
    *,
    config: FusionConfig | None = None,
) -> EvidenceFusionResult:
    cfg = config or DEFAULT_CONFIG
    _check_consistency(candidate, feature_vector, prediction)
    fv = feature_vector

    components = [
        gene_target_component(fv, cfg),
        pathway_component(fv, cfg),
        ml_component(prediction, cfg),
    ]
    score, renormalized = _fuse_components(components)

    provenance = FusionProvenance(
        feature_schema_version=fv.metadata.feature_schema_version,
        prediction_schema_version=(
            prediction.prediction_schema_version if prediction is not None else None
        ),
        normalization=_NORMALIZATION_NOTE,
        disclaimer=DISCLAIMER,
    )

    return EvidenceFusionResult(
        disease_id=fv.disease_id,
        drug_id=fv.drug_id,
        disease_name=fv.disease_name,
        drug_name=fv.drug_name,
        repurposing_score=score,
        components=components,
        n_components_available=sum(1 for c in components if c.available),
        n_components_unavailable=sum(1 for c in components if not c.available),
        weights_configured=cfg.as_weight_map(),
        weights_renormalized_over_available=renormalized,
        side_effect_context=SideEffectContext(
            side_effect_count=fv.side_effect_count,
            has_sider_evidence=fv.has_sider_evidence,
        ),
        drug_characterization=DrugCharacterizationContext(
            drug_target_count=fv.drug_target_count,
            drug_pathway_count=fv.drug_pathway_count,
            mechanism_count=fv.mechanism_count,
            action_type_counts=dict(fv.target_action_type_counts),
        ),
        matched_gene_hgnc_ids=list(candidate.matched_gene_hgnc_ids),
        matched_disease_gene_ids=list(candidate.matched_disease_gene_ids),
        matched_drug_target_ids=list(candidate.matched_drug_target_ids),
        matched_pathway_reactome_ids=list(candidate.matched_pathway_reactome_ids),
        generation_methods=[m.value for m in candidate.methods],
        ml_model_name=(prediction.model_name if prediction is not None else None),
        ml_model_output=(prediction.model_output if prediction is not None else None),
        ml_baseline_output=(prediction.baseline_output if prediction is not None else None),
        provenance=provenance,
    )


def fuse_all(
    candidates: list[CandidateDrug],
    feature_vectors: list[FeatureVector],
    predictions: list[PredictionResult] | None = None,
    *,
    config: FusionConfig | None = None,
) -> list[EvidenceFusionResult]:
    """Fuse a batch. Input order is preserved — this does NOT rank."""
    fv_by_drug = {fv.drug_id: fv for fv in feature_vectors}
    pred_by_drug = {p.drug_id: p for p in (predictions or [])}
    out: list[EvidenceFusionResult] = []
    for cand in candidates:
        fv = fv_by_drug.get(cand.drug_id)
        if fv is None:
            continue
        out.append(
            fuse_evidence(cand, fv, pred_by_drug.get(cand.drug_id), config=config)
        )
    return out


def fuse_for_disease(
    disease_query: str, *, config: FusionConfig | None = None, use_ml: bool = True
) -> list[EvidenceFusionResult]:
    """Convenience: run the whole pipeline for one disease and fuse every candidate.

    Order follows candidate generation — NOT ranked.
    """
    from app.services.candidates import default_index, generate_candidates
    from app.services.disease import build_disease_profile
    from app.services.features import build_feature_vectors

    idx = default_index()
    profile = build_disease_profile(disease_query)
    result = generate_candidates(profile, index=idx)
    vectors = build_feature_vectors(profile, result.candidates, index=idx)

    predictions = None
    if use_ml:
        try:
            from app.services.ml import predict
            from app.services.ml.model import ModelNotTrainedError

            predictions = predict(vectors, candidates=result.candidates)
        except ModelNotTrainedError:
            predictions = None

    return fuse_all(result.candidates, vectors, predictions, config=config)
