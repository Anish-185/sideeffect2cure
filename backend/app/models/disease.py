"""Level 2 schemas: disease resolution results and the canonical disease profile.

These models are the contract between the disease-intelligence service
(:mod:`app.services.disease`) and every downstream component. Everything in a
``DiseaseProfile`` traces back to the Level 1 processed datasets — nothing here
is fabricated or inferred beyond simple aggregation (counts, ordering, means
that Level 1 already computed).

Language convention used throughout:
  * a gene/pathway is *associated with* a disease — never *causes* it;
  * a profile is *potentially relevant* evidence — never *therapeutically
    effective*.
This is a research hypothesis-generation tool, not a clinical decision system.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    EMPTY_QUERY = "empty_query"
    NOT_SUPPORTED = "not_supported"
    AMBIGUOUS = "ambiguous"


class MatchType(str, Enum):
    INTERNAL_ID = "internal_id"
    ONTOLOGY_ID = "ontology_id"
    EXACT_NAME = "exact_name"
    ALIAS = "alias"


class DiseaseMatch(BaseModel):
    """A single disease the resolver matched a query to."""

    disease_id: str = Field(description="internal id, e.g. DIS:000035")
    disease_name: str = Field(description="canonical name as stored in Level 1 (lower-case)")
    ontology_id: str | None = Field(default=None, description="EFO / MONDO id")
    matched_on: MatchType
    matched_value: str = Field(description="the key that matched (name/alias/id)")


class ResolutionResult(BaseModel):
    """Deterministic outcome of resolving a user query. Never guesses."""

    status: ResolutionStatus
    query: str
    normalized_query: str
    match: DiseaseMatch | None = None
    candidates: list[DiseaseMatch] = Field(
        default_factory=list, description="populated when status == AMBIGUOUS"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="near-name hints for NOT_SUPPORTED; never auto-selected"
    )
    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status is ResolutionStatus.RESOLVED


class ExternalIdentifier(BaseModel):
    external_id: str
    source: str
    is_primary: bool = False


class GeneAssociation(BaseModel):
    """One disease-gene association, straight from ``disease_genes``."""

    gene_id: str = Field(description="internal id, e.g. GENE:000202")
    gene_name: str | None = Field(default=None, description="approved symbol, e.g. TP53")
    ensembl_id: str | None = None
    association_score: float | None = Field(
        default=None,
        description="Open Targets overall association score in [0,1]; 'associated with', not 'causes'",
    )
    source: str


class PathwayAssociation(BaseModel):
    """One disease-pathway association from the DERIVED ``disease_pathways`` table.

    Provenance matters: this is *not* an independently curated disease-pathway
    assertion. It means "this Reactome pathway is over-represented among the
    disease's associated genes" (>= ``gene_support_count`` supporting genes).
    """

    pathway_id: str = Field(description="internal id, e.g. PATH:000157")
    pathway_name: str
    reactome_id: str | None = None
    gene_support_count: int | None = Field(
        default=None, description="number of the disease's associated genes mapped into this pathway"
    )
    association_score: float | None = Field(
        default=None, description="mean association score of the supporting genes (derived)"
    )
    source: str


class ProfileProvenance(BaseModel):
    """Where every part of the profile comes from, and its limitations."""

    disease_source: str
    datasets_used: list[str]
    gene_source: str
    gene_score_semantics: str
    genes_capped_per_disease: int = Field(
        description="Level 1 kept only the top-N Open Targets associations per disease"
    )
    genes_truncated: bool = Field(description="True if this disease hit the Level 1 cap")
    pathway_source: str
    pathway_derivation: str
    pathway_min_gene_support: int
    snapshot_note: str
    disclaimer: str


class DiseaseMolecularProfile(BaseModel):
    """Compact Disease -> genes -> pathways rollup for downstream sense-checking.

    NOT a gene-expression signature and NOT a molecular embedding — those are
    later evidence layers. Just a deterministic summary of the association data.
    """

    gene_count: int
    pathway_count: int
    mean_gene_association_score: float | None
    max_gene_association_score: float | None
    top_gene_symbols: list[str]
    top_pathway_names: list[str]
    genes_truncated: bool


class DiseaseProfile(BaseModel):
    """Canonical structured representation of a resolved disease.

    This is what the Disease Resolver hands to Candidate Drug Generation,
    Feature Engineering and Explainability in later levels.
    """

    disease_id: str
    disease_name: str
    ontology_id: str | None = None
    external_identifiers: list[ExternalIdentifier] = Field(default_factory=list)
    genes: list[GeneAssociation] = Field(default_factory=list)
    pathways: list[PathwayAssociation] = Field(default_factory=list)
    molecular_profile: DiseaseMolecularProfile
    provenance: ProfileProvenance
    summary_text: str = Field(description="deterministic, data-derived plain-text summary")
