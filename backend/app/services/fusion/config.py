"""Fusion configuration — all weights + normalization caps in one place.

No magic numbers are scattered through the fusion code: every tunable lives
here, is validated, and is echoed into the result's provenance.

**Prototype weighting scheme — NOT clinically validated.** Rationale:

* ``gene_target`` (0.45) — a drug that directly targets a disease-associated
  gene is the most specific single mechanistic hypothesis, so it carries the
  most weight.
* ``ml`` (0.30) — the Phase 6 model is a data-driven prior from clinical-
  development history, but it is trained on a weak positive/unlabeled target
  (see docs/ml-prediction.md), so it contributes meaningfully without
  dominating the biology.
* ``pathway`` (0.25) — sharing a Reactome pathway is the loosest link (a broad
  signalling pathway can be shared by many unrelated drugs), so it is weighted
  least.

Weights need not sum to 1: the fusion renormalizes over the components that are
actually available for a given drug.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator, model_validator

_COMPONENT_NAMES = ("gene_target", "pathway", "ml")


class FusionConfig(BaseModel):
    # -- component weights (relative; renormalized over available components) --
    gene_target_weight: float = Field(default=0.45, gt=0.0)
    pathway_weight: float = Field(default=0.25, gt=0.0)
    ml_weight: float = Field(default=0.30, gt=0.0)

    # -- normalization: saturating cap for match counts --
    gene_target_count_cap: int = Field(default=5, ge=1)
    pathway_count_cap: int = Field(default=10, ge=1)

    # -- within-family blend of (count strength, specificity), must sum to 1 --
    count_subweight: float = Field(default=0.5, ge=0.0, le=1.0)
    specificity_subweight: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = {"frozen": True}

    @field_validator(
        "gene_target_weight", "pathway_weight", "ml_weight",
        "count_subweight", "specificity_subweight",
    )
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):  # NaN / inf guard
            raise ValueError("weight must be a finite number")
        return v

    @model_validator(mode="after")
    def _subweights_sum_to_one(self) -> FusionConfig:
        if abs(self.count_subweight + self.specificity_subweight - 1.0) > 1e-9:
            raise ValueError("count_subweight + specificity_subweight must equal 1.0")
        return self

    def weight_for(self, component_name: str) -> float:
        return {
            "gene_target": self.gene_target_weight,
            "pathway": self.pathway_weight,
            "ml": self.ml_weight,
        }[component_name]

    def as_weight_map(self) -> dict[str, float]:
        return {name: self.weight_for(name) for name in _COMPONENT_NAMES}


DEFAULT_CONFIG = FusionConfig()
