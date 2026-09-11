"""Phase 9 live smoke test — ONE real call to Featherless, only if a key is
locally configured. Never run in CI / by default; the deterministic fallback
is what every other test (and the rest of the app) actually depends on.

    FEATHERLESS_API_KEY=... pytest -m live tests/test_ai_explanation_live_smoke.py

If the key is not set this file is entirely skipped — it never fabricates a
"pass" and never fails the suite.
"""

from __future__ import annotations

import os

import pytest

from app.models.fusion import (
    DrugCharacterizationContext,
    EvidenceComponent,
    EvidenceFusionResult,
    FusionProvenance,
    SideEffectContext,
)
from app.services.explanation.context import build_explanation_context
from app.services.explanation.deepseek_provider import DeepSeekFeatherlessProvider
from app.services.ranking import rank_candidates

pytestmark = pytest.mark.live

_HAS_KEY = bool(os.environ.get("FEATHERLESS_API_KEY"))


def _one_candidate():
    comps = [
        EvidenceComponent(
            name="gene_target", available=True, value=0.8, configured_weight=0.45,
            effective_weight=0.6, contribution_points=36.0,
            calculation_method="m", provenance="p", supporting={"matched_gene_target_count": 3},
        ),
        EvidenceComponent(
            name="pathway", available=True, value=0.6, configured_weight=0.25,
            effective_weight=0.25, contribution_points=15.0,
            calculation_method="m", provenance="p", supporting={"matched_pathway_count": 5},
        ),
        EvidenceComponent(
            name="ml", available=True, value=0.9, configured_weight=0.30,
            effective_weight=0.3, contribution_points=27.0,
            calculation_method="m", provenance="p",
            supporting={"model_output": 0.9, "baseline_output": 0.5},
        ),
    ]
    fusion = EvidenceFusionResult(
        disease_id="DIS:000035", drug_id="DRUG:000124",
        disease_name="glioblastoma", drug_name="regorafenib",
        repurposing_score=78.0, components=comps,
        n_components_available=3, n_components_unavailable=0,
        weights_configured={"gene_target": 0.45, "pathway": 0.25, "ml": 0.30},
        weights_renormalized_over_available=False,
        side_effect_context=SideEffectContext(side_effect_count=10, has_sider_evidence=True),
        drug_characterization=DrugCharacterizationContext(
            drug_target_count=3, drug_pathway_count=20, mechanism_count=3,
        ),
        matched_gene_hgnc_ids=["HGNC:1097"], matched_disease_gene_ids=["GENE:000201"],
        matched_drug_target_ids=["TGT:000501"], matched_pathway_reactome_ids=["R-HSA-111"],
        generation_methods=["gene_target", "pathway"],
        ml_model_name="random_forest", ml_model_output=0.9, ml_baseline_output=0.5,
        provenance=FusionProvenance(normalization="n", disclaimer="not clinical efficacy"),
    )
    return rank_candidates([fusion]).candidates[0]


@pytest.mark.skipif(not _HAS_KEY, reason="FEATHERLESS_API_KEY not set locally")
def test_live_deepseek_explanation_is_grounded_and_valid():
    """One real request: send the structured context, receive a response,
    parse it, validate it, and get back a CandidateExplanation. If the key or
    model is unavailable this test is skipped, never faked."""
    candidate = _one_candidate()
    context = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider()  # reads FEATHERLESS_API_KEY from env

    explanation = provider.explain(candidate, context)  # raises on failure -> real test failure

    assert explanation.disease_id == candidate.disease_id
    assert explanation.drug_id == candidate.drug_id
    assert explanation.rank == candidate.rank
    assert explanation.repurposing_score == candidate.repurposing_score
    assert explanation.provenance.provider == "deepseek_featherless"
    assert explanation.summary.strip() != ""
