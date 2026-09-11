"""Phase 11 API response shapes.

Thin DTOs the dashboard actually needs — every field is a pass-through or a
plain count of an existing pipeline object (``DiseaseProfile`` /
``CandidateGenerationResult`` / ``RankedCandidateResult``). No score,
ranking, or evidence value is computed here; this module only shapes HTTP
responses. Business logic stays in ``app.services.pipeline``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.disease import DiseaseMatch
from app.models.drug import DrugMatch
from app.models.ranking import RankedCandidateResult


class DiseaseOverview(BaseModel):
    disease_id: str
    disease_name: str
    ontology_id: str | None
    gene_count: int
    pathway_count: int
    genes_truncated: bool = Field(
        description="True if Level 1's per-disease gene cap was hit — the profile is not exhaustive"
    )
    summary_text: str


class CandidateSummary(BaseModel):
    candidates_discovered: int = Field(description="Level 4 candidate pool size before ranking")
    candidates_ranked: int = Field(description="candidates actually returned in `ranked` (top_n applied)")
    counts_by_method: dict[str, int] = Field(description="Level 4 CandidateGenerationResult.counts_by_method")
    n_with_gene_target_evidence: int = Field(description="of the ranked candidates, how many have an available gene_target evidence component")
    n_with_pathway_evidence: int
    n_with_ml_evidence: int


class PipelineRunResponse(BaseModel):
    """Everything the main dashboard view needs for one disease, in one
    request: overview + summary + the full ranked list (each candidate
    already embeds its complete Phase 7 score breakdown)."""

    disease: DiseaseOverview
    candidate_summary: CandidateSummary
    ranked: RankedCandidateResult
    disclaimer: str


class AmbiguousDiseaseResponse(BaseModel):
    """Returned (409) when the query matches more than one disease."""

    status: str = "ambiguous"
    query: str
    candidates: list[DiseaseMatch]
    message: str


class UnsupportedDiseaseResponse(BaseModel):
    """Returned (404) when the query matches no supported disease."""

    status: str = "not_supported"
    query: str
    suggestions: list[str]
    message: str


class AmbiguousDrugResponse(BaseModel):
    """Returned (409) when the query matches more than one drug."""

    status: str = "ambiguous"
    query: str
    candidates: list[DrugMatch]
    message: str


class UnsupportedDrugResponse(BaseModel):
    """Returned (404) when the query matches no supported drug."""

    status: str = "not_supported"
    query: str
    suggestions: list[str]
    message: str
