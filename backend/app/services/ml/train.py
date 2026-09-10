"""Phase 6 training: cross-validate baseline models, select, fit, persist.

Models (classical, interpretable, no new dependency, no deep learning):

* ``logistic_regression`` — StandardScaler + LogisticRegression(class_weight=balanced)
* ``random_forest``       — RandomForestClassifier(class_weight=balanced)

Validation: **GroupKFold by disease_id**. A random split would leak — every
candidate of a disease shares that disease's constant features and its base
rate, so folds must hold out whole diseases and force the model to generalise
the *relationship* pattern to unseen diseases.

Selection: highest mean PR-AUC (imbalanced target), ROC-AUC as tie-breaker.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import DISCLAIMER
from app.models.feature import FEATURE_SCHEMA_VERSION
from app.models.prediction import (
    PredictionModelMetadata,
    ValidationSummary,
)
from app.services.ml.dataset import TrainingDataset
from app.services.ml.model import MODEL_VERSION, PredictionModel

RANDOM_SEED = 42
N_SPLITS = 5
_TARGET_DEFINITION = (
    "label=1 iff the candidate drug has a known clinical indication for the disease "
    "(any phase incl. approval) in Open Targets 'drugAndClinicalCandidates'; else 0. "
    "Positive/unlabeled weak supervision: 0 == 'not currently a known clinical drug', "
    "NOT 'known ineffective'. A model output is NOT clinical efficacy."
)
_LEAKAGE_NOTES = (
    "Labels come from clinical-development history (Open Targets), independent of Level 4 "
    "biology-based candidate generation and of every Level 5 feature. Validation is "
    "GroupKFold by disease_id so whole diseases are held out."
)


def _make_models() -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        class_weight="balanced", max_iter=2000, random_state=RANDOM_SEED
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                (
                    "clf",
                    RandomForestClassifier(
                        n_estimators=400,
                        max_depth=6,
                        min_samples_leaf=10,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }


def _fold_metrics(y_true, proba) -> dict[str, float]:
    pred = (proba >= 0.5).astype(int)
    out = {
        "roc_auc": float("nan"),
        "pr_auc": float("nan"),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
    }
    if len(np.unique(y_true)) == 2:
        out["roc_auc"] = roc_auc_score(y_true, proba)
        out["pr_auc"] = average_precision_score(y_true, proba)
    return out


def cross_validate(dataset: TrainingDataset) -> dict[str, dict[str, float]]:
    """Mean CV metrics per model (GroupKFold by disease)."""
    X, y, groups = dataset.X, dataset.y, dataset.groups
    n_splits = min(N_SPLITS, dataset.n_diseases)
    gkf = GroupKFold(n_splits=n_splits)
    results: dict[str, dict[str, float]] = {}

    for name, model in _make_models().items():
        fold_rows: list[dict[str, float]] = []
        for tr, te in gkf.split(X, y, groups):
            if len(np.unique(y[tr])) < 2:
                continue
            est = _clone_fit(model, X[tr], y[tr])
            proba = est.predict_proba(X[te])[:, 1]
            fold_rows.append(_fold_metrics(y[te], proba))
        agg: dict[str, float] = {}
        for key in ("roc_auc", "pr_auc", "precision", "recall", "f1"):
            vals = [r[key] for r in fold_rows if not np.isnan(r[key])]
            agg[f"{key}_mean"] = float(np.mean(vals)) if vals else float("nan")
            agg[f"{key}_std"] = float(np.std(vals)) if vals else float("nan")
        agg["n_folds"] = float(len(fold_rows))
        results[name] = agg
    return results


def _clone_fit(pipeline: Pipeline, X, y) -> Pipeline:
    from sklearn.base import clone

    est = clone(pipeline)
    est.fit(X, y)
    return est


def select_best(cv_results: dict[str, dict[str, float]]) -> str:
    def key(name: str) -> tuple[float, float]:
        r = cv_results[name]
        pr = r.get("pr_auc_mean", float("nan"))
        roc = r.get("roc_auc_mean", float("nan"))
        return (
            pr if not np.isnan(pr) else -1.0,
            roc if not np.isnan(roc) else -1.0,
        )

    return max(cv_results, key=key)


def train(dataset: TrainingDataset) -> PredictionModel:
    if dataset.n_rows == 0:
        raise ValueError("empty training dataset")
    if dataset.n_positive == 0 or dataset.n_positive == dataset.n_rows:
        raise ValueError(
            f"degenerate target: {dataset.n_positive}/{dataset.n_rows} positive — "
            "will not train a classifier on a single-class label"
        )

    cv = cross_validate(dataset)
    best_name = select_best(cv)
    pipeline = _make_models()[best_name]
    pipeline.fit(dataset.X, dataset.y)

    best = cv[best_name]
    validation = ValidationSummary(
        method="GroupKFold",
        n_splits=min(N_SPLITS, dataset.n_diseases),
        group_by="disease_id",
        positive_prevalence=dataset.positive_prevalence,
        no_skill_pr_auc=dataset.positive_prevalence,
        roc_auc_mean=best.get("roc_auc_mean", float("nan")),
        roc_auc_std=best.get("roc_auc_std", float("nan")),
        pr_auc_mean=best.get("pr_auc_mean", float("nan")),
        pr_auc_std=best.get("pr_auc_std", float("nan")),
        precision_mean=best.get("precision_mean", float("nan")),
        recall_mean=best.get("recall_mean", float("nan")),
        f1_mean=best.get("f1_mean", float("nan")),
        per_model={
            n: {k: v for k, v in r.items() if k.endswith("_mean")} for n, r in cv.items()
        },
    )
    metadata = PredictionModelMetadata(
        model_name=best_name,
        model_version=MODEL_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        trained_at=datetime.now(UTC).isoformat(),
        training_source=(
            "Levels 2-5 over all ingested diseases; labels from Open Targets "
            "disease.drugAndClinicalCandidates"
        ),
        target_definition=_TARGET_DEFINITION,
        n_training_rows=dataset.n_rows,
        n_training_positive=dataset.n_positive,
        positive_prevalence=dataset.positive_prevalence,
        n_training_diseases=dataset.n_diseases,
        feature_columns=list(dataset.feature_names),
        preprocessing="fixed FEATURE_COLUMNS; StandardScaler for logistic_regression only",
        imputation="None (zero-denominator fraction) -> 0.0 ; bool -> {0,1}",
        random_seed=RANDOM_SEED,
        validation=validation,
        selection_criterion="highest mean PR-AUC (ROC-AUC tie-break) under GroupKFold(disease_id)",
        leakage_notes=_LEAKAGE_NOTES,
        disclaimer=DISCLAIMER,
    )
    return PredictionModel(
        pipeline=pipeline,
        feature_names=tuple(dataset.feature_names),
        metadata=metadata,
        train_mean=dataset.X.mean(axis=0),
        train_std=dataset.X.std(axis=0),
    )
