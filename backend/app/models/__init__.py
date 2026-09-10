"""Models: Pydantic schemas for disease profiles, drug profiles, predictions and rankings.

Level 2 — disease intelligence — is in :mod:`app.models.disease`.
Level 3 — drug intelligence — is in :mod:`app.models.drug`.
Level 4 — candidate drug generation — is in :mod:`app.models.candidate`.
Level 5 — feature engineering — is in :mod:`app.models.feature`.
"""

from app.models.candidate import (
    CandidateDrug,
    CandidateGenerationProvenance,
    CandidateGenerationReason,
    CandidateGenerationResult,
    GenerationMethod,
    GeneTargetMatch,
    PathwayMatch,
)
from app.models.disease import (
    DiseaseMatch,
    DiseaseMolecularProfile,
    DiseaseProfile,
    GeneAssociation,
    MatchType,
    PathwayAssociation,
    ProfileProvenance,
    ResolutionResult,
    ResolutionStatus,
)
from app.models.drug import (
    DrugBiologicalContext,
    DrugMatch,
    DrugMatchType,
    DrugProfile,
    DrugProvenance,
    DrugResolutionResult,
    DrugResolutionStatus,
    DrugTargetAssociation,
    MechanismOfAction,
    PathwayContext,
    SideEffect,
)
from app.models.feature import (
    FEATURE_SCHEMA_VERSION,
    FeatureVector,
    FeatureVectorMetadata,
)
from app.models.prediction import (
    PREDICTION_SCHEMA_VERSION,
    FeatureContribution,
    PredictionModelMetadata,
    PredictionResult,
    ValidationSummary,
)

__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "PREDICTION_SCHEMA_VERSION",
    "CandidateDrug",
    "CandidateGenerationProvenance",
    "CandidateGenerationReason",
    "CandidateGenerationResult",
    "DiseaseMatch",
    "DiseaseMolecularProfile",
    "DiseaseProfile",
    "DrugBiologicalContext",
    "DrugMatch",
    "DrugMatchType",
    "DrugProfile",
    "DrugProvenance",
    "DrugResolutionResult",
    "DrugResolutionStatus",
    "DrugTargetAssociation",
    "FeatureContribution",
    "FeatureVector",
    "FeatureVectorMetadata",
    "GeneAssociation",
    "GeneTargetMatch",
    "GenerationMethod",
    "MatchType",
    "MechanismOfAction",
    "PathwayAssociation",
    "PathwayContext",
    "PathwayMatch",
    "PredictionModelMetadata",
    "PredictionResult",
    "ProfileProvenance",
    "ResolutionResult",
    "ResolutionStatus",
    "SideEffect",
    "ValidationSummary",
]
