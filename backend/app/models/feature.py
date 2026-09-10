"""Level 5 schemas: the disease-drug FeatureVector.

A FeatureVector is a **deterministic, descriptive** summary of the biological
relationship between one disease and one candidate drug. It is computed only
from the Level 2 ``DiseaseProfile``, the Level 3 ``DrugProfile``, the Level 4
``CandidateDrug`` and their underlying evidence.

    features describe evidence  —  they do NOT decide the answer

There is deliberately **no** ``repurposing_score`` / ``probability`` /
``confidence`` / ``rank`` / ``similarity`` field, and nothing here is trained,
predicted or fused. Counts are counts; fractions are explicit ratios with
documented denominators; booleans are source-availability flags. Missing /
undefined values are ``None`` — never ``NaN`` or ``inf``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

FEATURE_SCHEMA_VERSION = "1.0"


class FeatureVectorMetadata(BaseModel):
    """Provenance + interpretation notes for a FeatureVector."""

    feature_schema_version: str = FEATURE_SCHEMA_VERSION
    gene_target_bridge: str = Field(
        default=(
            "HGNC complete set: disease gene ensembl_gene_id -> hgnc_id ; "
            "drug target uniprot -> hgnc_id ; overlap computed on hgnc_id"
        )
    )
    pathway_intersection: str = Field(
        default="direct Reactome stable-id (R-HSA-*) set intersection; no similarity, no embeddings"
    )
    drug_pathway_source: str = Field(
        description="'level4_index_uncapped' | 'drug_profile_capped_100' | 'unavailable'"
    )
    ratio_denominators: dict[str, str] = Field(default_factory=dict)
    unavailable: list[str] = Field(
        default_factory=list,
        description="feature groups with no source in this run (values are null/0 + flagged)",
    )
    leakage_guard: str = Field(
        default=(
            "features use only DiseaseProfile / DrugProfile / CandidateDrug inputs; no ML "
            "output, label, ranking or therapeutic-outcome information is used"
        )
    )
    disclaimer: str


class FeatureVector(BaseModel):
    """Descriptive features for a (disease, drug) candidate pair. No scoring."""

    # -- identity --
    disease_id: str
    drug_id: str
    disease_name: str
    drug_name: str

    # -- A. candidate-generation (how Level 4 produced this candidate) --
    generated_by_gene_target: bool
    generated_by_pathway: bool
    generation_method_count: int = Field(description="1 or 2")
    gene_target_reason_count: int = Field(description="# GeneTargetMatch reasons on the candidate")
    pathway_reason_count: int = Field(description="# PathwayMatch reasons on the candidate")

    # -- B. disease-gene / drug-target overlap (HGNC id join) --
    disease_gene_count: int = Field(description="genes on the DiseaseProfile (Level 1 top-N cap)")
    disease_gene_hgnc_mapped_count: int
    drug_target_count: int = Field(description="distinct drug targets on the DrugProfile")
    drug_target_hgnc_mapped_count: int
    matched_gene_target_count: int = Field(description="distinct HGNC genes shared by both sides")
    matched_disease_gene_count: int
    matched_drug_target_count: int
    fraction_of_drug_targets_matching_disease_genes: float | None = Field(
        description="matched_gene_target_count / drug_target_hgnc_mapped_count ; null if denom 0"
    )
    fraction_of_disease_genes_targeted_by_drug: float | None = Field(
        description="matched_gene_target_count / disease_gene_hgnc_mapped_count ; null if denom 0"
    )

    # -- C. pathway overlap (direct Reactome id intersection) --
    disease_pathway_count: int
    drug_pathway_count: int
    matched_pathway_count: int
    fraction_of_drug_pathways_matching_disease_pathways: float | None = Field(
        description="matched_pathway_count / drug_pathway_count ; null if denom 0"
    )
    fraction_of_disease_pathways_matching_drug_pathways: float | None = Field(
        description="matched_pathway_count / disease_pathway_count ; null if denom 0"
    )

    # -- D. side effects (drug burden only; no disease relevance claimed) --
    side_effect_count: int

    # -- E. targets / action types --
    unique_target_count: int
    inhibitor_target_count: int
    agonist_target_count: int
    antagonist_target_count: int
    targets_with_action_type_count: int
    targets_missing_action_type_count: int
    target_action_type_counts: dict[str, int] = Field(
        default_factory=dict, description="full breakdown, only action types present in the data"
    )
    target_type_counts: dict[str, int] = Field(
        default_factory=dict, description="full breakdown, only target types present in the data"
    )

    # -- F. drug-level structural counts --
    mechanism_count: int

    # -- G. evidence-source availability (flags, not confidence) --
    has_sider_evidence: bool
    has_chembl_target_evidence: bool
    has_reactome_pathway_evidence: bool
    has_gene_target_bridge: bool
    disease_pathways_available: bool

    metadata: FeatureVectorMetadata

    # -- flat numeric view for downstream ML --
    def to_feature_dict(self) -> dict[str, float | int | bool | None]:
        """Flat name -> value map (scalars only; the two count-dicts are flattened
        with an ``action_type__`` / ``target_type__`` prefix). No identity or
        metadata fields."""
        skip = {"disease_id", "drug_id", "disease_name", "drug_name", "metadata"}
        out: dict[str, float | int | bool | None] = {}
        for name, value in self.model_dump().items():
            if name in skip:
                continue
            if name == "target_action_type_counts":
                for k, v in value.items():
                    out[f"action_type__{k}"] = v
            elif name == "target_type_counts":
                for k, v in value.items():
                    out[f"target_type__{k}"] = v
            else:
                out[name] = value
        return out
