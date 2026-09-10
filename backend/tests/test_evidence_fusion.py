"""Phase 7 — evidence fusion + repurposing score tests."""

from __future__ import annotations

import math

import pytest

from app.models.candidate import CandidateDrug, GenerationMethod
from app.models.feature import FeatureVector, FeatureVectorMetadata
from app.models.fusion import EvidenceFusionResult, FusionProvenance
from app.models.prediction import (
    PredictionModelMetadata,
    PredictionResult,
    ValidationSummary,
)
from app.services.fusion import (
    DEFAULT_CONFIG,
    FusionConfig,
    InconsistentFusionInputError,
    fuse_all,
    fuse_evidence,
)

_DID, _DRID = "DIS:000035", "DRUG:000001"


def _fv(**over) -> FeatureVector:
    base = {
        "disease_id": _DID, "drug_id": _DRID,
        "disease_name": "glioblastoma", "drug_name": "testdrug",
        "generated_by_gene_target": True, "generated_by_pathway": True,
        "generation_method_count": 2, "gene_target_reason_count": 2, "pathway_reason_count": 4,
        "disease_gene_count": 200, "disease_gene_hgnc_mapped_count": 200,
        "drug_target_count": 4, "drug_target_hgnc_mapped_count": 4,
        "matched_gene_target_count": 2, "matched_disease_gene_count": 2,
        "matched_drug_target_count": 2,
        "fraction_of_drug_targets_matching_disease_genes": 0.5,
        "fraction_of_disease_genes_targeted_by_drug": 0.01,
        "disease_pathway_count": 300, "drug_pathway_count": 20, "matched_pathway_count": 6,
        "fraction_of_drug_pathways_matching_disease_pathways": 0.3,
        "fraction_of_disease_pathways_matching_drug_pathways": 0.02,
        "side_effect_count": 120,
        "unique_target_count": 4, "inhibitor_target_count": 3, "agonist_target_count": 0,
        "antagonist_target_count": 1, "targets_with_action_type_count": 4,
        "targets_missing_action_type_count": 0,
        "target_action_type_counts": {"INHIBITOR": 3, "ANTAGONIST": 1},
        "target_type_counts": {"SINGLE PROTEIN": 4},
        "mechanism_count": 4,
        "has_sider_evidence": True, "has_chembl_target_evidence": True,
        "has_reactome_pathway_evidence": True, "has_gene_target_bridge": True,
        "disease_pathways_available": True,
        "metadata": FeatureVectorMetadata(
            drug_pathway_source="level4_index_uncapped", disclaimer="research prototype"
        ),
    }
    base.update(over)
    return FeatureVector(**base)


def _cand(**over) -> CandidateDrug:
    base = {
        "drug_id": _DRID, "drug_name": "testdrug",
        "disease_id": _DID, "disease_name": "glioblastoma",
        "methods": [GenerationMethod.GENE_TARGET, GenerationMethod.PATHWAY],
        "reasons": [],
        "matched_gene_hgnc_ids": ["HGNC:1", "HGNC:2"],
        "matched_gene_symbols": ["AAA", "BBB"],
        "matched_disease_gene_ids": ["GENE:1", "GENE:2"],
        "matched_drug_target_ids": ["TGT:1", "TGT:2"],
        "matched_pathway_reactome_ids": ["R-HSA-1", "R-HSA-2"],
    }
    base.update(over)
    return CandidateDrug(**base)


def _pred(model_output=0.8, **over) -> PredictionResult:
    md = PredictionModelMetadata(
        model_name="random_forest", model_version="1.0.0", feature_schema_version="1.0",
        trained_at="2026-01-01T00:00:00Z", training_source="test", target_definition="test target",
        n_training_rows=100, n_training_positive=12, positive_prevalence=0.12,
        n_training_diseases=10, feature_columns=["matched_gene_target_count"],
        preprocessing="p", imputation="i", random_seed=42,
        validation=ValidationSummary(
            method="GroupKFold", n_splits=5, group_by="disease_id", positive_prevalence=0.12,
            no_skill_pr_auc=0.12, roc_auc_mean=0.78, roc_auc_std=0.04, pr_auc_mean=0.37,
            pr_auc_std=0.07, precision_mean=0.28, recall_mean=0.66, f1_mean=0.39,
        ),
        selection_criterion="PR-AUC", leakage_notes="n", disclaimer="not clinical efficacy",
    )
    base = {
        "disease_id": _DID, "drug_id": _DRID, "disease_name": "glioblastoma",
        "drug_name": "testdrug", "model_name": "random_forest", "model_version": "1.0.0",
        "feature_schema_version": "1.0", "model_output": model_output, "baseline_output": 0.5,
        "important_features": [], "model_metadata": md,
    }
    base.update(over)
    return PredictionResult(**base)


