"""Phase 11 dashboard API: disease query -> pipeline run -> candidate detail.

Thin routing only — every response is built from
``app.services.pipeline`` (which itself only composes the existing Level
2-10 services). No score/rank/evidence is computed in this module.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import DISCLAIMER
from app.models.disease import ResolutionStatus
from app.models.explanation import CandidateExplanation
from app.models.graph import EvidenceGraph
from app.models.ranking import RankedCandidate
from app.services import pipeline as pipeline_service
from app.services.disease.errors import DiseaseIntelligenceError, DiseaseResolutionError

from .schemas import (
    AmbiguousDiseaseResponse,
    CandidateSummary,
    DiseaseOverview,
    PipelineRunResponse,
    UnsupportedDiseaseResponse,
)

router = APIRouter()


def _resolution_error_to_http(exc: DiseaseResolutionError) -> HTTPException:
    result = exc.result
    if result.status is ResolutionStatus.EMPTY_QUERY:
        return HTTPException(status_code=400, detail={"status": "empty_query", "message": "Enter a disease name, alias, or id."})
    if result.status is ResolutionStatus.AMBIGUOUS:
        body = AmbiguousDiseaseResponse(
            query=result.query,
            candidates=result.candidates,
            message=result.message or "Multiple diseases match this query — pick one.",
        )
        return HTTPException(status_code=409, detail=body.model_dump(mode="json"))
    # NOT_SUPPORTED (and any other non-resolved status)
    body = UnsupportedDiseaseResponse(
        query=result.query,
        suggestions=result.suggestions,
        message=result.message or f"{result.query!r} is not a supported disease.",
    )
    return HTTPException(status_code=404, detail=body.model_dump(mode="json"))


@router.get("/pipeline", response_model=PipelineRunResponse, tags=["pipeline"])
def run_pipeline(
    query: str = Query(..., min_length=0, description="disease name, alias, or internal/ontology id"),
    top_n: int = Query(10, ge=1, le=50, description="how many ranked candidates to return"),
) -> PipelineRunResponse:
    """Resolve a disease and run candidate generation through ranking
    (Levels 2-8). Does NOT generate explanations or graphs — those are
    fetched lazily per candidate via the endpoints below, so a query never
    pays for AI-explanation calls the user never asks to see."""
    try:
        run = pipeline_service.run_pipeline(query, top_n=top_n)
    except DiseaseResolutionError as exc:
        raise _resolution_error_to_http(exc) from exc
    except DiseaseIntelligenceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    profile = run.disease_profile
    ranked = run.ranked

    def _has(component_name: str) -> int:
        n = 0
        for c in ranked.candidates:
            comp = c.component(component_name)
            if comp is not None and comp.available:
                n += 1
        return n

    return PipelineRunResponse(
        disease=DiseaseOverview(
            disease_id=profile.disease_id,
            disease_name=profile.disease_name,
            ontology_id=profile.ontology_id,
            gene_count=profile.molecular_profile.gene_count,
            pathway_count=profile.molecular_profile.pathway_count,
            genes_truncated=profile.molecular_profile.genes_truncated,
            summary_text=profile.summary_text,
        ),
        candidate_summary=CandidateSummary(
            candidates_discovered=run.candidate_count,
            candidates_ranked=ranked.n_candidates,
            counts_by_method=run.counts_by_method,
            n_with_gene_target_evidence=_has("gene_target"),
            n_with_pathway_evidence=_has("pathway"),
            n_with_ml_evidence=_has("ml"),
        ),
        ranked=ranked,
        disclaimer=DISCLAIMER,
    )


@router.get("/candidate", response_model=RankedCandidate, tags=["pipeline"])
def candidate(
    disease_id: str = Query(..., description="disease_id from a prior /pipeline response"),
    drug_id: str = Query(..., description="drug_id of one of that response's ranked candidates"),
) -> RankedCandidate:
    """One already-ranked candidate on its own — lets the Candidate Analysis
    page be a deep-linkable route instead of requiring the full ranked list
    to still be in memory. Reuses the same process-local cache as
    /candidate/explanation and /candidate/graph; still requires /pipeline to
    have been run at least once for this disease."""
    try:
        ranked_candidate, _generation = pipeline_service.get_candidate(disease_id, drug_id)
        return ranked_candidate
    except pipeline_service.PipelineNotRunError as exc:
        raise HTTPException(
            status_code=409, detail={"message": "Run the pipeline for this disease first.", "disease_id": disease_id}
        ) from exc
    except pipeline_service.CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail={"message": str(exc), "disease_id": disease_id, "drug_id": drug_id}
        ) from exc


@router.get("/candidate/explanation", response_model=CandidateExplanation, tags=["pipeline"])
def candidate_explanation(
    disease_id: str = Query(..., description="disease_id from a prior /pipeline response"),
    drug_id: str = Query(..., description="drug_id of one of that response's ranked candidates"),
) -> CandidateExplanation:
    """Phase 9, lazily, for one candidate. Calls the backend-configured
    DeepSeek/Featherless provider (or its deterministic fallback) — never
    called from the browser directly."""
    try:
        return pipeline_service.explain(disease_id, drug_id)
    except pipeline_service.PipelineNotRunError as exc:
        raise HTTPException(
            status_code=409, detail={"message": "Run the pipeline for this disease first.", "disease_id": disease_id}
        ) from exc
    except pipeline_service.CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail={"message": str(exc), "disease_id": disease_id, "drug_id": drug_id}
        ) from exc


@router.get("/candidate/graph", response_model=EvidenceGraph, tags=["pipeline"])
def candidate_graph(
    disease_id: str = Query(...),
    drug_id: str = Query(...),
    include_explanation: bool = Query(True, description="also attach the Phase 9 explanation node"),
) -> EvidenceGraph:
    """Phase 10, lazily, for one candidate."""
    try:
        return pipeline_service.graph_for_candidate(
            disease_id, drug_id, include_explanation=include_explanation
        )
    except pipeline_service.PipelineNotRunError as exc:
        raise HTTPException(
            status_code=409, detail={"message": "Run the pipeline for this disease first.", "disease_id": disease_id}
        ) from exc
    except pipeline_service.CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail={"message": str(exc), "disease_id": disease_id, "drug_id": drug_id}
        ) from exc
