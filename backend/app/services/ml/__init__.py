"""ML Prediction + Interpretability (Phase 6).

    FeatureVector[]  ->  preprocessing  ->  model  ->  PredictionResult[]
                                                       + per-prediction feature contributions

Supervised, with a defensible target: whether a candidate drug has a known
clinical indication for the disease (Open Targets ``drugAndClinicalCandidates``)
— positive/unlabeled weak supervision, validated with GroupKFold by disease.

A model output is a **model prediction over the available dataset**. It is NOT a
repurposing score, NOT clinical efficacy, and nothing here ranks or fuses.
"""

from app.services.ml.dataset import TrainingDataset, build_training_dataset
from app.services.ml.labels import (
    LabelSourceUnavailable,
    fetch_known_drugs,
    known_chembl_ids,
    label_for,
)
from app.services.ml.model import (
    MODEL_VERSION,
    ModelNotTrainedError,
    PredictionModel,
    model_path,
)
from app.services.ml.predict import predict, predict_for_disease, reset_default_model
from app.services.ml.preprocessing import FEATURE_COLUMNS, to_frame, to_matrix
from app.services.ml.train import cross_validate, select_best, train

__all__ = [
    "FEATURE_COLUMNS",
    "MODEL_VERSION",
    "LabelSourceUnavailable",
    "ModelNotTrainedError",
    "PredictionModel",
    "TrainingDataset",
    "build_training_dataset",
    "cross_validate",
    "fetch_known_drugs",
    "known_chembl_ids",
    "label_for",
    "model_path",
    "predict",
    "predict_for_disease",
    "reset_default_model",
    "select_best",
    "to_frame",
    "to_matrix",
    "train",
]
