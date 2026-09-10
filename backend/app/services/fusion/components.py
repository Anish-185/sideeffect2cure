"""Compute the independent evidence components from the Level 5 FeatureVector
(+ optional Level 6 PredictionResult).

Double-counting safeguard: each *biological relationship* maps to exactly ONE
component. The several Level 5 features that describe the same relationship
(``matched_gene_target_count`` / ``fraction_of_drug_targets_matching_disease_genes``
/ ``generated_by_gene_target`` / ...) are combined **once** into that component,
not counted as separate evidence streams.
"""

from __future__ import annotations

import math

from app.models.feature import FeatureVector
from app.models.fusion import EvidenceComponent
from app.models.prediction import PredictionResult
from app.services.fusion.config import FusionConfig


def _clip01(v: float | None) -> float:
    if v is None or not math.isfinite(v):  # None / NaN / inf
        return 0.0
    return max(0.0, min(1.0, float(v)))


def _blend(count: int, cap: int, specificity: float, cfg: FusionConfig) -> tuple[float, float]:
    count_norm = min(int(count), int(cap)) / float(cap)
    value = cfg.count_subweight * count_norm + cfg.specificity_subweight * _clip01(specificity)
    return _clip01(value), count_norm


# --- A. gene-target evidence -------------------------------------------
def gene_target_component(fv: FeatureVector, cfg: FusionConfig) -> EvidenceComponent:
    w = cfg.gene_target_weight
    method = (
        f"value = {cfg.count_subweight}*min(matched_gene_target_count, "
        f"{cfg.gene_target_count_cap})/{cfg.gene_target_count_cap} + "
        f"{cfg.specificity_subweight}*fraction_of_drug_targets_matching_disease_genes"
    )
    prov = "Level 4 gene-target route (HGNC id join) + Level 5 overlap features"

    assessable = (
        fv.has_gene_target_bridge
        and fv.drug_target_hgnc_mapped_count >= 1
        and fv.disease_gene_hgnc_mapped_count >= 1
    )
    if not assessable:
        reason = (
            "HGNC bridge unavailable"
            if not fv.has_gene_target_bridge
            else "drug has no HGNC-mapped target"
            if fv.drug_target_hgnc_mapped_count < 1
            else "disease has no HGNC-mapped gene"
        )
        return EvidenceComponent(
            name="gene_target", available=False, configured_weight=w,
            calculation_method=method, provenance=prov, unavailable_reason=reason,
            supporting={
                "has_gene_target_bridge": fv.has_gene_target_bridge,
                "drug_target_hgnc_mapped_count": fv.drug_target_hgnc_mapped_count,
                "disease_gene_hgnc_mapped_count": fv.disease_gene_hgnc_mapped_count,
            },
        )

    specificity = fv.fraction_of_drug_targets_matching_disease_genes
    value, count_norm = _blend(
        fv.matched_gene_target_count, cfg.gene_target_count_cap, specificity, cfg
    )
    return EvidenceComponent(
        name="gene_target", available=True, value=round(value, 6), configured_weight=w,
        calculation_method=method, provenance=prov,
        supporting={
            "matched_gene_target_count": fv.matched_gene_target_count,
            "matched_disease_gene_count": fv.matched_disease_gene_count,
            "matched_drug_target_count": fv.matched_drug_target_count,
            "count_norm": round(count_norm, 6),
            "fraction_of_drug_targets_matching_disease_genes": specificity,
            "fraction_of_disease_genes_targeted_by_drug": fv.fraction_of_disease_genes_targeted_by_drug,
            "generated_by_gene_target": fv.generated_by_gene_target,
        },
    )


# --- B. pathway evidence -----------------------------------------------
def pathway_component(fv: FeatureVector, cfg: FusionConfig) -> EvidenceComponent:
    w = cfg.pathway_weight
    method = (
        f"value = {cfg.count_subweight}*min(matched_pathway_count, "
        f"{cfg.pathway_count_cap})/{cfg.pathway_count_cap} + "
        f"{cfg.specificity_subweight}*fraction_of_drug_pathways_matching_disease_pathways"
    )
    prov = (
        "Level 2 disease pathways (derived:opentargets+reactome) ∩ Level 3 drug "
        "pathways (derived:chembl-targets+reactome) — direct Reactome id intersection"
    )

    assessable = (
        fv.has_reactome_pathway_evidence
        and fv.disease_pathways_available
        and fv.drug_pathway_count >= 1
    )
    if not assessable:
        reason = (
            "drug Reactome pathway context unavailable"
            if not fv.has_reactome_pathway_evidence or fv.drug_pathway_count < 1
            else "disease has no derived pathways"
        )
        return EvidenceComponent(
            name="pathway", available=False, configured_weight=w,
            calculation_method=method, provenance=prov, unavailable_reason=reason,
            supporting={
                "has_reactome_pathway_evidence": fv.has_reactome_pathway_evidence,
                "disease_pathways_available": fv.disease_pathways_available,
                "drug_pathway_count": fv.drug_pathway_count,
            },
        )

    specificity = fv.fraction_of_drug_pathways_matching_disease_pathways
    value, count_norm = _blend(
        fv.matched_pathway_count, cfg.pathway_count_cap, specificity, cfg
    )
    return EvidenceComponent(
        name="pathway", available=True, value=round(value, 6), configured_weight=w,
        calculation_method=method, provenance=prov,
        supporting={
            "matched_pathway_count": fv.matched_pathway_count,
            "disease_pathway_count": fv.disease_pathway_count,
            "drug_pathway_count": fv.drug_pathway_count,
            "count_norm": round(count_norm, 6),
            "fraction_of_drug_pathways_matching_disease_pathways": specificity,
            "fraction_of_disease_pathways_matching_drug_pathways": (
                fv.fraction_of_disease_pathways_matching_drug_pathways
            ),
            "generated_by_pathway": fv.generated_by_pathway,
        },
    )


# --- E. ML evidence ---------------------------------------------------
def ml_component(
    prediction: PredictionResult | None, cfg: FusionConfig
) -> EvidenceComponent:
    w = cfg.ml_weight
    method = "value = PredictionResult.model_output (already a [0,1] model output)"
    prov = "Level 6 ML prediction (GroupKFold-validated classifier over Level 5 features)"

    if prediction is None:
        return EvidenceComponent(
            name="ml", available=False, configured_weight=w,
            calculation_method=method, provenance=prov,
            unavailable_reason="no Phase 6 PredictionResult provided",
        )
    value = _clip01(prediction.model_output)
    return EvidenceComponent(
        name="ml", available=True, value=round(value, 6), configured_weight=w,
        calculation_method=method, provenance=prov,
        supporting={
            "model_output": prediction.model_output,
            "model_output_type": prediction.model_output_type,
            "baseline_output": prediction.baseline_output,
            "model_name": prediction.model_name,
            "model_version": prediction.model_version,
            "top_feature_names": [f.feature_name for f in prediction.important_features[:3]],
        },
    )