# --- component calculation ------------------------------------------
def test_gene_target_evidence_calculation():
    r = fuse_evidence(_cand(), _fv(matched_gene_target_count=2,
                                   fraction_of_drug_targets_matching_disease_genes=0.5))
    gt = r.component("gene_target")
    assert gt.available and gt.value == pytest.approx(0.5 * (2 / 5) + 0.5 * 0.5)  # 0.45
    assert gt.supporting["matched_gene_target_count"] == 2
    assert "matched_gene_target_count" in gt.calculation_method


def test_gene_target_count_saturates_at_cap():
    r = fuse_evidence(_cand(), _fv(matched_gene_target_count=99,
                                   fraction_of_drug_targets_matching_disease_genes=1.0))
    assert r.component("gene_target").value == pytest.approx(1.0)  # min(99,5)/5=1 ; 0.5*1+0.5*1


def test_pathway_evidence_calculation():
    r = fuse_evidence(_cand(), _fv(matched_pathway_count=5,
                                   fraction_of_drug_pathways_matching_disease_pathways=0.4))
    pw = r.component("pathway")
    assert pw.available and pw.value == pytest.approx(0.5 * (5 / 10) + 0.5 * 0.4)  # 0.45


def test_ml_evidence_integration():
    r = fuse_evidence(_cand(), _fv(), _pred(model_output=0.83))
    ml = r.component("ml")
    assert ml.available and ml.value == pytest.approx(0.83)
    assert ml.supporting["model_output"] == 0.83
    assert ml.supporting["model_name"] == "random_forest"
    assert r.ml_model_output == 0.83 and r.ml_baseline_output == 0.5


def test_ml_unavailable_behavior():
    r = fuse_evidence(_cand(), _fv(), None)          # no PredictionResult
    ml = r.component("ml")
    assert ml.available is False and ml.value is None and ml.contribution_points is None
    assert "no Phase 6 PredictionResult" in ml.unavailable_reason
    assert r.ml_model_output is None
    # score is computed from the remaining components, weights renormalized
    assert r.weights_renormalized_over_available is True
    gt, pw = r.component("gene_target"), r.component("pathway")
    assert gt.effective_weight == pytest.approx(0.45 / 0.70)
    assert pw.effective_weight == pytest.approx(0.25 / 0.70)


# --- missing vs negative ------------------------------------------
def test_missing_pathway_evidence_is_not_negative():
    fv_full = _fv()
    fv_no_pw = _fv(has_reactome_pathway_evidence=False, drug_pathway_count=0,
                   matched_pathway_count=0,
                   fraction_of_drug_pathways_matching_disease_pathways=None)
    r_full = fuse_evidence(_cand(), fv_full, _pred())
    r_no_pw = fuse_evidence(_cand(), fv_no_pw, _pred())

    assert r_full.component("pathway").available is True
    assert r_no_pw.component("pathway").available is False
    assert r_no_pw.component("pathway").value is None            # not 0.0
    # gene-target + ml components are byte-identical between the two runs
    assert r_full.component("gene_target").value == r_no_pw.component("gene_target").value
    assert r_full.component("ml").value == r_no_pw.component("ml").value
    # score renormalized over the 2 available components (weights 0.45 + 0.30)
    assert r_no_pw.weights_renormalized_over_available is True
    assert r_no_pw.component("gene_target").effective_weight == pytest.approx(0.45 / 0.75)


def test_available_component_with_zero_value_is_kept_not_dropped():
    """gene-target assessed (bridge ran, drug has mapped targets) but 0 overlap."""
    fv = _fv(matched_gene_target_count=0, matched_disease_gene_count=0,
             matched_drug_target_count=0, fraction_of_drug_targets_matching_disease_genes=0.0,
             generated_by_gene_target=False)
    r = fuse_evidence(_cand(matched_gene_hgnc_ids=[], matched_drug_target_ids=[]), fv, _pred())
    gt = r.component("gene_target")
    assert gt.available is True and gt.value == 0.0            # assessed, no support
    assert gt.contribution_points == 0.0
    assert gt.configured_weight == 0.45                       # still weighted -> pulls score down
    assert r.weights_renormalized_over_available is False     # all 3 components present


def test_no_evidence_available_gives_zero_not_nan():
    fv = _fv(has_gene_target_bridge=False, drug_target_hgnc_mapped_count=0,
             disease_gene_hgnc_mapped_count=0,
             has_reactome_pathway_evidence=False, drug_pathway_count=0,
             disease_pathways_available=False)
    r = fuse_evidence(_cand(), fv, None)
    assert r.repurposing_score == 0.0
    assert r.n_components_available == 0 and r.n_components_unavailable == 3
    assert math.isfinite(r.repurposing_score)


