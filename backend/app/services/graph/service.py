"""Phase 10 orchestration: disease query -> full pipeline -> EvidenceGraph.

Runs Levels 2-8 itself (mirroring ``fuse_for_disease`` / ``rank_for_disease``)
because, unlike those convenience functions, the graph builder needs the
intermediate Level 4 ``CandidateDrug`` objects (for their gene-target /
pathway provenance) alongside the final ``RankedCandidate``s — information
``rank_for_disease`` does not expose.
"""

from __future__ import annotations

from app.models.explanation import CandidateExplanation
from app.models.graph import EvidenceGraph
from app.models.ranking import RankedCandidate
from app.services.graph.build import build_evidence_graph
from app.services.graph.errors import InconsistentGraphInputError


def build_graph_for_candidates(
    candidates: list[RankedCandidate],
    *,
    include_explanations: bool = True,
    explanation_provider=None,  # app.services.explanation.provider.ExplanationProvider | None
) -> EvidenceGraph:
    """Build the evidence graph for an already-ranked list of candidates
    (e.g. ``ranked_result.top(n)``), re-deriving only the Level 4
    ``CandidateDrug`` objects they need. Candidate generation is
    deterministic, so this is the exact same ``CandidateDrug`` the original
    pipeline run produced — not a new inference, just re-fetching it because
    ``RankedCandidate`` only keeps the matched *ids*, not the full match
    records with their provenance."""
    if not candidates:
        raise InconsistentGraphInputError("candidates must be non-empty")

    disease_ids = {c.disease_id for c in candidates}
    if len(disease_ids) != 1:
        raise InconsistentGraphInputError("all candidates must share the same disease_id")

    from app.services.candidates import default_index, generate_candidates
    from app.services.disease import build_disease_profile

    idx = default_index()
    profile = build_disease_profile(next(iter(disease_ids)))
    result = generate_candidates(profile, index=idx)
    gen_by_drug = {c.drug_id: c for c in result.candidates}

    generation_candidates = []
    for c in candidates:
        gen = gen_by_drug.get(c.drug_id)
        if gen is None:
            raise InconsistentGraphInputError(
                f"no CandidateDrug found for disease {c.disease_id!r} / drug {c.drug_id!r}"
            )
        generation_candidates.append(gen)

    explanations: list[CandidateExplanation] | None = None
    if include_explanations:
        from app.services.explanation import explain_candidate

        explanations = [
            explain_candidate(c, provider=explanation_provider) for c in candidates
        ]

    return build_evidence_graph(candidates, generation_candidates, explanations=explanations)


def build_graph_for_disease(
    disease_query: str,
    *,
    top_n: int = 1,
    use_ml: bool = True,
    include_explanations: bool = True,
    explanation_provider=None,  # app.services.explanation.provider.ExplanationProvider | None
) -> EvidenceGraph:
    """Convenience: run the whole pipeline for one disease and build the
    evidence graph for its top-N ranked candidates (default: just the top
    candidate). ``top_n`` may be any positive int — 1, 3, 10, ... — nothing
    is hardcoded to a specific count."""
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

    top_candidates = ranked.candidates
    gen_by_drug = {c.drug_id: c for c in result.candidates}
    generation_candidates = [gen_by_drug[c.drug_id] for c in top_candidates if c.drug_id in gen_by_drug]

    explanations: list[CandidateExplanation] | None = None
    if include_explanations:
        from app.services.explanation import explain_candidate

        explanations = [
            explain_candidate(c, provider=explanation_provider) for c in top_candidates
        ]

    return build_evidence_graph(top_candidates, generation_candidates, explanations=explanations)
