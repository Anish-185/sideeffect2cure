"""Build the canonical :class:`DiseaseProfile` from Level 1 processed data.

Everything here is deterministic aggregation of real rows — filtering by
``disease_id``, ordering, counting, and the mean that Level 1 already stored.
Nothing biological is invented.
"""

from __future__ import annotations

import math

import pandas as pd

from app.core.config import DISCLAIMER
from app.data.constants import (
    DATA_SNAPSHOT_NOTE,
    DISEASE_PATHWAY_MIN_GENES,
    OPENTARGETS_TARGETS_PER_DISEASE,
    Dataset,
)
from app.models.disease import (
    DiseaseMolecularProfile,
    DiseaseProfile,
    ExternalIdentifier,
    GeneAssociation,
    PathwayAssociation,
    ProfileProvenance,
    ResolutionResult,
)
from app.services.disease.errors import DiseaseResolutionError, UnknownDiseaseError
from app.services.disease.repository import DiseaseRepository, default_repository
from app.services.disease.resolver import DiseaseResolver

_TOP_N = 15


def _clean(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    return value


def _gene_rows(df: pd.DataFrame) -> list[GeneAssociation]:
    out: list[GeneAssociation] = []
    for r in df.itertuples(index=False):
        score = _clean(getattr(r, "association_score", None))
        out.append(
            GeneAssociation(
                gene_id=str(r.gene_id),
                gene_name=_clean(getattr(r, "gene_name", None)),
                ensembl_id=_clean(getattr(r, "ensembl_id", None)),
                association_score=float(score) if score is not None else None,
                source=str(_clean(getattr(r, "source", None)) or "opentargets"),
            )
        )
    return out


def _pathway_rows(df: pd.DataFrame) -> list[PathwayAssociation]:
    out: list[PathwayAssociation] = []
    for r in df.itertuples(index=False):
        support = _clean(getattr(r, "gene_support_count", None))
        score = _clean(getattr(r, "association_score", None))
        out.append(
            PathwayAssociation(
                pathway_id=str(r.pathway_id),
                pathway_name=str(r.pathway_name),
                reactome_id=_clean(getattr(r, "reactome_id", None)),
                gene_support_count=int(support) if support is not None else None,
                association_score=float(score) if score is not None else None,
                source=str(_clean(getattr(r, "source", None)) or "derived:opentargets+reactome"),
            )
        )
    return out


def _molecular_profile(
    genes: list[GeneAssociation], pathways: list[PathwayAssociation], *, truncated: bool
) -> DiseaseMolecularProfile:
    scores = [g.association_score for g in genes if g.association_score is not None]
    return DiseaseMolecularProfile(
        gene_count=len(genes),
        pathway_count=len(pathways),
        mean_gene_association_score=(round(sum(scores) / len(scores), 6) if scores else None),
        max_gene_association_score=(round(max(scores), 6) if scores else None),
        top_gene_symbols=[g.gene_name for g in genes[:_TOP_N] if g.gene_name],
        top_pathway_names=[p.pathway_name for p in pathways[:_TOP_N]],
        genes_truncated=truncated,
    )


def _provenance(disease_source: str, *, truncated: bool) -> ProfileProvenance:
    return ProfileProvenance(
        disease_source=disease_source or "opentargets",
        datasets_used=[
            Dataset.DISEASES.value,
            Dataset.DISEASE_GENES.value,
            Dataset.DISEASE_PATHWAYS.value,
            "identifiers",
        ],
        gene_source="opentargets",
        gene_score_semantics=(
            "Open Targets Platform overall association score in [0,1]. It quantifies how "
            "strongly a gene/target is *associated with* the disease across evidence types; "
            "it does NOT mean the gene causes the disease or that modulating it is "
            "therapeutically effective."
        ),
        genes_capped_per_disease=OPENTARGETS_TARGETS_PER_DISEASE,
        genes_truncated=truncated,
        pathway_source="derived:opentargets+reactome",
        pathway_derivation=(
            "DERIVED, not curated: the disease's associated genes were mapped to Reactome "
            f"pathways (Ensembl2Reactome, human); a (disease, pathway) pair is kept only when "
            f">= {DISEASE_PATHWAY_MIN_GENES} of the disease's genes fall in that pathway. "
            "'gene_support_count' is that overlap; 'association_score' is the mean Open Targets "
            "score of the supporting genes. These are candidate pathways of interest, not "
            "independent disease-pathway assertions."
        ),
        pathway_min_gene_support=DISEASE_PATHWAY_MIN_GENES,
        snapshot_note=DATA_SNAPSHOT_NOTE,
        disclaimer=DISCLAIMER,
    )


def render_summary(
    profile_row: dict,
    genes: list[GeneAssociation],
    pathways: list[PathwayAssociation],
    *,
    truncated: bool,
) -> str:
    """Deterministic plain-text summary. No LLM, no fabrication."""
    lines: list[str] = []
    name = profile_row["disease_name"]
    lines.append(f"Disease: {name}")
    lines.append(f"Internal ID: {profile_row['disease_id']}")
    if profile_row.get("ontology_id"):
        lines.append(f"Ontology ID: {profile_row['ontology_id']}")
    lines.append("")

    top_g = [g.gene_name or g.gene_id for g in genes[:10]]
    lines.append(f"Associated genes ({len(genes)}" + (", Level 1 cap reached" if truncated else "") + "):")
    lines.append("  " + ", ".join(top_g) + (" ..." if len(genes) > 10 else ""))
    lines.append("")

    top_p = [f"{p.pathway_name} (n={p.gene_support_count})" for p in pathways[:10]]
    lines.append(f"Associated pathways ({len(pathways)}, derived from disease genes x Reactome):")
    for p in top_p:
        lines.append(f"  - {p}")
    if len(pathways) > 10:
        lines.append("  ...")
    lines.append("")

    lines.append("Evidence:")
    lines.append("  - disease-gene associations: Open Targets Platform association scores")
    lines.append(
        "  - disease-pathway associations: DERIVED (Reactome gene->pathway; "
        f">= {DISEASE_PATHWAY_MIN_GENES} supporting genes), not curated"
    )
    lines.append("")
    lines.append(
        "Note: 'associated with' does not mean 'causes'. This profile is "
        "hypothesis-generating evidence, not a clinical or therapeutic claim."
    )
    return "\n".join(lines)


# -- public API ---------------------------------------------------------
def get_disease_profile(
    disease_id: str, *, repository: DiseaseRepository | None = None
) -> DiseaseProfile:
    repo = repository or default_repository()
    row = repo.get_disease(disease_id)
    if row is None:
        raise UnknownDiseaseError(disease_id)

    genes_df = repo.genes_for(row["disease_id"])
    pathways_df = repo.pathways_for(row["disease_id"])
    genes = _gene_rows(genes_df)
    pathways = _pathway_rows(pathways_df)
    truncated = len(genes) >= OPENTARGETS_TARGETS_PER_DISEASE

    external = [
        ExternalIdentifier(external_id=e["external_id"], source=e["source"], is_primary=e["is_primary"])
        for e in repo.external_identifiers_for(row["disease_id"])
    ]

    return DiseaseProfile(
        disease_id=row["disease_id"],
        disease_name=row["disease_name"],
        ontology_id=row.get("ontology_id"),
        external_identifiers=external,
        genes=genes,
        pathways=pathways,
        molecular_profile=_molecular_profile(genes, pathways, truncated=truncated),
        provenance=_provenance(row.get("source", ""), truncated=truncated),
        summary_text=render_summary(row, genes, pathways, truncated=truncated),
    )


def resolve_disease(query: str, *, repository: DiseaseRepository | None = None) -> ResolutionResult:
    return DiseaseResolver(repository or default_repository()).resolve(query)


def build_disease_profile(
    query: str, *, repository: DiseaseRepository | None = None
) -> DiseaseProfile:
    repo = repository or default_repository()
    result = resolve_disease(query, repository=repo)
    if not result.resolved or result.match is None:
        raise DiseaseResolutionError(result)
    return get_disease_profile(result.match.disease_id, repository=repo)