# --- score / bounds / determinism -------------------------------
def test_final_score_formula_matches_component_contributions():
    r = fuse_evidence(_cand(), _fv(), _pred())
    pts = sum(c.contribution_points for c in r.components if c.contribution_points is not None)
    assert r.repurposing_score == pytest.approx(pts, abs=1e-2)


def test_score_bounds_extremes():
    hi = fuse_evidence(_cand(), _fv(matched_gene_target_count=50,
                                    fraction_of_drug_targets_matching_disease_genes=1.0,
                                    matched_pathway_count=50,
                                    fraction_of_drug_pathways_matching_disease_pathways=1.0),
                       _pred(model_output=1.0))
    lo = fuse_evidence(_cand(), _fv(matched_gene_target_count=0,
                                    fraction_of_drug_targets_matching_disease_genes=0.0,
                                    matched_pathway_count=0,
                                    fraction_of_drug_pathways_matching_disease_pathways=0.0),
                       _pred(model_output=0.0))
    assert hi.repurposing_score == pytest.approx(100.0)
    assert lo.repurposing_score == pytest.approx(0.0)
    for r in (hi, lo):
        assert 0.0 <= r.repurposing_score <= 100.0


def test_out_of_range_feature_values_are_clipped():
    r = fuse_evidence(_cand(), _fv(fraction_of_drug_targets_matching_disease_genes=5.0,
                                   fraction_of_drug_pathways_matching_disease_pathways=-1.0),
                      _pred(model_output=2.0))
    assert 0.0 <= r.repurposing_score <= 100.0
    assert 0.0 <= r.component("gene_target").value <= 1.0
    assert 0.0 <= r.component("ml").value <= 1.0
    assert all(math.isfinite(c.value) for c in r.components if c.value is not None)


def test_deterministic():
    a = fuse_evidence(_cand(), _fv(), _pred())
    b = fuse_evidence(_cand(), _fv(), _pred())
    assert a.model_dump() == b.model_dump()


# --- weights / config -------------------------------------------
def test_weights_are_configurable_and_validated():
    cfg = FusionConfig(gene_target_weight=0.7, pathway_weight=0.2, ml_weight=0.1)
    r = fuse_evidence(_cand(), _fv(), _pred(), config=cfg)
    assert r.weights_configured == {"gene_target": 0.7, "pathway": 0.2, "ml": 0.1}
    assert r.component("gene_target").configured_weight == 0.7

    for bad in ({"gene_target_weight": 0.0}, {"ml_weight": -1.0},
                {"count_subweight": 0.6, "specificity_subweight": 0.6}):
        with pytest.raises(ValueError):
            FusionConfig(**bad)


def test_default_weights_do_not_let_ml_dominate():
    assert DEFAULT_CONFIG.ml_weight < DEFAULT_CONFIG.gene_target_weight
    assert DEFAULT_CONFIG.pathway_weight <= DEFAULT_CONFIG.ml_weight


# --- double counting -------------------------------------------
def test_no_double_counting_one_component_per_family():
    r = fuse_evidence(_cand(), _fv(), _pred())
    names = [c.name for c in r.components]
    assert names.count("gene_target") == 1
    assert names.count("pathway") == 1
    assert names.count("ml") == 1
    assert set(names) == {"gene_target", "pathway", "ml"}


def test_related_gene_target_features_feed_one_component_only():
    """matched_gene_target_count / fraction / generated_by flag all describe the
    same intersection -> exactly one gene_target component, its value unchanged
    when the pathway/ML families change."""
    v1 = fuse_evidence(_cand(), _fv(), _pred(model_output=0.1)).component("gene_target").value
    v2 = fuse_evidence(_cand(), _fv(matched_pathway_count=0,
                                    fraction_of_drug_pathways_matching_disease_pathways=0.0),
                       _pred(model_output=0.9)).component("gene_target").value
    assert v1 == v2


# --- side effects: descriptive, not penalizing -----------------
def test_side_effects_are_descriptive_not_scored():
    low = fuse_evidence(_cand(), _fv(side_effect_count=5), _pred())
    high = fuse_evidence(_cand(), _fv(side_effect_count=500), _pred())
    assert low.repurposing_score == high.repurposing_score          # not penalized
    assert high.side_effect_context.side_effect_count == 500
    assert "not" in high.side_effect_context.note.lower()
    # no component references side effects
    assert not any("side_effect" in str(c.supporting) for c in high.components)


# --- schema / provenance / no clinical claims -----------------
def test_result_schema_and_graph_ids():
    r = fuse_evidence(_cand(), _fv(), _pred())
    assert isinstance(r, EvidenceFusionResult)
    assert r.disease_id == _DID and r.drug_id == _DRID
    assert r.matched_gene_hgnc_ids == ["HGNC:1", "HGNC:2"]
    assert r.matched_disease_gene_ids == ["GENE:1", "GENE:2"]
    assert r.matched_drug_target_ids == ["TGT:1", "TGT:2"]
    assert r.matched_pathway_reactome_ids == ["R-HSA-1", "R-HSA-2"]
    assert r.generation_methods == ["gene_target", "pathway"]
    assert r.scoring_version == "1.0"
    assert isinstance(r.provenance, FusionProvenance)
    assert r.provenance.feature_schema_version == "1.0"
    assert r.provenance.prediction_schema_version == "1.0"


