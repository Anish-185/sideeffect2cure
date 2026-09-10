"""Deterministic disease-drug feature engineering (Level 5).

    CandidateDrug + DiseaseProfile + DrugProfile  ->  FeatureVector

Every feature is a count, a documented ratio, or a source-availability flag.
Nothing is trained, predicted, scored, fused or ranked. Undefined ratios are
``None`` (never NaN / inf). Uses the Level 4 HGNC bridge + Reactome index for
identifier overlap — no new data loading or identifier mapping.
"""

from __future__ import annotations

from collections import Counter

from app.core.config import DISCLAIMER
from app.models.candidate import CandidateDrug, GenerationMethod
from app.models.disease import DiseaseProfile
from app.models.drug import DrugProfile
from app.models.feature import FeatureVector, FeatureVectorMetadata
from app.services.candidates.repository import CandidateIndex, default_index
from app.services.drug.profile import get_drug_profile
from app.services.features.errors import InvalidFeatureInputError

_RATIO_DOCS = {
    "fraction_of_drug_targets_matching_disease_genes": (
        "matched_gene_target_count / drug_target_hgnc_mapped_count"
    ),
    "fraction_of_disease_genes_targeted_by_drug": (
        "matched_gene_target_count / disease_gene_hgnc_mapped_count"
    ),
    "fraction_of_drug_pathways_matching_disease_pathways": (
        "matched_pathway_count / drug_pathway_count"
    ),
    "fraction_of_disease_pathways_matching_drug_pathways": (
        "matched_pathway_count / disease_pathway_count"
    ),
}


def _ratio(numerator: int, denominator: int) -> float | None:
    """Deterministic ratio: ``None`` when the denominator is zero (never NaN/inf)."""
    if not denominator:
        return None
    return round(numerator / denominator, 6)


def _check_inputs(
    candidate: CandidateDrug, disease_profile: DiseaseProfile, drug_profile: DrugProfile
) -> None:
    if not isinstance(candidate, CandidateDrug):
        raise InvalidFeatureInputError(f"candidate must be a CandidateDrug, got {type(candidate)}")
    if not isinstance(disease_profile, DiseaseProfile):
        raise InvalidFeatureInputError("disease_profile must be a DiseaseProfile")
    if not isinstance(drug_profile, DrugProfile):
        raise InvalidFeatureInputError("drug_profile must be a DrugProfile")
    if candidate.drug_id != drug_profile.drug_id:
        raise InvalidFeatureInputError(
            f"candidate.drug_id {candidate.drug_id!r} != drug_profile.drug_id {drug_profile.drug_id!r}"
        )
    if candidate.disease_id != disease_profile.disease_id:
        raise InvalidFeatureInputError(
            f"candidate.disease_id {candidate.disease_id!r} != "
            f"disease_profile.disease_id {disease_profile.disease_id!r}"
        )


def _drug_reactome_ids(
    drug_id: str, drug_profile: DrugProfile, index: CandidateIndex | None
) -> tuple[set[str], str]:
    """Full set of Reactome ids for the drug + which source it came from."""
    if index is not None and index.pathway_available:
        meta = index.drug_pathway_meta.get(drug_id, {})
        return {rid for rid in meta if rid}, "level4_index_uncapped"
    bc = drug_profile.biological_context
    if bc.pathway_context_available:
        return {p.reactome_id for p in bc.pathways if p.reactome_id}, "drug_profile_capped_100"
    return set(), "unavailable"


