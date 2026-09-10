"""Level 4 schemas: candidate drug generation records.

A "candidate" is a drug that has at least one **real biological relationship**
to a disease worth investigating downstream. Candidate generation is a
*filter*, not a judgement:

    candidate  ==  "worthy of downstream investigation"
    candidate  !=  "effective treatment"  /  "therapeutic recommendation"

There are deliberately **no** score / probability / confidence / rank fields on
any model in this module. Those belong to later levels.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class GenerationMethod(str, Enum):
    GENE_TARGET = "gene_target"
    PATHWAY = "pathway"


class GeneTargetMatch(BaseModel):
    """A disease gene and a drug target that are the *same gene* (HGNC id join)."""

    hgnc_id: str = Field(description="the shared gene identity, e.g. HGNC:3236")
    gene_symbol: str | None = None

    # disease side (Level 2 DiseaseProfile / disease_genes)
    disease_gene_id: str = Field(description="internal id, e.g. GENE:000240")
    disease_gene_ensembl_id: str | None = None
    disease_gene_source: str = "opentargets"

    # drug side (Level 1 drug_targets)
    drug_target_id: str = Field(description="internal id, e.g. TGT:000203")
    drug_target_name: str | None = None
    drug_target_uniprot_id: str | None = None
    drug_action_type: str | None = None
    drug_target_source: str = "chembl"


class PathwayMatch(BaseModel):
    """A Reactome pathway shared by the disease (Level 2) and the drug (Level 3)."""

    reactome_id: str = Field(description="the shared Reactome stable id, e.g. R-HSA-1257604")
    pathway_name: str | None = None

    disease_pathway_id: str | None = Field(default=None, description="Level 2 internal PATH:… id")
    disease_pathway_source: str = "derived:opentargets+reactome"
    disease_gene_support_count: int | None = Field(
        default=None, description="disease genes supporting this pathway (Level 2)"
    )

    drug_pathway_source: str = "derived:chembl-targets+reactome"
    drug_supporting_target_count: int | None = Field(
        default=None, description="drug targets mapping into this pathway (Level 3)"
    )


class CandidateGenerationReason(BaseModel):
    """One reason a drug is in the pool. A drug may have many, across both methods."""

    method: GenerationMethod
    gene_target: GeneTargetMatch | None = None
    pathway: PathwayMatch | None = None


class CandidateDrug(BaseModel):
    """A drug that entered the candidate pool for a disease, with every reason why.

    No scoring / ranking / probability fields — by design.
    """

    drug_id: str
    drug_name: str
    disease_id: str
    disease_name: str

    methods: list[GenerationMethod] = Field(description="distinct generation methods, sorted")
    reasons: list[CandidateGenerationReason] = Field(default_factory=list)

    # convenience roll-ups over ``reasons`` (deduplicated, sorted) for Level 5
    matched_gene_hgnc_ids: list[str] = Field(default_factory=list)
    matched_gene_symbols: list[str] = Field(default_factory=list)
    matched_disease_gene_ids: list[str] = Field(default_factory=list)
    matched_drug_target_ids: list[str] = Field(default_factory=list)
    matched_pathway_reactome_ids: list[str] = Field(default_factory=list)


class CandidateGenerationProvenance(BaseModel):
    gene_target_bridge: str
    gene_target_bridge_available: bool
    gene_target_unavailable_reason: str | None = None

    pathway_disease_source: str
    pathway_drug_source: str
    pathway_enrichment_available: bool
    pathway_unavailable_reason: str | None = None

    datasets_used: list[str]
    methods_run: list[str]
    disclaimer: str
    interpretation_note: str = (
        "A candidate is a drug with a real biological relationship to the disease "
        "that is worth downstream analysis. It is NOT a therapeutic recommendation "
        "and carries no score, probability or ranking at this level."
    )


class CandidateGenerationResult(BaseModel):
    disease_id: str
    disease_name: str
    ontology_id: str | None = None

    candidate_count: int
    candidates: list[CandidateDrug] = Field(default_factory=list)

    counts_by_method: dict[str, int] = Field(
        default_factory=dict,
        description="{'gene_target': n, 'pathway': m, 'both': k, 'universe': 1430}",
    )
    provenance: CandidateGenerationProvenance
