"""Build the canonical :class:`DrugProfile` from Level 1 processed data, plus
one optional Reactome enrichment step.

All core fields are deterministic aggregation of real rows. The optional
biological context (proteins / pathways) never causes the profile to fail.
"""

from __future__ import annotations

import math

import pandas as pd

from app.core.config import DISCLAIMER
from app.data.constants import DATA_SNAPSHOT_NOTE, Dataset
from app.models.drug import (
    DrugBiologicalContext,
    DrugProfile,
    DrugProvenance,
    DrugResolutionResult,
    DrugTargetAssociation,
    ExternalIdentifier,
    MechanismOfAction,
    PathwayContext,
    SideEffect,
)
from app.services.drug.enrichment import PathwayEnrichmentUnavailable, get_reactome_index
from app.services.drug.errors import DrugResolutionError, UnknownDrugError
from app.services.drug.repository import DrugRepository, default_repository
from app.services.drug.resolver import DrugResolver

_TARGET_COVERAGE_NOTE = (
    "Targets come from ChEMBL curated mechanism-of-action records, restricted to "
    "the SIDER-drug / ChEMBL intersection (Level 1: 548 drug-target rows across "
    "~390 drugs). This is NOT the full set of ChEMBL bioactivity targets for a "
    "drug, and a drug with no row here is not necessarily target-less."
)
_PATHWAY_DERIVATION = (
    "OPTIONAL, DERIVED: drug -> ChEMBL target -> UniProt accession -> Reactome "
    "(UniProt2Reactome.txt, human). 'supporting_target_count' is how many of the "
    "drug's targets fall in the pathway. Not a curated drug-pathway assertion."
)
_OPTIONAL_SKIPPED = {
    "pubchem": (
        "Level 1 already maps every drug to a PubChem CID and to ChEMBL via PubChem; "
        "extra chemical descriptors (SMILES/InChI/formula) have no consumer in the "
        "current pipeline, so nothing further is fetched."
    ),
    "uniprot": (
        "UniProt accessions are already carried on the ChEMBL targets (drug_targets."
        "uniprot_id); ChEMBL target names/types are sufficient for the prototype, so "
        "no live UniProt annotation calls are made."
    ),
    "opentargets": (
        "Open Targets' drug-level value is indications / known-drug disease links, "
        "which is Level 4+ (candidate generation & scoring) territory; its mechanism "
        "data duplicates ChEMBL. Not integrated here."
    ),
}


def _clean(v: object) -> object | None:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if bool(pd.isna(v)):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _s(v: object) -> str | None:
    v = _clean(v)
    return None if v is None else str(v)


def _side_effects(df: pd.DataFrame) -> list[SideEffect]:
    return [
        SideEffect(
            side_effect_id=str(r.side_effect_id),
            side_effect_name=str(r.side_effect_name),
            umls_cui=_s(getattr(r, "umls_cui", None)),
            source=_s(getattr(r, "source", None)) or "sider",
        )
        for r in df.itertuples(index=False)
    ]


def _targets(df: pd.DataFrame) -> list[DrugTargetAssociation]:
    return [
        DrugTargetAssociation(
            target_id=str(r.target_id),
            target_name=_s(getattr(r, "target_name", None)),
            target_type=_s(getattr(r, "target_type", None)),
            uniprot_id=_s(getattr(r, "uniprot_id", None)),
            action_type=_s(getattr(r, "action_type", None)),
            source=_s(getattr(r, "source", None)) or "chembl",
        )
        for r in df.itertuples(index=False)
    ]


def _mechanisms(targets: list[DrugTargetAssociation]) -> list[MechanismOfAction]:
    out: list[MechanismOfAction] = []
    for t in targets:
        action = (t.action_type or "").strip().lower()
        tgt = t.target_name or t.target_id
        if action:
            desc = f"{action} of {tgt}"
        else:
            desc = f"acts on {tgt}"
        out.append(
            MechanismOfAction(
                target_id=t.target_id,
                target_name=t.target_name,
                action_type=t.action_type,
                description=desc,
                source=t.source,
            )
        )
    # stable, de-duplicated on (target, action)
    seen: set[tuple[str, str | None]] = set()
    uniq: list[MechanismOfAction] = []
    for m in out:
        key = (m.target_id, m.action_type)
        if key not in seen:
            seen.add(key)
            uniq.append(m)
    return uniq


def _biological_context(
    targets: list[DrugTargetAssociation],
    *,
    enrich_pathways: bool = True,
    pathway_index: object | None = None,
) -> DrugBiologicalContext:
    proteins = list(dict.fromkeys(t.uniprot_id for t in targets if t.uniprot_id))
    ctx = DrugBiologicalContext(proteins=proteins)
    if not enrich_pathways:
        ctx.unavailable_reason = "pathway enrichment disabled for this call"
        return ctx
    if not proteins:
        ctx.unavailable_reason = "drug has no target with a UniProt accession"
        return ctx
    index = pathway_index
    if index is None:
        try:
            index = get_reactome_index()
        except PathwayEnrichmentUnavailable as exc:
            ctx.unavailable_reason = f"Reactome enrichment unavailable: {exc}"
            return ctx
    rows = index.pathways_for(proteins)
    ctx.pathways = [PathwayContext(**r) for r in rows]
    ctx.pathway_context_available = True
    if not rows:
        ctx.unavailable_reason = "no human Reactome pathway maps to this drug's target proteins"
    return ctx


