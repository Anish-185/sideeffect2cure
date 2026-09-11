"""Phase 9 schemas: grounded AI-powered candidate explanation.

    RankedCandidate  ->  ExplanationContext  ->  (LLM | deterministic)  ->  CandidateExplanation

The explanation layer only **narrates** evidence Phases 4-8 already computed.
It never recalculates the ``repurposing_score``, never reranks, never invents
a gene / target / pathway / mechanism / study, and never claims clinical
efficacy, safety, or treatment probability.

Design note: every *structural* field on ``CandidateExplanation``
(``value``, ``contribution_points``, ``supporting_ids``, ``status``, the
score and rank themselves) is built deterministically from the embedded
Phase 7 ``EvidenceFusionResult`` — never trusted from a model response. Only
prose fields (``summary``, evidence ``description``, ``limitations``) may
come from an LLM, and only after passing grounding validation
(``app.services.explanation.validate``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.fusion import DrugCharacterizationContext, EvidenceComponent, SideEffectContext

EXPLANATION_SCHEMA_VERSION = "1.0"

GROUNDING_NOTE = (
    "This explanation narrates computational evidence already produced by the "
    "deterministic pipeline (Levels 1-8). It does not establish clinical "
    "efficacy, safety, treatment suitability, or cure, and introduces no gene, "
    "target, pathway, mechanism, study, or clinical-trial fact beyond what the "
    "pipeline supplied."
)


class ExplanationContext(BaseModel):
    """Compact, structured evidence handed to the explanation provider.

    Everything here traces back to the Phase 8 ``RankedCandidate`` (and its
    embedded Phase 7 ``EvidenceFusionResult``) — nothing new is computed or
    fetched, and no unrelated dataset is attached. Deliberately small: this,
    not the repository, is what gets sent to the LLM.
    """

    disease_id: str
    disease_name: str
    drug_id: str
    drug_name: str

    rank: int
    repurposing_score: float
    score_scale: str = "0-100"

    generation_methods: list[str] = Field(default_factory=list)
    matched_gene_hgnc_ids: list[str] = Field(default_factory=list)
    matched_disease_gene_ids: list[str] = Field(default_factory=list)
    matched_drug_target_ids: list[str] = Field(default_factory=list)
    matched_pathway_reactome_ids: list[str] = Field(default_factory=list)

    components: list[EvidenceComponent] = Field(
        default_factory=list, description="the Phase 7 evidence families (gene_target/pathway/ml), verbatim"
    )
    drug_characterization: DrugCharacterizationContext | None = None
    side_effect_context: SideEffectContext | None = None

    ml_model_name: str | None = None
    ml_model_output: float | None = None
    ml_baseline_output: float | None = None

    weights_configured: dict[str, float] = Field(default_factory=dict)
    scoring_version: str
    ranking_version: str
    disclaimer: str

    model_config = {"protected_namespaces": ()}

    def component(self, name: str) -> EvidenceComponent | None:
        return next((c for c in self.components if c.name == name), None)

    def allowed_identifiers(self) -> set[str]:
        """Every identifier the explanation is permitted to reference by name."""
        ids: set[str] = {
            self.disease_id,
            self.drug_id,
            *self.matched_gene_hgnc_ids,
            *self.matched_disease_gene_ids,
            *self.matched_drug_target_ids,
            *self.matched_pathway_reactome_ids,
        }
        for c in self.components:
            for v in c.supporting.values():
                if isinstance(v, str):
                    ids.add(v)
                elif isinstance(v, list):
                    ids.update(x for x in v if isinstance(x, str))
        return ids

    def to_prompt_payload(self) -> dict:
        """Compact dict for the LLM prompt — drops ``None``s to keep it small."""
        return self.model_dump(exclude_none=True)


class BiologicalEvidenceItem(BaseModel):
    """One evidence family (gene-target or pathway), narrated.

    ``kind`` / ``status`` / ``value`` / ``contribution_points`` /
    ``supporting_ids`` are always deterministic — only ``description`` may be
    LLM-authored (and only post-validation).
    """

    kind: str = Field(description="'gene_target' | 'pathway'")
    status: str = Field(description="'supported' | 'assessed_no_support' | 'not_assessed'")
    value: float | None = None
    contribution_points: float | None = None
    supporting_ids: list[str] = Field(default_factory=list)
    description: str


class ModelEvidence(BaseModel):
    """The Phase 6 ML component, narrated. Structural fields are deterministic."""

    status: str = Field(description="'supported' | 'assessed_no_support' | 'not_assessed'")
    model_name: str | None = None
    model_output: float | None = None
    baseline_output: float | None = None
    contribution_points: float | None = None
    top_feature_names: list[str] = Field(default_factory=list)
    description: str

    model_config = {"protected_namespaces": ()}


class ExplanationProvenance(BaseModel):
    explanation_version: str = EXPLANATION_SCHEMA_VERSION
    provider: str = Field(description="'deepseek_featherless' | 'deterministic_fallback'")
    model_name: str | None = None
    generated_at: str = Field(description="ISO-8601 UTC timestamp")
    scoring_version: str
    ranking_version: str
    fallback_reason: str | None = Field(
        default=None, description="set iff the LLM provider was tried and failed/was rejected"
    )
    validation_notes: list[str] = Field(default_factory=list)
    grounding_note: str = GROUNDING_NOTE
    disclaimer: str

    model_config = {"protected_namespaces": ()}


class CandidateExplanation(BaseModel):
    """Validated Phase 9 output for one ranked candidate."""

    disease_id: str
    drug_id: str
    disease_name: str
    drug_name: str
    rank: int = Field(description="UNCHANGED from Phase 8")
    repurposing_score: float = Field(description="UNCHANGED from Phase 7")

    summary: str = Field(description="why this candidate was computationally prioritized")
    biological_evidence: list[BiologicalEvidenceItem]
    model_evidence: ModelEvidence
    limitations: list[str]

    provenance: ExplanationProvenance

    model_config = {"protected_namespaces": ()}
