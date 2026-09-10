"""Feature Engineering (Level 5).

    CandidateDrug + DiseaseProfile + DrugProfile  ->  FeatureVector

Deterministic, descriptive features (counts, documented ratios, availability
flags) over a disease-drug pair. Consumed by Level 6. There is NO scoring,
probability, ranking, ML, or evidence fusion at this level.
"""

from app.services.features.builder import (
    build_feature_vector,
    build_feature_vectors,
    build_features,
    feature_rows,
)
from app.services.features.errors import (
    FeatureEngineeringError,
    InvalidFeatureInputError,
)

__all__ = [
    "FeatureEngineeringError",
    "InvalidFeatureInputError",
    "build_feature_vector",
    "build_feature_vectors",
    "build_features",
    "feature_rows",
]
