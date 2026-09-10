"""Level 3 schemas: drug resolution results and the canonical drug profile.

Everything in a ``DrugProfile`` traces back to a Level 1 processed dataset or a
single explicitly-named optional enrichment source. Nothing biological is
fabricated: a field is either backed by real data or absent.

Language convention (same as Level 2): a drug *acts on* / *is associated with* a
target or pathway — this is mechanistic/annotation evidence, never a claim that
the drug treats or is effective for any disease.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DrugResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    EMPTY_QUERY = "empty_query"
    NOT_SUPPORTED = "not_supported"
    AMBIGUOUS = "ambiguous"


class DrugMatchType(str, Enum):
    INTERNAL_ID = "internal_id"
    EXTERNAL_ID = "external_id"
    EXACT_NAME = "exact_name"


class DrugMatch(BaseModel):
    drug_id: str = Field(description="internal id, e.g. DRUG:000124")
    drug_name: str = Field(description="canonical name as stored in Level 1 (lower-case)")
    chembl_id: str | None = None
    pubchem_cid: str | None = None
    matched_on: DrugMatchType
    matched_value: str


class DrugResolutionResult(BaseModel):
    """Deterministic outcome of resolving a drug query. Never guesses."""

    status: DrugResolutionStatus
    query: str
    normalized_query: str
    match: DrugMatch | None = None
    candidates: list[DrugMatch] = Field(default_factory=list, description="when status == AMBIGUOUS")
    suggestions: list[str] = Field(
        default_factory=list, description="near-name hints for NOT_SUPPORTED; never auto-selected"
    )
    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status is DrugResolutionStatus.RESOLVED


class ExternalIdentifier(BaseModel):
    external_id: str
    source: str
    is_primary: bool = False


class SideEffect(BaseModel):
    """One drug-side-effect association, straight from SIDER (``drug_side_effects``)."""

    side_effect_id: str = Field(description="internal id, e.g. SE:000001")
    side_effect_name: str
    umls_cui: str | None = Field(default=None, description="UMLS concept id from SIDER/MedDRA")
    source: str


class DrugTargetAssociation(BaseModel):
    """One drug-target relationship from the ChEMBL mechanism-of-action data."""

    target_id: str = Field(description="internal id, e.g. TGT:000619")
    target_name: str | None = None
    target_type: str | None = Field(default=None, description="e.g. SINGLE PROTEIN")
    uniprot_id: str | None = Field(default=None, description="UniProt accession (from ChEMBL)")
    action_type: str | None = Field(default=None, description="e.g. INHIBITOR, AGONIST")
    source: str


class MechanismOfAction(BaseModel):
    """Deterministic (target, action) view of a drug's mechanism.

    Derived only from ``action_type`` + ``target_name`` in ``drug_targets`` —
    the free-text ChEMBL MoA string is not in the Level 1 processed layer, so it
    is not claimed here.
    """

    target_id: str
    target_name: str | None
    action_type: str | None
    description: str = Field(description="deterministic phrase, e.g. 'inhibitor of Carbonic anhydrase 1'")
    source: str


class PathwayContext(BaseModel):
    """OPTIONAL enrichment: a Reactome pathway reached via the drug's targets.

    DERIVED: drug -> ChEMBL target -> UniProt accession -> Reactome
    (UniProt2Reactome, human). Not a curated drug-pathway assertion and not a
    pathway-enrichment statistic.
    """

    reactome_id: str
    pathway_name: str
    supporting_target_count: int = Field(description="how many of the drug's targets map here")
    supporting_uniprot_ids: list[str] = Field(default_factory=list)
    source: str = "derived:chembl-targets+reactome"


class DrugBiologicalContext(BaseModel):
    """Optional block. If enrichment is unavailable the core profile still works."""

    proteins: list[str] = Field(
        default_factory=list, description="distinct UniProt accessions from the drug's targets"
    )
    pathways: list[PathwayContext] = Field(default_factory=list)
    pathway_context_available: bool = False
    unavailable_reason: str | None = None


class DrugProvenance(BaseModel):
    identity_source: str
    side_effect_source: str
    target_source: str
    mechanism_source: str
    target_coverage_note: str
    pathway_source: str
    pathway_derivation: str
    datasets_used: list[str]
    optional_sources_used: list[str]
    optional_sources_skipped: dict[str, str]
    snapshot_note: str
    disclaimer: str


class DrugProfile(BaseModel):
    """Canonical structured representation of a resolved drug.

        Drug
        |-- identity        (id, name, external identifiers)
        |-- side effects
        |-- targets
        |-- mechanisms
        `-- biological context (optional: proteins, pathways)
    """

    drug_id: str
    drug_name: str
    canonical_identifier: str | None = None
    chembl_id: str | None = None
    pubchem_cid: str | None = None
    external_identifiers: list[ExternalIdentifier] = Field(default_factory=list)

    side_effects: list[SideEffect] = Field(default_factory=list)
    side_effect_count: int = 0

    targets: list[DrugTargetAssociation] = Field(default_factory=list)
    target_count: int = 0

    mechanisms: list[MechanismOfAction] = Field(default_factory=list)

    biological_context: DrugBiologicalContext = Field(default_factory=DrugBiologicalContext)

    provenance: DrugProvenance
    summary_text: str = Field(description="deterministic, data-derived plain-text summary")
