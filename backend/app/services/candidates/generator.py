"""Deterministic candidate drug generation (Level 4).

    DiseaseProfile (genes + pathways)
        -> gene-target route :  disease gene  ==(HGNC id)==  drug target
        -> pathway route     :  disease Reactome pathway  ==  drug Reactome pathway
        -> UNION (dedup drugs, keep every reason)
        -> CandidateGenerationResult

No scores, no probabilities, no ranking. A drug is a candidate iff it has at
least one real biological relationship worth downstream analysis.
"""

from __future__ import annotations

from app.core.config import DISCLAIMER
from app.data.constants import Dataset
from app.models.candidate import (
    CandidateDrug,
    CandidateGenerationProvenance,
    CandidateGenerationReason,
    CandidateGenerationResult,
    GenerationMethod,
    GeneTargetMatch,
    PathwayMatch,
)
from app.models.disease import DiseaseProfile
from app.services.candidates.errors import InvalidDiseaseProfileError
from app.services.candidates.repository import CandidateIndex, default_index

_GENE_TARGET_BRIDGE = (
    "HGNC complete set: disease gene ensembl_gene_id -> hgnc_id ; "
    "drug target uniprot accession -> hgnc_id ; candidates join on hgnc_id"
)


def _require_profile(disease_profile: object) -> DiseaseProfile:
    if not isinstance(disease_profile, DiseaseProfile):
        raise InvalidDiseaseProfileError(
            f"expected a DiseaseProfile, got {type(disease_profile).__name__}"
        )
    if not disease_profile.disease_id:
        raise InvalidDiseaseProfileError("disease profile has no disease_id")
    return disease_profile


# -- gene-target route --------------------------------------------------
def _gene_target_reasons(
    profile: DiseaseProfile, index: CandidateIndex
) -> dict[str, list[CandidateGenerationReason]]:
    out: dict[str, list[CandidateGenerationReason]] = {}
    if not index.gene_target_available or index.bridge is None:
        return out

    for gene in profile.genes:
        hgnc = index.bridge.hgnc_for_ensembl(gene.ensembl_id)
        if not hgnc:
            continue
        symbol = index.bridge.symbol_for_hgnc(hgnc) or gene.gene_name
        for tgt in index.targets_for_hgnc(hgnc):
            reason = CandidateGenerationReason(
                method=GenerationMethod.GENE_TARGET,
                gene_target=GeneTargetMatch(
                    hgnc_id=hgnc,
                    gene_symbol=symbol,
                    disease_gene_id=gene.gene_id,
                    disease_gene_ensembl_id=gene.ensembl_id,
                    disease_gene_source=gene.source or "opentargets",
                    drug_target_id=tgt["target_id"],
                    drug_target_name=tgt["target_name"],
                    drug_target_uniprot_id=tgt["uniprot_id"],
                    drug_action_type=tgt["action_type"],
                    drug_target_source=tgt["source"],
                ),
            )
            out.setdefault(tgt["drug_id"], []).append(reason)
    return out


# -- pathway route ----------------------------------------------------
def _pathway_reasons(
    profile: DiseaseProfile, index: CandidateIndex
) -> dict[str, list[CandidateGenerationReason]]:
    out: dict[str, list[CandidateGenerationReason]] = {}
    if not index.pathway_available:
        return out

    for dp in profile.pathways:
        rid = dp.reactome_id
        if not rid:
            continue
        for drug_id in index.drugs_for_reactome(rid):
            meta = index.drug_pathway(drug_id, rid) or {}
            reason = CandidateGenerationReason(
                method=GenerationMethod.PATHWAY,
                pathway=PathwayMatch(
                    reactome_id=rid,
                    pathway_name=dp.pathway_name or meta.get("pathway_name"),
                    disease_pathway_id=dp.pathway_id,
                    disease_pathway_source=dp.source or "derived:opentargets+reactome",
                    disease_gene_support_count=dp.gene_support_count,
                    drug_supporting_target_count=meta.get("supporting_target_count"),
                ),
            )
            out.setdefault(drug_id, []).append(reason)
    return out