def test_provenance_documents_double_counting_and_missing_policy():
    p = fuse_evidence(_cand(), _fv(), _pred()).provenance
    assert "renormaliz" in p.missing_evidence_policy.lower()
    assert "never be treated as negative" not in p.missing_evidence_policy  # sanity of phrasing
    assert "one evidence family" in p.double_counting_policy.lower()
    assert "prototype" in p.weight_scheme.lower()
    assert "not clinically validated" in p.weight_scheme.lower()


def test_no_clinical_or_ranking_fields():
    forbidden = {"clinical_efficacy", "efficacy", "treatment_probability", "cure",
                 "recommendation", "rank", "ranking", "top_n", "response_probability",
                 "success_probability", "safe", "safety_score"}
    for model in (EvidenceFusionResult, FusionProvenance):
        assert not (set(model.model_fields) & forbidden), model.__name__
    r = fuse_evidence(_cand(), _fv(), _pred())
    text = (r.interpretation + " " + r.provenance.disclaimer).lower()
    assert "not clinical efficacy" in text
    assert "not" in text and "recommendation" in text


def test_inconsistent_inputs_raise():
    with pytest.raises(InconsistentFusionInputError):
        fuse_evidence(_cand(drug_id="DRUG:999"), _fv())
    with pytest.raises(InconsistentFusionInputError):
        fuse_evidence(_cand(), _fv(), _pred(disease_id="DIS:999"))
    with pytest.raises(InconsistentFusionInputError):
        fuse_evidence("not a candidate", _fv())


def test_fuse_all_preserves_order_and_does_not_rank():
    cands = [_cand(drug_id="DRUG:A", matched_gene_hgnc_ids=[]),
             _cand(drug_id="DRUG:B")]
    fvs = [_fv(drug_id="DRUG:A", matched_gene_target_count=0,
              fraction_of_drug_targets_matching_disease_genes=0.0),
           _fv(drug_id="DRUG:B", matched_gene_target_count=5,
               fraction_of_drug_targets_matching_disease_genes=1.0)]
    out = fuse_all(cands, fvs, None)
    assert [r.drug_id for r in out] == ["DRUG:A", "DRUG:B"]      # input order, NOT by score


# --- real GBM end-to-end -------------------------------------
def test_gbm_end_to_end_fusion(real_candidate_index):
    from app.services.candidates import generate_candidates
    from app.services.disease import build_disease_profile
    from app.services.features import build_feature_vectors
    from app.services.ml import predict
    from app.services.ml.model import ModelNotTrainedError

    profile = build_disease_profile("Glioblastoma")
    res = generate_candidates(profile, index=real_candidate_index)
    vectors = build_feature_vectors(profile, res.candidates, index=real_candidate_index)
    try:
        predictions = predict(vectors, candidates=res.candidates)
    except ModelNotTrainedError:
        predictions = None

    fused = fuse_all(res.candidates, vectors, predictions)
    assert len(fused) == res.candidate_count > 0

    scores = [r.repurposing_score for r in fused]
    assert all(0.0 <= s <= 100.0 and math.isfinite(s) for s in scores)
    assert len({round(s, 2) for s in scores}) > 1                 # not constant

    for r in fused:
        assert r.disease_id == profile.disease_id                 # graph-ready
        assert r.drug_id.startswith("DRUG:")
        # component contributions reconstruct the score
        pts = sum(c.contribution_points for c in r.components if c.contribution_points is not None)
        assert r.repurposing_score == pytest.approx(pts, abs=1e-2)
        # gene-target-only candidates: pathway component value 0 or unavailable
        gm = set(r.generation_methods)
        if gm == {"gene_target"}:
            pw = r.component("pathway")
            assert (not pw.available) or pw.value == 0.0 or r.matched_pathway_reactome_ids == []

    # determinism on real data
    fused2 = fuse_all(res.candidates, vectors, predictions)
    assert [r.repurposing_score for r in fused] == [r.repurposing_score for r in fused2]


def test_fuse_for_disease_convenience(real_candidate_index):
    from app.services.fusion import fuse_for_disease

    a = fuse_for_disease("glioblastoma")
    b = fuse_for_disease("MONDO_0018177")
    assert len(a) == len(b) > 0
    assert [r.repurposing_score for r in a] == [r.repurposing_score for r in b]  # deterministic
    assert all(0.0 <= r.repurposing_score <= 100.0 for r in a)
