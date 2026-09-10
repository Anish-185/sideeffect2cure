"""Phase 8 schemas: the ordered candidate list.

Phase 8 **only orders** the Phase 7 ``EvidenceFusionResult`` objects. It does not
recalculate biology, does not create a new score, and does not modify the
``repurposing_score``.

    Ranking is based on the Phase 7 computational ``repurposing_score``.
    It does NOT establish clinical efficacy, treatment suitability, or safety.

Every ranked candidate embeds the **full** ``EvidenceFusionResult`` so the later
AI-explanation, evidence-graph and dashboard phases can answer "why did this
candidate get this score / this rank?" without re-running anything.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.fusion import EvidenceFusionResult

RANKING_VERSION = "1.0"

_INTERPRETATION = (
    "Ordered list of computationally prioritized candidates for further "
    "investigation, sorted by the Phase 7 repurposing_score. A higher rank means "
    "more of the available computational/biological evidence supports "
    "investigating this drug for this disease. It does NOT establish clinical "
    "efficacy, treatment suitability, patient response, or safety, and is not a "
    "medical recommendation."
)


class RankedCandidate(BaseModel):
    """One candidate at its position in the ordered list."""

    rank: int = Field(ge=1, description="1-based position after sorting (unique; ties broken by drug_id)")

    disease_id: str
    drug_id: str
    disease_name: str
    drug_name: str

    repurposing_score: float = Field(description="UNCHANGED from Phase 7")

    # quick-access identifiers for the future evidence graph (also inside `fusion`)
    matched_gene_hgnc_ids: list[str] = Field(default_factory=list)
    matched_disease_gene_ids: list[str] = Field(default_factory=list)
    matched_drug_target_ids: list[str] = Field(default_factory=list)
    matched_pathway_reactome_ids: list[str] = Field(default_factory=list)
    generation_methods: list[str] = Field(default_factory=list)

    # the complete Phase 7 record — nothing is dropped
    fusion: EvidenceFusionResult

    model_config = {"protected_namespaces": ()}

    def component(self, name: str):
        return self.fusion.component(name)


class RankingProvenance(BaseModel):
    ranking_version: str = RANKING_VERSION
    ranking_signal: str = "Phase 7 repurposing_score (higher first)"
    tie_breaker: str = (
        "drug_id ascending (lexicographic) — stable, deterministic; ranks are always unique"
    )
    scores_recalculated: bool = False
    biology_recalculated: bool = False
    n_input: int
    n_ranked: int
    top_n_requested: int | None = None
    top_n_applied: int | None = None
    scoring_version: str | None = None
    disclaimer: str
    interpretation: str = _INTERPRETATION


class RankedCandidateResult(BaseModel):
    """Container: the ordered candidates + how the ordering was produced."""

    disease_id: str | None = Field(
        default=None, description="the single disease_id shared by all candidates, else None"
    )
    disease_name: str | None = None

    candidates: list[RankedCandidate]
    n_candidates: int

    provenance: RankingProvenance

    model_config = {"protected_namespaces": ()}

    def top(self, n: int) -> list[RankedCandidate]:
        return self.candidates[: max(0, n)]

    def table_rows(self) -> list[dict]:
        """Flat rows for a later table/dashboard view (no evidence dropped from
        the model — this is just a convenience projection)."""
        rows = []
        for c in self.candidates:
            gt, pw, ml = (c.component("gene_target"), c.component("pathway"), c.component("ml"))
            rows.append(
                {
                    "rank": c.rank,
                    "drug_id": c.drug_id,
                    "drug_name": c.drug_name,
                    "disease_id": c.disease_id,
                    "repurposing_score": c.repurposing_score,
                    "gene_target_value": gt.value if gt and gt.available else None,
                    "gene_target_points": gt.contribution_points if gt else None,
                    "pathway_value": pw.value if pw and pw.available else None,
                    "pathway_points": pw.contribution_points if pw else None,
                    "ml_value": ml.value if ml and ml.available else None,
                    "ml_points": ml.contribution_points if ml else None,
                    "generation_methods": c.generation_methods,
                }
            )
        return rows