# -- assembly -------------------------------------------------------
def _assemble(
    profile: DiseaseProfile,
    index: CandidateIndex,
    by_drug: dict[str, list[CandidateGenerationReason]],
) -> list[CandidateDrug]:
    candidates: list[CandidateDrug] = []
    for drug_id, reasons in by_drug.items():
        methods = sorted({r.method for r in reasons}, key=lambda m: m.value)
        gt = [r.gene_target for r in reasons if r.gene_target]
        pw = [r.pathway for r in reasons if r.pathway]
        candidates.append(
            CandidateDrug(
                drug_id=drug_id,
                drug_name=index.drug_name(drug_id),
                disease_id=profile.disease_id,
                disease_name=profile.disease_name,
                methods=methods,
                reasons=reasons,
                matched_gene_hgnc_ids=_uniq(m.hgnc_id for m in gt),
                matched_gene_symbols=_uniq(m.gene_symbol for m in gt if m.gene_symbol),
                matched_disease_gene_ids=_uniq(m.disease_gene_id for m in gt),
                matched_drug_target_ids=_uniq(m.drug_target_id for m in gt),
                matched_pathway_reactome_ids=_uniq(m.reactome_id for m in pw),
            )
        )
    candidates.sort(key=lambda c: (c.drug_name, c.drug_id))
    return candidates


def _uniq(it) -> list[str]:
    return sorted(dict.fromkeys(x for x in it if x))


def _provenance(index: CandidateIndex, methods_run: list[str]) -> CandidateGenerationProvenance:
    return CandidateGenerationProvenance(
        gene_target_bridge=_GENE_TARGET_BRIDGE,
        gene_target_bridge_available=index.gene_target_available,
        gene_target_unavailable_reason=index.gene_target_unavailable_reason,
        pathway_disease_source="derived:opentargets+reactome (Level 2 disease_pathways)",
        pathway_drug_source="derived:chembl-targets+reactome (Level 3 Reactome enrichment)",
        pathway_enrichment_available=index.pathway_available,
        pathway_unavailable_reason=index.pathway_unavailable_reason,
        datasets_used=[
            Dataset.DISEASE_GENES.value,
            Dataset.DISEASE_PATHWAYS.value,
            Dataset.DRUG_TARGETS.value,
            "hgnc_complete_set",
            "reactome UniProt2Reactome",
        ],
        methods_run=methods_run,
        disclaimer=DISCLAIMER,
    )


# -- public API ----------------------------------------------------
def generate_candidates_by_gene_target(
    disease_profile: DiseaseProfile, *, index: CandidateIndex | None = None
) -> list[CandidateDrug]:
    """Candidates from disease gene == drug target (HGNC id) only."""
    profile = _require_profile(disease_profile)
    idx = index or default_index()
    return _assemble(profile, idx, _gene_target_reasons(profile, idx))


def generate_candidates_by_pathway(
    disease_profile: DiseaseProfile, *, index: CandidateIndex | None = None
) -> list[CandidateDrug]:
    """Candidates from shared disease/drug Reactome pathway only."""
    profile = _require_profile(disease_profile)
    idx = index or default_index()
    return _assemble(profile, idx, _pathway_reasons(profile, idx))


def generate_candidates(
    disease_profile: DiseaseProfile, *, index: CandidateIndex | None = None
) -> CandidateGenerationResult:
    profile = _require_profile(disease_profile)
    idx = index or default_index()

    gt = _gene_target_reasons(profile, idx)
    pw = _pathway_reasons(profile, idx)

    by_drug: dict[str, list[CandidateGenerationReason]] = {}
    for source in (gt, pw):
        for drug_id, reasons in source.items():
            by_drug.setdefault(drug_id, []).extend(reasons)

    candidates = _assemble(profile, idx, by_drug)

    gt_only = set(gt) - set(pw)
    pw_only = set(pw) - set(gt)
    both = set(gt) & set(pw)
    methods_run = []
    if idx.gene_target_available:
        methods_run.append(GenerationMethod.GENE_TARGET.value)
    if idx.pathway_available:
        methods_run.append(GenerationMethod.PATHWAY.value)

    return CandidateGenerationResult(
        disease_id=profile.disease_id,
        disease_name=profile.disease_name,
        ontology_id=profile.ontology_id,
        candidate_count=len(candidates),
        candidates=candidates,
        counts_by_method={
            "gene_target": len(gt),
            "pathway": len(pw),
            "gene_target_only": len(gt_only),
            "pathway_only": len(pw_only),
            "both": len(both),
            "universe": idx.universe_size,
        },
        provenance=_provenance(idx, methods_run),
    )
