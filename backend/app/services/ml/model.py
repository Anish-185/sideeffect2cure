"""The fitted prediction model + interpretability, persisted locally.

Interpretability refers ONLY to real Level 5 features — no biological narrative
is invented here (the future AI layer does language).

* logistic regression : per-prediction contribution of feature ``i`` is
  ``coef_i * (x_i - mean_i) / std_i`` (a log-odds term); they sum to
  ``logit(p) - logit(baseline)``.
* random forest : exact decision-path contributions ("treeinterpreter"
  algorithm) — for each tree, sum ``P(class 1 | child) - P(class 1 | node)``
  along the sample's path; average over trees. They sum to
  ``predict_proba - baseline`` (baseline = mean root positive rate).

No external interpretability dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.core.config import get_settings
from app.data.paths import DataPaths
from app.models.prediction import PredictionModelMetadata

MODEL_VERSION = "1.0.0"
_MODEL_FILE = "prediction_model.joblib"
_EPS = 1e-9


class ModelNotTrainedError(RuntimeError):
    pass


def model_path() -> Path:
    d = DataPaths.from_settings(get_settings()).root / "models"
    return d / _MODEL_FILE


@dataclass
class PredictionModel:
    pipeline: Pipeline
    feature_names: tuple[str, ...]
    metadata: PredictionModelMetadata
    train_mean: np.ndarray
    train_std: np.ndarray

    # -- persistence ------------------------------------------------
    def save(self, path: Path | None = None) -> Path:
        p = path or model_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "feature_names": self.feature_names,
                "metadata": self.metadata.model_dump(),
                "train_mean": self.train_mean,
                "train_std": self.train_std,
                "model_version": MODEL_VERSION,
            },
            p,
        )
        p.with_suffix(".meta.json").write_text(self.metadata.model_dump_json(indent=2))
        return p

    @classmethod
    def load(cls, path: Path | None = None) -> PredictionModel:
        p = path or model_path()
        if not p.exists():
            raise ModelNotTrainedError(
                f"{p} not found — run `python scripts/train_model.py` first"
            )
        blob = joblib.load(p)
        return cls(
            pipeline=blob["pipeline"],
            feature_names=tuple(blob["feature_names"]),
            metadata=PredictionModelMetadata.model_validate(blob["metadata"]),
            train_mean=np.asarray(blob["train_mean"], dtype=np.float64),
            train_std=np.asarray(blob["train_std"], dtype=np.float64),
        )

    # -- inference -------------------------------------------------
    @property
    def name(self) -> str:
        return self.metadata.model_name

    @property
    def _clf(self):
        return self.pipeline.named_steps["clf"]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return self.pipeline.predict_proba(X)[:, 1]

    def baseline(self) -> float:
        clf = self._clf
        if isinstance(clf, LogisticRegression):
            return float(_sigmoid(clf.intercept_[0]))
        if isinstance(clf, RandomForestClassifier):
            roots = [_pos_rate(t.tree_, 0) for t in clf.estimators_]
            return float(np.mean(roots))
        return float(self.metadata.positive_prevalence)

    def global_importance(self) -> list[tuple[str, float]]:
        clf = self._clf
        if isinstance(clf, LogisticRegression):
            vals = np.abs(clf.coef_[0])
        elif isinstance(clf, RandomForestClassifier):
            vals = clf.feature_importances_
        else:  # pragma: no cover
            vals = np.zeros(len(self.feature_names))
        order = np.argsort(vals)[::-1]
        return [(self.feature_names[i], float(vals[i])) for i in order]

    def contributions(self, x: np.ndarray) -> list[tuple[str, float, float]]:
        """(feature_name, feature_value, signed_contribution) for one sample."""
        x = np.asarray(x, dtype=np.float64).ravel()
        clf = self._clf
        if isinstance(clf, LogisticRegression):
            std = np.where(self.train_std < _EPS, 1.0, self.train_std)
            z = (x - self.train_mean) / std
            contrib = clf.coef_[0] * z
        elif isinstance(clf, RandomForestClassifier):
            contrib = _forest_contributions(clf, x)
        else:  # pragma: no cover
            contrib = np.zeros_like(x)
        return [
            (self.feature_names[i], float(x[i]), float(contrib[i]))
            for i in range(len(self.feature_names))
        ]


# --- helpers -----------------------------------------------------
def _sigmoid(v: float) -> float:
    return 1.0 / (1.0 + np.exp(-v))


def _pos_rate(tree, node: int) -> float:
    v = tree.value[node][0]
    total = v.sum()
    return float(v[1] / total) if total else 0.0


def _forest_contributions(rf: RandomForestClassifier, x: np.ndarray) -> np.ndarray:
    n_features = x.shape[0]
    total = np.zeros(n_features, dtype=np.float64)
    for est in rf.estimators_:
        tree = est.tree_
        node = 0
        while tree.children_left[node] != tree.children_right[node]:  # not a leaf
            feat = tree.feature[node]
            nxt = (
                tree.children_left[node]
                if x[feat] <= tree.threshold[node]
                else tree.children_right[node]
            )
            total[feat] += _pos_rate(tree, nxt) - _pos_rate(tree, node)
            node = nxt
    return total / len(rf.estimators_)