def _provenance(context: DrugBiologicalContext) -> DrugProvenance:
    optional_used = ["reactome"] if context.pathway_context_available else []
    skipped = dict(_OPTIONAL_SKIPPED)
    if not context.pathway_context_available:
        skipped["reactome"] = context.unavailable_reason or "not available in this run"
    return DrugProvenance(
        identity_source="sider (Level 1 drugs); PubChem CID + ChEMBL id crosswalk",
        side_effect_source="sider (SIDER 4.1, MedDRA preferred terms)",
        target_source="chembl (mechanism of action)",
        mechanism_source="chembl (action_type + target_name from drug_targets)",
        target_coverage_note=_TARGET_COVERAGE_NOTE,
        pathway_source="reactome (UniProt2Reactome, human)" if optional_used else "not integrated",
        pathway_derivation=_PATHWAY_DERIVATION,
        datasets_used=[
            Dataset.DRUGS.value,
            Dataset.DRUG_SIDE_EFFECTS.value,
            Dataset.DRUG_TARGETS.value,
            "identifiers",
        ],
        optional_sources_used=optional_used,
        optional_sources_skipped=skipped,
        snapshot_note=DATA_SNAPSHOT_NOTE,
        disclaimer=DISCLAIMER,
    )


def render_summary(
    rec: dict,
    side_effects: list[SideEffect],
    targets: list[DrugTargetAssociation],
    mechanisms: list[MechanismOfAction],
    context: DrugBiologicalContext,
) -> str:
    lines = [
        f"Drug: {rec['drug_name']}",
        f"Internal ID: {rec['drug_id']}",
    ]
    if rec.get("chembl_id"):
        lines.append(f"ChEMBL ID: {rec['chembl_id']}")
    if rec.get("pubchem_cid"):
        lines.append(f"PubChem CID: {rec['pubchem_cid']}")
    lines.append("")

    lines.append(f"Side effects ({len(side_effects)}, SIDER):")
    lines.append("  " + ", ".join(s.side_effect_name for s in side_effects[:10]) + (
        " ..." if len(side_effects) > 10 else ""
    ))
    lines.append("")

    if targets:
        lines.append(f"Targets ({len(targets)}, ChEMBL mechanism of action):")
        for m in mechanisms[:10]:
            lines.append(f"  - {m.description}")
    else:
        lines.append("Targets: none in the SIDER∩ChEMBL mechanism-of-action intersection")
    lines.append("")

    if context.pathway_context_available and context.pathways:
        lines.append(f"Target pathways ({len(context.pathways)}, derived via Reactome):")
        for p in context.pathways[:8]:
            lines.append(f"  - {p.pathway_name} (targets={p.supporting_target_count})")
    else:
        lines.append("Target pathways: unavailable" + (
            f" ({context.unavailable_reason})" if context.unavailable_reason else ""
        ))
    lines.append("")

    lines.append("Provenance: SIDER -> side effects; ChEMBL -> targets/mechanisms; "
                 "Reactome -> optional target pathways.")
    lines.append(
        "Note: target and pathway annotations are mechanistic / annotation evidence "
        "only. They are not evidence of clinical benefit for any disease."
    )
    return "\n".join(lines)


# -- public API -------------------------------------------------------
def get_drug_profile(
    drug_id: str,
    *,
    repository: DrugRepository | None = None,
    enrich_pathways: bool = True,
    pathway_index: object | None = None,
) -> DrugProfile:
    repo = repository or default_repository()
    rec = repo.get_drug(drug_id)
    if rec is None:
        raise UnknownDrugError(drug_id)

    se = _side_effects(repo.side_effects_for(rec["drug_id"]))
    targets = _targets(repo.targets_for(rec["drug_id"]))
    mechanisms = _mechanisms(targets)
    context = _biological_context(
        targets, enrich_pathways=enrich_pathways, pathway_index=pathway_index
    )
    external = [
        ExternalIdentifier(external_id=e["external_id"], source=e["source"], is_primary=e["is_primary"])
        for e in repo.external_identifiers_for(rec["drug_id"])
    ]

    return DrugProfile(
        drug_id=rec["drug_id"],
        drug_name=rec["drug_name"],
        canonical_identifier=rec.get("canonical_identifier"),
        chembl_id=rec.get("chembl_id"),
        pubchem_cid=rec.get("pubchem_cid"),
        external_identifiers=external,
        side_effects=se,
        side_effect_count=len(se),
        targets=targets,
        target_count=len(targets),
        mechanisms=mechanisms,
        biological_context=context,
        provenance=_provenance(context),
        summary_text=render_summary(rec, se, targets, mechanisms, context),
    )


def resolve_drug(query: str, *, repository: DrugRepository | None = None) -> DrugResolutionResult:
    return DrugResolver(repository or default_repository()).resolve(query)


def build_drug_profile(
    query: str,
    *,
    repository: DrugRepository | None = None,
    enrich_pathways: bool = True,
    pathway_index: object | None = None,
) -> DrugProfile:
    repo = repository or default_repository()
    result = resolve_drug(query, repository=repo)
    if not result.resolved or result.match is None:
        raise DrugResolutionError(result)
    return get_drug_profile(
        result.match.drug_id,
        repository=repo,
        enrich_pathways=enrich_pathways,
        pathway_index=pathway_index,
    )
