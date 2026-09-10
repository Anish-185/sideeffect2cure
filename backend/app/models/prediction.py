"""Phase 6 schemas: the ML PredictionResult + interpretability payload.

A prediction is a **model output over the available dataset** — never a
probability of cure, patient response, clinical efficacy, or a treatment
recommendation. It is not a repurposing score and it is not ranked here.

Design keeps ``disease_id`` / ``drug_id`` and the matched-relationship ids so a
later phase can wire predictions into the evidence graph.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

PREDICTION_SCHEMA_VERSION = "1.0"


class FeatureContribution(BaseModel):
    """How one Level 5 feature pushed this model output, in the model's own terms."""

    feature_name: str = Field(description="an actual Level 5 feature (see preprocessing.FEATURE_COLUMNS)")
    feature_value: float
    contribution: float = Field(
        description="signed effect on the model output "
        "(log-odds term for logistic regression; probability delta for the forest)"
    )
    direction: str = Field(description="'increases' | 'decreases' | 'neutral'")


class ValidationSummary(BaseModel):
    method: str
    n_splits: int
    group_by: str
    positive_prevalence: float
    no_skill_pr_auc: float = Field(description="PR-AUC of a constant predictor = prevalence")
    roc_auc_mean: float
    roc_auc_std: float
    pr_auc_mean: float
    pr_auc_std: float
    precision_mean: float
    recall_mean: float
    f1_mean: float
    per_model: dict[str, dict[str, float]] = Field(
        default_factory=dict, description="mean metrics for every candidate model"
    )


class PredictionModelMetadata(BaseModel):
    model_name: str
    model_version: str
    prediction_schema_version: str = PREDICTION_SCHEMA_VERSION
    feature_schema_version: str
    trained_at: str
    training_source: str
    target_definition: str
    n_training_rows: int
    n_training_positive: int
    positive_prevalence: float
    n_training_diseases: int
    feature_columns: list[str]
    preprocessing: str
    imputation: str
    random_seed: int
    validation: ValidationSummary
    selection_criterion: str
    leakage_notes: str
    disclaimer: str


class PredictionResult(BaseModel):
    disease_id: str
    drug_id: str
    disease_name: str
    drug_name: str

    model_name: str
    model_version: str
    feature_schema_version: str
    prediction_schema_version: str = PREDICTION_SCHEMA_VERSION

    model_output: float = Field(description="model output in [0,1] over the available dataset")
    model_output_type: str = "predicted_probability"
    baseline_output: float = Field(description="the model's base rate (constant-feature output)")

    important_features: list[FeatureContribution] = Field(
        default_factory=list, description="top contributing Level 5 features for THIS prediction"
    )

    # ids preserved for later evidence-graph wiring (not a graph itself)
    matched_gene_hgnc_ids: list[str] = Field(default_factory=list)
    matched_drug_target_ids: list[str] = Field(default_factory=list)
    matched_pathway_reactome_ids: list[str] = Field(default_factory=list)
    generation_methods: list[str] = Field(default_factory=list)

    model_metadata: PredictionModelMetadata

    model_config = {"protected_namespaces": ()}
