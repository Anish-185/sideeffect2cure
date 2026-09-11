"""Deterministic, data-derived prose fragments for Phase 9.

No biological narrative is invented anywhere in this module — every sentence
is built directly from the structured evidence Phases 4-8 already computed.
Both the deterministic provider (``deterministic.py``) and the LLM-response
validator (``validate.py``) use these as the ground-truth description for
each evidence item, and as the fallback whenever the LLM's own text is
rejected.
"""

from __future__ import annotations

from app.models.explanation import BiologicalEvidenceItem, ModelEvidence
from app.models.fusion import EvidenceComponent
from app.models.ranking import RankedCandidate


def evidence_status(component: EvidenceComponent) -> str:
    if not component.available:
        return "not_assessed"
    return "supported" if (component.value or 0.0) > 0.0 else "assessed_no_support"


def gene_target_description(component: EvidenceComponent, candidate: RankedCandidate) -> str:
    if not component.available:
        return f"Gene-target evidence was unavailable ({component.unavailable_reason})."
    if (component.value or 0.0) <= 0.0:
        return "Gene-target evidence was assessed; no shared gene/target overlap was found."
    n = len(candidate.matched_gene_hgnc_ids)
    genes = ", ".join(candidate.matched_gene_hgnc_ids[:5]) or "n/a"
    pts = component.contribution_points or 0.0
    return (
        f"{n} disease-associated gene(s) matched this drug's known target(s) via HGNC id "
        f"({genes}), contributing {pts:.1f} of the {candidate.repurposing_score:.1f}-point "
        "repurposing score."
    )


def pathway_description(component: EvidenceComponent, candidate: RankedCandidate) -> str:
    if not component.available:
        return f"Pathway evidence was unavailable ({component.unavailable_reason})."
    if (component.value or 0.0) <= 0.0:
        return "Pathway evidence was assessed; no shared Reactome pathway was found."
    n = len(candidate.matched_pathway_reactome_ids)
    pts = component.contribution_points or 0.0
    return (
        f"{n} Reactome pathway(s) associated with the disease are also linked to this drug's "
        f"targets, contributing {pts:.1f} points to the repurposing score."
    )


def ml_description(component: EvidenceComponent, candidate: RankedCandidate) -> str:
    if not component.available:
        return "ML evidence was unavailable (no Phase 6 prediction for this candidate)."
    pts = component.contribution_points or 0.0
    out = component.supporting.get("model_output")
    baseline = component.supporting.get("baseline_output")
    out_str = f"{out:.2f}" if isinstance(out, (int, float)) else "n/a"
    baseline_str = f"{baseline:.2f}" if isinstance(baseline, (int, float)) else "n/a"
    return (
        f"The Phase 6 model output was {out_str} (baseline {baseline_str}), contributing "
        f"{pts:.1f} points to the repurposing score."
    )


_DESCRIBERS = {"gene_target": gene_target_description, "pathway": pathway_description}
_SUPPORTING_IDS = {
    "gene_target": lambda c: list(c.matched_gene_hgnc_ids),
    "pathway": lambda c: list(c.matched_pathway_reactome_ids),
}


def biological_evidence_items(candidate: RankedCandidate) -> list[BiologicalEvidenceItem]:
    """Deterministic evidence items for the gene-target and pathway families,
    in that order. The ML family is kept separate (``model_evidence_item``) —
    it is not "biology" produced by Levels 2-5, it is a Phase 6 model output."""
    items: list[BiologicalEvidenceItem] = []
    for name, describe in _DESCRIBERS.items():
        component = candidate.fusion.component(name)
        if component is None:
            continue
        items.append(
            BiologicalEvidenceItem(
                kind=component.name,
                status=evidence_status(component),
                value=component.value,
                contribution_points=component.contribution_points,
                supporting_ids=_SUPPORTING_IDS[name](candidate),
                description=describe(component, candidate),
            )
        )
    return items


def model_evidence_item(candidate: RankedCandidate) -> ModelEvidence:
    component = candidate.fusion.component("ml")
    if component is None:
        return ModelEvidence(status="not_assessed", description="ML evidence was not assessed.")
    top_features = component.supporting.get("top_feature_names") or []
    return ModelEvidence(
        status=evidence_status(component),
        model_name=candidate.fusion.ml_model_name,
        model_output=candidate.fusion.ml_model_output,
        baseline_output=candidate.fusion.ml_baseline_output,
        contribution_points=component.contribution_points,
        top_feature_names=[f for f in top_features if isinstance(f, str)],
        description=ml_description(component, candidate),
    )


def deterministic_summary(candidate: RankedCandidate) -> str:
    fusion = candidate.fusion
    available = [c.name for c in fusion.components if c.available]
    available_str = ", ".join(available) if available else "none available"
    return (
        f"{candidate.drug_name} was computationally prioritized at rank {candidate.rank} for "
        f"{candidate.disease_name}, with a repurposing score of "
        f"{candidate.repurposing_score:.1f}/100 based on the available evidence: "
        f"{available_str}. This score reflects the available computational and biological "
        "evidence supporting further investigation — it is not a measure of clinical "
        "efficacy or treatment probability."
    )


def deterministic_limitations(candidate: RankedCandidate) -> list[str]:
    fusion = candidate.fusion
    out = [
        f"{c.name.replace('_', ' ').title()} evidence was unavailable: {c.unavailable_reason}."
        for c in fusion.components
        if not c.available and c.unavailable_reason
    ]
    if fusion.weights_renormalized_over_available:
        out.append("Evidence weights were renormalized over the components that were available.")
    out.append(
        "The repurposing score is an internal research prioritization score for further "
        "investigation — it is not a measure of clinical efficacy, safety, or treatment "
        "probability, and this candidate has not been clinically validated for this disease."
    )
    return out
