"""Phase 6 inference: FeatureVector[] -> PredictionResult[].

Same preprocessing as training. Each result carries the model output, the top
contributing Level 5 features for that row, and the ids needed for later
evidence-graph wiring. No score, no ranking, no fusion.
"""

from __future__ import annotations

import functools

from app.models.candidate import CandidateDrug
from app.models.feature import FeatureVector
from app.models.prediction import FeatureContribution, PredictionResult
from app.services.ml.model import PredictionModel
from app.services.ml.preprocessing import to_matrix

_DEFAULT_TOP_K = 6


@functools.cache
def _default_model() -> PredictionModel:
    return PredictionModel.load()


def reset_default_model() -> None:
    _default_model.cache_clear()


def _direction(contribution: float) -> str:
    if contribution > 1e-6:
        return "increases"
    if contribution < -1e-6:
        return "decreases"
    return "neutral"


def predict(
    feature_vectors: list[FeatureVector],
    *,
    model: PredictionModel | None = None,
    candidates: list[CandidateDrug] | None = None,
    top_k: int = _DEFAULT_TOP_K,
) -> list[PredictionResult]:
    if not feature_vectors:
        return []
    mdl = model or _default_model()
    X = to_matrix(feature_vectors)
    proba = mdl.predict_proba(X)
    baseline = mdl.baseline()
    cand_by_drug = {c.drug_id: c for c in (candidates or [])}

    results: list[PredictionResult] = []
    for i, fv in enumerate(feature_vectors):
        contribs = mdl.contributions(X[i])
        top = sorted(contribs, key=lambda c: abs(c[2]), reverse=True)[:top_k]
        cand = cand_by_drug.get(fv.drug_id)
        results.append(
            PredictionResult(
                disease_id=fv.disease_id,
                drug_id=fv.drug_id,
                disease_name=fv.disease_name,
                drug_name=fv.drug_name,
                model_name=mdl.name,
                model_version=mdl.metadata.model_version,
                feature_schema_version=fv.metadata.feature_schema_version,
                model_output=round(float(proba[i]), 6),
                baseline_output=round(float(baseline), 6),
                important_features=[
                    FeatureContribution(
                        feature_name=name,
                        feature_value=round(value, 6),
                        contribution=round(contribution, 6),
                        direction=_direction(contribution),
                    )
                    for name, value, contribution in top
                ],
                matched_gene_hgnc_ids=(cand.matched_gene_hgnc_ids if cand else []),
                matched_drug_target_ids=(cand.matched_drug_target_ids if cand else []),
                matched_pathway_reactome_ids=(cand.matched_pathway_reactome_ids if cand else []),
                generation_methods=([m.value for m in cand.methods] if cand else []),
                model_metadata=mdl.metadata,
            )
        )
    return results


def predict_for_disease(
    disease_query: str, *, model: PredictionModel | None = None, top_k: int = _DEFAULT_TOP_K
) -> list[PredictionResult]:
    """Convenience: run the whole pipeline for one disease query."""
    from app.services.candidates import default_index, generate_candidates
    from app.services.disease import build_disease_profile
    from app.services.features import build_feature_vectors

    idx = default_index()
    profile = build_disease_profile(disease_query)
    result = generate_candidates(profile, index=idx)
    vectors = build_feature_vectors(profile, result.candidates, index=idx)
    return predict(vectors, model=model, candidates=result.candidates, top_k=top_k)
