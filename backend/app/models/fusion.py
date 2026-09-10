"""Phase 7 schemas: evidence fusion + the internal repurposing score.

`repurposing_score` is an **internal research prioritization score** on a 0-100
scale. It answers:

    "How strongly does the available computational / biological evidence support
     prioritizing this existing drug for further investigation for this disease?"

It is **not** clinical efficacy, **not** probability of treatment success, **not**
patient-response probability, **not** a medical or safety recommendation. Nothing
in this module makes such a claim.

The result keeps every evidence component visible (value, weight, formula,
supporting data, provenance) so Phase 8 (ranking) and later phases (AI
explanation, evidence graph, dashboard) can consume the breakdown, not just the
number.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

SCORING_VERSION = "1.0"

_INTERPRETATION = (
    "Internal research prioritization score (0-100). Higher = more of the "
    "available computational/biological evidence supports investigating this "
    "existing drug for this disease. NOT clinical efficacy, NOT treatment "
    "probability, NOT a medical recommendation."
)


class EvidenceComponent(BaseModel):
    """One independent evidence family, normalized to [0, 1]."""

    name: str = Field(description="'gene_target' | 'pathway' | 'ml'")
    available: bool = Field(
        description="True if this evidence could be assessed; False = NOT ASSESSED "
        "(missing != negative). An available component with value 0.0 means "
        "'assessed, no support found'."
    )
    value: float | None = Field(
        default=None, description="normalized evidence strength in [0,1]; None iff not available"
    )
    configured_weight: float = Field(description="weight from FusionConfig (before renormalization)")
    effective_weight: float | None = Field(
        default=None,
        description="weight actually used = configured_weight / sum(configured weights of AVAILABLE "
        "components); None iff not available",
    )
    contribution_points: float | None = Field(
        default=None, description="points this component added to the 0-100 score "
        "(value * effective_weight * 100); None iff not available",
    )
    calculation_method: str = Field(description="the exact formula used")
    supporting: dict[str, float | int | bool | str | None | list] = Field(
        default_factory=dict, description="the underlying Level 4/5/6 values that fed this component"
    )
    provenance: str = Field(description="which pipeline levels / sources this evidence comes from")
    unavailable_reason: str | None = None


class SideEffectContext(BaseModel):
    """Descriptive only — NOT a scoring component.

    Side effects are retained for downstream context. A drug is **not** penalized
    for having many side effects: no defensible disease-relevant side-effect
    relationship exists in the current data.
    """

    side_effect_count: int
    has_sider_evidence: bool
    note: str = (
        "descriptive context only; NOT used in the repurposing score and NOT a "
        "safety assessment"
    )


class DrugCharacterizationContext(BaseModel):
    """Descriptive only — how well the drug is characterized, NOT scored.

    Not a scoring component: rewarding well-studied drugs would bias the score
    toward popular compounds rather than toward disease-relevant evidence.
    """

    drug_target_count: int
    drug_pathway_count: int
    mechanism_count: int
    action_type_counts: dict[str, int] = Field(default_factory=dict)
    note: str = "descriptive context only; NOT used in the repurposing score"


class FusionProvenance(BaseModel):
    scoring_version: str = SCORING_VERSION
    feature_schema_version: str | None = None
    prediction_schema_version: str | None = None
    weight_scheme: str = Field(
        default="prototype heuristic — NOT clinically validated; favours direct "
        "mechanistic evidence (gene-target) over looser pathway overlap, with the "
        "ML prior contributing but not dominating"
    )
    normalization: str
    missing_evidence_policy: str = Field(
        default="components that could not be assessed are marked unavailable and "
        "EXCLUDED from the weighted mean; the remaining weights are renormalized. "
        "Missing evidence is never treated as negative (0.0) evidence."
    )
    double_counting_policy: str = Field(
        default="Level 5 features that describe the same biological relationship are "
        "grouped into one evidence family and produce exactly one component; "
        "count and specificity are combined once, not counted as separate streams."
    )
    disclaimer: str


class EvidenceFusionResult(BaseModel):
    disease_id: str
    drug_id: str
    disease_name: str
    drug_name: str

    repurposing_score: float = Field(description="0-100 internal prioritization score", ge=0.0, le=100.0)
    score_scale: str = "0-100"

    components: list[EvidenceComponent]
    n_components_available: int
    n_components_unavailable: int
    weights_configured: dict[str, float]
    weights_renormalized_over_available: bool

    side_effect_context: SideEffectContext
    drug_characterization: DrugCharacterizationContext

    # ids preserved for the future evidence graph (not a graph here)
    matched_gene_hgnc_ids: list[str] = Field(default_factory=list)
    matched_disease_gene_ids: list[str] = Field(default_factory=list)
    matched_drug_target_ids: list[str] = Field(default_factory=list)
    matched_pathway_reactome_ids: list[str] = Field(default_factory=list)
    generation_methods: list[str] = Field(default_factory=list)

    ml_model_name: str | None = None
    ml_model_output: float | None = None
    ml_baseline_output: float | None = None

    scoring_version: str = SCORING_VERSION
    provenance: FusionProvenance
    interpretation: str = _INTERPRETATION

    model_config = {"protected_namespaces": ()}

    def component(self, name: str) -> EvidenceComponent | None:
        return next((c for c in self.components if c.name == name), None)