def build_feature_vector(
    candidate: CandidateDrug,
    disease_profile: DiseaseProfile,
    drug_profile: DrugProfile,
    *,
    index: CandidateIndex | None = None,
) -> FeatureVector:
    _check_inputs(candidate, disease_profile, drug_profile)
    idx = index if index is not None else default_index()
    unavailable: list[str] = []

    # -- A. candidate-generation features --
    methods = set(candidate.methods)
    gene_target_reason_count = sum(1 for r in candidate.reasons if r.gene_target is not None)
    pathway_reason_count = sum(1 for r in candidate.reasons if r.pathway is not None)

    # -- B. disease-gene / drug-target overlap (HGNC id join) --
    disease_gene_count = len(disease_profile.genes)
    drug_target_count = len({t.target_id for t in drug_profile.targets})

    bridge = idx.bridge if (idx is not None and idx.gene_target_available) else None
    has_gene_target_bridge = bridge is not None
    if bridge is None:
        unavailable.append("gene_target_bridge")
        disease_gene_hgnc: dict[str, str] = {}
        target_hgnc: dict[str, str] = {}
    else:
        disease_gene_hgnc = {
            g.gene_id: h
            for g in disease_profile.genes
            if (h := bridge.hgnc_for_ensembl(g.ensembl_id))
        }
        target_hgnc = {
            t.target_id: h
            for t in drug_profile.targets
            if (h := bridge.hgnc_for_uniprot(t.uniprot_id))
        }

    disease_gene_hgnc_set = set(disease_gene_hgnc.values())
    target_hgnc_set = set(target_hgnc.values())
    shared_hgnc = disease_gene_hgnc_set & target_hgnc_set

    disease_gene_hgnc_mapped_count = len(disease_gene_hgnc_set)
    drug_target_hgnc_mapped_count = len(target_hgnc_set)
    matched_gene_target_count = len(shared_hgnc)
    matched_disease_gene_count = len(
        {gid for gid, h in disease_gene_hgnc.items() if h in shared_hgnc}
    )
    matched_drug_target_count = len(
        {tid for tid, h in target_hgnc.items() if h in shared_hgnc}
    )

    # -- C. pathway overlap (direct Reactome id intersection) --
    disease_reactome = {p.reactome_id for p in disease_profile.pathways if p.reactome_id}
    disease_pathway_count = len(disease_reactome)
    drug_reactome, drug_pathway_source = _drug_reactome_ids(candidate.drug_id, drug_profile, idx)
    drug_pathway_count = len(drug_reactome)
    matched_pathway_count = len(disease_reactome & drug_reactome)
    if drug_pathway_source == "unavailable":
        unavailable.append("reactome_pathway")

    # -- D. side effects --
    side_effect_count = len(drug_profile.side_effects)

    # -- E. targets / action types --
    action_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    missing_action = 0
    for t in drug_profile.targets:
        at = (t.action_type or "").strip().upper()
        if at:
            action_counts[at] += 1
        else:
            missing_action += 1
        tt = (t.target_type or "").strip().upper()
        if tt:
            type_counts[tt] += 1

    # -- G. evidence availability flags --
    has_sider_evidence = side_effect_count > 0
    has_chembl_target_evidence = len(drug_profile.targets) > 0
    has_reactome_pathway_evidence = (
        drug_pathway_source != "unavailable" and drug_pathway_count > 0
    )

    metadata = FeatureVectorMetadata(
        drug_pathway_source=drug_pathway_source,
        ratio_denominators=_RATIO_DOCS,
        unavailable=sorted(set(unavailable)),
        disclaimer=DISCLAIMER,
    )

    return FeatureVector(
        disease_id=disease_profile.disease_id,
        drug_id=candidate.drug_id,
        disease_name=disease_profile.disease_name,
        drug_name=candidate.drug_name,
        # A
        generated_by_gene_target=GenerationMethod.GENE_TARGET in methods,
        generated_by_pathway=GenerationMethod.PATHWAY in methods,
        generation_method_count=len(methods),
        gene_target_reason_count=gene_target_reason_count,
        pathway_reason_count=pathway_reason_count,
        # B
        disease_gene_count=disease_gene_count,
        disease_gene_hgnc_mapped_count=disease_gene_hgnc_mapped_count,
        drug_target_count=drug_target_count,
        drug_target_hgnc_mapped_count=drug_target_hgnc_mapped_count,
        matched_gene_target_count=matched_gene_target_count,
        matched_disease_gene_count=matched_disease_gene_count,
        matched_drug_target_count=matched_drug_target_count,
        fraction_of_drug_targets_matching_disease_genes=_ratio(
            matched_gene_target_count, drug_target_hgnc_mapped_count
        ),
        fraction_of_disease_genes_targeted_by_drug=_ratio(
            matched_gene_target_count, disease_gene_hgnc_mapped_count
        ),
        # C
        disease_pathway_count=disease_pathway_count,
        drug_pathway_count=drug_pathway_count,
        matched_pathway_count=matched_pathway_count,
        fraction_of_drug_pathways_matching_disease_pathways=_ratio(
            matched_pathway_count, drug_pathway_count
        ),
        fraction_of_disease_pathways_matching_drug_pathways=_ratio(
            matched_pathway_count, disease_pathway_count
        ),
        # D
        side_effect_count=side_effect_count,
        # E
        unique_target_count=drug_target_count,
        inhibitor_target_count=action_counts.get("INHIBITOR", 0),
        agonist_target_count=action_counts.get("AGONIST", 0),
        antagonist_target_count=action_counts.get("ANTAGONIST", 0),
        targets_with_action_type_count=len(drug_profile.targets) - missing_action,
        targets_missing_action_type_count=missing_action,
        target_action_type_counts=dict(sorted(action_counts.items())),
        target_type_counts=dict(sorted(type_counts.items())),
        # F
        mechanism_count=len(drug_profile.mechanisms),
        # G
        has_sider_evidence=has_sider_evidence,
        has_chembl_target_evidence=has_chembl_target_evidence,
        has_reactome_pathway_evidence=has_reactome_pathway_evidence,
        has_gene_target_bridge=has_gene_target_bridge,
        disease_pathways_available=disease_pathway_count > 0,
        metadata=metadata,
    )


# alias matching the brief's naming
build_features = build_feature_vector


def build_feature_vectors(
    disease_profile: DiseaseProfile,
    candidates: list[CandidateDrug],
    *,
    index: CandidateIndex | None = None,
    drug_profiles: dict[str, DrugProfile] | None = None,
) -> list[FeatureVector]:
    """Batch: one FeatureVector per candidate. Reuses one CandidateIndex and
    builds each DrugProfile once (pathway enrichment is taken from the index)."""
    if not isinstance(disease_profile, DiseaseProfile):
        raise InvalidFeatureInputError("disease_profile must be a DiseaseProfile")
    idx = index if index is not None else default_index()
    supplied = drug_profiles or {}

    vectors: list[FeatureVector] = []
    for cand in candidates:
        dp = supplied.get(cand.drug_id)
        if dp is None:
            dp = get_drug_profile(
                cand.drug_id, repository=idx.drug_repo, enrich_pathways=False
            )
        vectors.append(build_feature_vector(cand, disease_profile, dp, index=idx))
    return vectors


def feature_rows(vectors: list[FeatureVector]) -> list[dict]:
    """Flat id-tagged dicts, ready for a DataFrame in Level 6. No scoring columns."""
    return [
        {"disease_id": v.disease_id, "drug_id": v.drug_id, **v.to_feature_dict()}
        for v in vectors
    ]
