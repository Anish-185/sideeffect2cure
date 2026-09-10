"""Internal schemas for the biomedical data foundation.

These Pydantic models are the contract between the ingestion layer and every
later level. Each processed table has a row model; the column order of the model
is the column order written to parquet/CSV.

Fields named ``*_id`` that are marked required hold **internal** identifiers
(e.g. ``DRUG:000123``). External identifiers are preserved either as explicit
columns (``canonical_identifier``, ``ontology_id`` ...) or in the separate
``identifiers`` mapping table.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class _Row(BaseModel):
    model_config = {"str_strip_whitespace": True, "extra": "forbid"}

    @field_validator("*", mode="before")
    @classmethod
    def _empty_string_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v == "":
            return None
        return v


# --- primary entities ------------------------------------------------------
class Drug(_Row):
    drug_id: str = Field(description="internal id, e.g. DRUG:000123")
    drug_name: str
    canonical_identifier: str | None = Field(
        default=None, description="preferred external id (PubChem CID or ChEMBL id)"
    )
    pubchem_cid: str | None = None
    chembl_id: str | None = None
    source: str


class Disease(_Row):
    disease_id: str = Field(description="internal id, e.g. DIS:000045")
    disease_name: str
    ontology_id: str | None = Field(default=None, description="EFO / MONDO id")
    source: str


# --- relationships -------------------------------------------------------
class DrugTarget(_Row):
    drug_id: str
    target_id: str = Field(description="internal id, e.g. TGT:000045")
    target_name: str | None = None
    target_type: str | None = None
    uniprot_id: str | None = None
    action_type: str | None = Field(default=None, description="e.g. INHIBITOR (ChEMBL)")
    source: str


class DrugSideEffect(_Row):
    drug_id: str
    side_effect_id: str = Field(description="internal id, e.g. SE:000045")
    side_effect_name: str
    umls_cui: str | None = Field(default=None, description="UMLS concept id from SIDER")
    source: str


class DiseaseGene(_Row):
    disease_id: str
    gene_id: str = Field(description="internal id, e.g. GENE:000045")
    gene_name: str | None = None
    ensembl_id: str | None = None
    association_score: float | None = Field(
        default=None, description="0-1 overall association score (Open Targets)"
    )
    source: str

    @field_validator("association_score")
    @classmethod
    def _score_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError(f"association_score out of [0,1]: {v}")
        return v


class DiseasePathway(_Row):
    disease_id: str
    pathway_id: str = Field(description="internal id, e.g. PATH:000045")
    pathway_name: str
    reactome_id: str | None = None
    gene_support_count: int | None = Field(
        default=None, description="disease genes mapped into this pathway"
    )
    association_score: float | None = Field(
        default=None, description="mean association score of supporting genes"
    )
    source: str


class IdentifierMapping(_Row):
    internal_id: str
    entity_type: str
    external_id: str
    external_source: str
    name: str | None = None
    is_primary: bool = False


ROW_MODELS = {
    "drugs": Drug,
    "diseases": Disease,
    "drug_targets": DrugTarget,
    "drug_side_effects": DrugSideEffect,
    "disease_genes": DiseaseGene,
    "disease_pathways": DiseasePathway,
}
