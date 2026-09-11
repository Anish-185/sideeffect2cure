"""Phase 11 pipeline orchestration for the dashboard API.

    disease query -> Levels 2-8 (candidate generation -> ranking)
        -> cached CachedRun
        -> lazy, per-candidate: Phase 9 explanation / Phase 10 graph

This module runs no new science — it is the same Level 2-8 composition
already used by ``fuse_for_disease`` / ``rank_for_disease`` /
``build_graph_for_disease``, plus a small in-memory cache so the dashboard
can run the (expensive) ranking once per disease and then request each
candidate's explanation/graph lazily, on demand, without recomputing
anything already computed.
"""

from __future__ import annotations

from app.models.candidate import CandidateDrug
from app.models.explanation import CandidateExplanation
from app.models.graph import EvidenceGraph
from app.models.ranking import RankedCandidate, RankedCandidateResult
from app.services.pipeline import cache as _cache
from app.services.pipeline.errors import CandidateNotFoundError, PipelineNotRunError

_DEFAULT_TOP_N = 10


def run_pipeline(
    disease_query: str,
    *,
    top_n: int = _DEFAULT_TOP_N,
    use_ml: bool = True,
) -> _cache.CachedRun:
    """Resolve the disease and run candidate generation -> features -> ML ->
    evidence fusion -> ranking (Levels 2-8, unchanged). Caches the result
    (keyed by the resolved ``disease_id``) so later ``explain``/``graph_for_candidate``
    calls for the same disease reuse it instead of recomputing.

    Raises whatever ``build_disease_profile`` raises for an unsupported/empty
    query (``app.services.disease.errors.DiseaseIntelligenceError``).
    """
    from app.services.candidates import default_index, generate_candidates
    from app.services.disease import build_disease_profile
    from app.services.features import build_feature_vectors
    from app.services.fusion import fuse_all
    from app.services.ranking import rank_candidates

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

    fused = fuse_all(result.candidates, vectors, predictions)
    ranked = rank_candidates(fused, top_n=top_n)

    run = _cache.CachedRun(
        disease_profile=profile,
        candidate_count=result.candidate_count,
        counts_by_method=dict(result.counts_by_method),
        ranked=ranked,
        generation_by_drug={c.drug_id: c for c in result.candidates},
    )
    _cache.put(run)
    return run


def get_run(disease_id: str) -> _cache.CachedRun:
    run = _cache.get(disease_id)
    if run is None:
        raise PipelineNotRunError(disease_id)
    return run


def get_candidate(disease_id: str, drug_id: str) -> tuple[RankedCandidate, CandidateDrug]:
    """Look up an already-ranked candidate + its Level 4 generation record
    from the cached run. Raises ``PipelineNotRunError`` /
    ``CandidateNotFoundError`` rather than silently recomputing anything."""
    run = get_run(disease_id)
    ranked_candidate = next((c for c in run.ranked.candidates if c.drug_id == drug_id), None)
    generation_candidate = run.generation_by_drug.get(drug_id)
    if ranked_candidate is None or generation_candidate is None:
        raise CandidateNotFoundError(disease_id, drug_id)
    return ranked_candidate, generation_candidate


def explain(
    disease_id: str, drug_id: str, *, provider=None  # ExplanationProvider | None
) -> CandidateExplanation:
    """Phase 9, lazily, for exactly one candidate the pipeline already ranked."""
    from app.services.explanation import explain_candidate

    ranked_candidate, _generation_candidate = get_candidate(disease_id, drug_id)
    return explain_candidate(ranked_candidate, provider=provider)


def graph_for_candidate(
    disease_id: str, drug_id: str, *, include_explanation: bool = True
) -> EvidenceGraph:
    """Phase 10, lazily, for exactly one candidate the pipeline already
    ranked. Reuses the (possibly already-cached) Phase 9 explanation rather
    than generating a second one."""
    from app.services.graph import build_candidate_graph

    ranked_candidate, generation_candidate = get_candidate(disease_id, drug_id)
    explanation = explain(disease_id, drug_id) if include_explanation else None
    return build_candidate_graph(ranked_candidate, generation_candidate, explanation=explanation)


def ranked_result_for(disease_id: str) -> RankedCandidateResult:
    return get_run(disease_id).ranked
