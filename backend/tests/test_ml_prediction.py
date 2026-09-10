"""Phase 6 — ML prediction + interpretability tests.

Unit tests use synthetic feature vectors and a synthetic training dataset with a
planted signal. Integration tests use the real Levels 2-5 pipeline + the trained
model artifact (skipped if it has not been trained).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.models.feature import FeatureVector, FeatureVectorMetadata
from app.models.prediction import PredictionModelMetadata, PredictionResult
from app.services.ml import (
    ModelNotTrainedError,
    PredictionModel,
    TrainingDataset,
    cross_validate,
    predict,
    select_best,
    train,
)
from app.services.ml.preprocessing import FEATURE_COLUMNS, to_frame, to_matrix


def _make_fv(disease_id="DIS:T", drug_id="DRUG:T", **overrides) -> FeatureVector:
    base = {
        "disease_id": disease_id, "drug_id": drug_id,
        "disease_name": "test disease", "drug_name": "test drug",
        "generated_by_gene_target": True, "generated_by_pathway": False,
        "generation_method_count": 1, "gene_target_reason_count": 1, "pathway_reason_count": 0,
        "disease_gene_count": 100, "disease_gene_hgnc_mapped_count": 100,
        "drug_target_count": 2, "drug_target_hgnc_mapped_count": 2,
        "matched_gene_target_count": 1, "matched_disease_gene_count": 1,
        "matched_drug_target_count": 1,
        "fraction_of_drug_targets_matching_disease_genes": 0.5,
        "fraction_of_disease_genes_targeted_by_drug": 0.01,
        "disease_pathway_count": 200, "drug_pathway_count": 0, "matched_pathway_count": 0,
        "fraction_of_drug_pathways_matching_disease_pathways": None,
        "fraction_of_disease_pathways_matching_drug_pathways": 0.0,
        "side_effect_count": 50,
        "unique_target_count": 2, "inhibitor_target_count": 1, "agonist_target_count": 0,
        "antagonist_target_count": 1, "targets_with_action_type_count": 2,
        "targets_missing_action_type_count": 0,
        "target_action_type_counts": {"INHIBITOR": 1, "ANTAGONIST": 1},
        "target_type_counts": {"SINGLE PROTEIN": 2},
        "mechanism_count": 2,
        "has_sider_evidence": True, "has_chembl_target_evidence": True,
        "has_reactome_pathway_evidence": False, "has_gene_target_bridge": True,
        "disease_pathways_available": True,
        "metadata": FeatureVectorMetadata(drug_pathway_source="level4_index_uncapped",
                                          disclaimer="research prototype"),
    }
    base.update(overrides)
    return FeatureVector(**base)


def _synthetic_dataset(n_diseases=8, per=40, seed=0) -> TrainingDataset:
    rng = np.random.default_rng(seed)   # fresh + seeded -> every call identical
    rows, y, groups, ids = [], [], [], []
    for d in range(n_diseases):
        for j in range(per):
            matched = int(rng.integers(0, 6))
            noise = rng.normal(0, 1)
            label = int(matched + noise > 2.5)          # planted signal
            fv = _make_fv(
                disease_id=f"DIS:{d}", drug_id=f"DRUG:{d}-{j}",
                matched_gene_target_count=matched,
                matched_disease_gene_count=matched, matched_drug_target_count=matched,
                side_effect_count=int(rng.integers(0, 300)),
            )
            rows.append(fv)
            y.append(label)
            groups.append(f"DIS:{d}")
            ids.append({"disease_id": f"DIS:{d}", "drug_id": f"DRUG:{d}-{j}",
                        "chembl_id": f"CHEMBL{d}{j}", "disease_name": "d", "drug_name": "x"})
    return TrainingDataset(
        X=to_matrix(rows), y=np.asarray(y), groups=np.asarray(groups, dtype=object),
        ids=pd.DataFrame(ids), feature_names=FEATURE_COLUMNS, feature_vectors=rows,
    )


@pytest.fixture(scope="module")
def synthetic_model() -> PredictionModel:
    return train(_synthetic_dataset())


# --- preprocessing ---------------------------------------------
def test_feature_matrix_shape_and_columns():
    fvs = [_make_fv(), _make_fv(drug_id="DRUG:T2")]
    X = to_matrix(fvs)
    assert X.shape == (2, len(FEATURE_COLUMNS))
    assert X.dtype == np.float64
    frame = to_frame(fvs)
    assert list(frame.columns[:2]) == ["disease_id", "drug_id"]
    assert list(frame.columns[2:]) == list(FEATURE_COLUMNS)


def test_preprocessing_missing_and_bool_handling():
    fv = _make_fv(
        fraction_of_drug_targets_matching_disease_genes=None,
        fraction_of_drug_pathways_matching_disease_pathways=None,
        has_reactome_pathway_evidence=False, has_gene_target_bridge=True,
    )
    frame = to_frame([fv]).iloc[0]
    assert frame["fraction_of_drug_targets_matching_disease_genes"] == 0.0   # None -> 0.0
    assert frame["fraction_of_drug_pathways_matching_disease_pathways"] == 0.0
    assert frame["has_reactome_pathway_evidence"] == 0.0                     # bool -> {0,1}
    assert frame["has_gene_target_bridge"] == 1.0


def test_matrix_is_always_finite():
    X = to_matrix([_make_fv(fraction_of_disease_genes_targeted_by_drug=None,
                            fraction_of_disease_pathways_matching_drug_pathways=None)])
    assert np.isfinite(X).all()


def test_empty_input_gives_empty_matrix():
    assert to_matrix([]).shape == (0, len(FEATURE_COLUMNS))
    assert predict([]) == []


# --- target / labels ------------------------------------------
def test_label_logic_no_fabrication(monkeypatch):
    from app.services.ml import labels

    monkeypatch.setattr(labels, "_cached_known", lambda oid: frozenset({"CHEMBL25"}))
    assert labels.label_for("CHEMBL25", "MONDO_X") == 1
    assert labels.label_for("CHEMBL999", "MONDO_X") == 0
    assert labels.label_for(None, "MONDO_X") == 0


def test_train_refuses_single_class_target():
    ds = _synthetic_dataset(n_diseases=3, per=10)
    ds.y[:] = 0
    with pytest.raises(ValueError, match="degenerate target"):
        train(ds)


# --- training / validation ----------------------------------
def test_cross_validate_reports_both_models_with_metrics():
    cv = cross_validate(_synthetic_dataset())
    assert set(cv) == {"logistic_regression", "random_forest"}
    for m in cv.values():
        for k in ("roc_auc_mean", "pr_auc_mean", "precision_mean", "recall_mean", "f1_mean"):
            assert k in m and not math.isnan(m[k])
        assert m["n_folds"] >= 2


def test_planted_signal_is_learned(synthetic_model: PredictionModel):
    # PR-AUC should beat the no-skill baseline (prevalence)
    v = synthetic_model.metadata.validation
    assert v.pr_auc_mean > v.no_skill_pr_auc
    assert v.roc_auc_mean > 0.55
    # the planted feature should be among the most important
    top = [name for name, _ in synthetic_model.global_importance()[:5]]
    assert "matched_gene_target_count" in top


def test_model_selection_criterion(synthetic_model: PredictionModel):
    cv = cross_validate(_synthetic_dataset())
    assert select_best(cv) in {"logistic_regression", "random_forest"}
    assert synthetic_model.metadata.model_name == select_best(cv)


def test_validation_uses_group_kfold_by_disease(synthetic_model: PredictionModel):
    v = synthetic_model.metadata.validation
    assert v.method == "GroupKFold" and v.group_by == "disease_id"
    assert v.n_splits >= 2


# --- prediction schema + interpretability --------------------
def test_prediction_generation_and_schema(synthetic_model: PredictionModel):
    fvs = [_make_fv(drug_id="DRUG:A", matched_gene_target_count=5),
           _make_fv(drug_id="DRUG:B", matched_gene_target_count=0)]
    results = predict(fvs, model=synthetic_model)
    assert len(results) == 2
    r = results[0]
    assert isinstance(r, PredictionResult)
    assert r.disease_id == "DIS:T" and r.drug_id == "DRUG:A"          # ids preserved
    assert 0.0 <= r.model_output <= 1.0
    assert r.model_output_type == "predicted_probability"
    assert 0.0 <= r.baseline_output <= 1.0
    assert r.model_name == synthetic_model.name
    assert isinstance(r.model_metadata, PredictionModelMetadata)
    assert r.feature_schema_version == "1.0"


def test_interpretability_refers_to_real_features(synthetic_model: PredictionModel):
    r = predict([_make_fv(matched_gene_target_count=5)], model=synthetic_model)[0]
    assert 1 <= len(r.important_features) <= 6
    for fc in r.important_features:
        assert fc.feature_name in FEATURE_COLUMNS
        assert fc.direction in {"increases", "decreases", "neutral"}
        assert math.isfinite(fc.contribution) and math.isfinite(fc.feature_value)
    # sorted by |contribution| desc
    mags = [abs(fc.contribution) for fc in r.important_features]
    assert mags == sorted(mags, reverse=True)


def test_contributions_sum_to_output_minus_baseline(synthetic_model: PredictionModel):
    X = to_matrix([_make_fv(matched_gene_target_count=4, side_effect_count=120)])
    contribs = synthetic_model.contributions(X[0])
    total = sum(c for _, _, c in contribs)
    proba = float(synthetic_model.predict_proba(X)[0])
    base = synthetic_model.baseline()
    if synthetic_model.name == "random_forest":
        assert abs(total - (proba - base)) < 1e-6           # exact tree contributions
    else:  # logistic_regression: contributions are log-odds terms
        from app.services.ml.model import _sigmoid
        assert abs(_sigmoid(math.log(base / (1 - base)) + total) - proba) < 1e-6


def test_deterministic_and_reproducible():
    ds = _synthetic_dataset()
    m1, m2 = train(ds), train(ds)
    X = to_matrix([_make_fv(matched_gene_target_count=3)])
    assert np.allclose(m1.predict_proba(X), m2.predict_proba(X))
    r1 = predict([_make_fv(matched_gene_target_count=3)], model=m1)[0]
    r2 = predict([_make_fv(matched_gene_target_count=3)], model=m1)[0]
    assert r1.model_dump() == r2.model_dump()


def test_no_nan_or_infinity_in_outputs(synthetic_model: PredictionModel):
    fvs = [_make_fv(drug_id=f"D{i}", matched_gene_target_count=i,
                    fraction_of_drug_pathways_matching_disease_pathways=None)
           for i in range(6)]
    for r in predict(fvs, model=synthetic_model):
        assert math.isfinite(r.model_output) and math.isfinite(r.baseline_output)
        for fc in r.important_features:
            assert math.isfinite(fc.contribution)


def test_no_clinical_claims_or_scoring_or_ranking(synthetic_model: PredictionModel):
    forbidden = {"repurposing_score", "score", "rank", "ranking", "efficacy",
                 "cure", "clinical_efficacy", "recommendation", "fusion",
                 "confidence", "response_probability"}
    for model in (PredictionResult, PredictionModelMetadata):
        assert not (set(model.model_fields) & forbidden), model.__name__

    r = predict([_make_fv()], model=synthetic_model)[0]
    md = r.model_metadata
    assert r.model_output_type == "predicted_probability"       # neutral wording
    assert "not" in md.disclaimer.lower()
    assert "not clinical efficacy" in md.target_definition.lower()
    # predict() keeps input order — it does not rank by model_output
    fvs = [_make_fv(drug_id="LOW", matched_gene_target_count=0),
           _make_fv(drug_id="HIGH", matched_gene_target_count=5)]
    out = predict(fvs, model=synthetic_model)
    assert [x.drug_id for x in out] == ["LOW", "HIGH"]


def test_model_not_trained_error():
    from app.services.ml.model import PredictionModel as PM

    with pytest.raises(ModelNotTrainedError):
        PM.load(path=__import__("pathlib").Path("/nonexistent/model.joblib"))


# --- real end-to-end -----------------------------------------
@pytest.fixture
def trained_model():
    try:
        return PredictionModel.load()
    except ModelNotTrainedError:
        pytest.skip("model not trained; run scripts/train_model.py")


def test_real_training_target_is_defensible(real_candidate_index):
    """Labels come from a real source and are not fabricated (not all 0 / all 1)."""
    from app.services.ml import build_training_dataset
    from app.services.ml.labels import LabelSourceUnavailable

    try:
        ds = build_training_dataset(index=real_candidate_index)
    except LabelSourceUnavailable:
        pytest.skip("Open Targets label source unavailable")
    assert ds.n_rows > 500
    assert 0 < ds.n_positive < ds.n_rows                       # both classes present
    assert 0.02 < ds.positive_prevalence < 0.5                 # sane, imbalanced
    assert ds.n_diseases >= 10


def test_gbm_end_to_end_prediction_pipeline(trained_model, real_candidate_index):
    from app.services.candidates import generate_candidates
    from app.services.disease import build_disease_profile
    from app.services.features import build_feature_vectors

    profile = build_disease_profile("Glioblastoma")
    res = generate_candidates(profile, index=real_candidate_index)
    vectors = build_feature_vectors(profile, res.candidates, index=real_candidate_index)
    results = predict(vectors, model=trained_model, candidates=res.candidates)

    assert len(results) == len(vectors) == res.candidate_count
    for r in results:
        assert r.disease_id == profile.disease_id                # graph-ready ids
        assert r.drug_id.startswith("DRUG:")
        assert 0.0 <= r.model_output <= 1.0
        assert math.isfinite(r.model_output)
        assert r.important_features and all(
            fc.feature_name in FEATURE_COLUMNS for fc in r.important_features
        )
        assert r.model_metadata.validation.pr_auc_mean >= r.model_metadata.validation.no_skill_pr_auc

    # results preserve input order (no ranking)
    assert [r.drug_id for r in results] == [v.drug_id for v in vectors]
    # predictions vary across candidates (not a constant)
    assert len({round(r.model_output, 4) for r in results}) > 1
