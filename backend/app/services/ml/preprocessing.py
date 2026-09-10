"""Feature-vector -> model-matrix preprocessing (Phase 6).

Training and inference share this module, so the column set, order and
imputation are identical in both directions.

* input  : Level 5 ``FeatureVector`` objects (never recomputed here)
* columns: a **fixed** list of the scalar Level 5 features (the variable-key
  ``target_action_type_counts`` / ``target_type_counts`` dicts are intentionally
  left out to keep the matrix fixed-width and interpretable — the explicit
  ``inhibitor_target_count`` etc. already carry the action-type signal)
* missing : a ``None`` fraction (zero denominator in Level 5) -> ``0.0``
  (biologically: "no overlap possible"); booleans -> 0/1
* output  : ``numpy.ndarray`` of float64, guaranteed finite (no NaN / inf)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.models.feature import FeatureVector

# Fixed, ordered. ``unique_target_count`` is dropped (identical to
# ``drug_target_count`` by Level 5 construction).
FEATURE_COLUMNS: tuple[str, ...] = (
    # A. candidate generation
    "generated_by_gene_target",
    "generated_by_pathway",
    "generation_method_count",
    "gene_target_reason_count",
    "pathway_reason_count",
    # B. disease-gene / drug-target overlap
    "disease_gene_count",
    "disease_gene_hgnc_mapped_count",
    "drug_target_count",
    "drug_target_hgnc_mapped_count",
    "matched_gene_target_count",
    "matched_disease_gene_count",
    "matched_drug_target_count",
    "fraction_of_drug_targets_matching_disease_genes",
    "fraction_of_disease_genes_targeted_by_drug",
    # C. pathway overlap
    "disease_pathway_count",
    "drug_pathway_count",
    "matched_pathway_count",
    "fraction_of_drug_pathways_matching_disease_pathways",
    "fraction_of_disease_pathways_matching_drug_pathways",
    # D. side effects
    "side_effect_count",
    # E. targets / action types
    "inhibitor_target_count",
    "agonist_target_count",
    "antagonist_target_count",
    "targets_with_action_type_count",
    "targets_missing_action_type_count",
    # F. drug structural
    "mechanism_count",
    # G. evidence availability
    "has_sider_evidence",
    "has_chembl_target_evidence",
    "has_reactome_pathway_evidence",
    "has_gene_target_bridge",
    "disease_pathways_available",
)

IMPUTATION = "None (zero-denominator fraction) -> 0.0 ; bool -> {0,1}"


def _row(fv: FeatureVector) -> list[float]:
    d = fv.model_dump()
    out: list[float] = []
    for col in FEATURE_COLUMNS:
        v = d.get(col)
        if v is None:
            out.append(0.0)
        elif isinstance(v, bool):
            out.append(1.0 if v else 0.0)
        else:
            out.append(float(v))
    return out


def to_matrix(feature_vectors: list[FeatureVector]) -> np.ndarray:
    """(n_samples, n_features) float64, finite-guaranteed."""
    if not feature_vectors:
        return np.zeros((0, len(FEATURE_COLUMNS)), dtype=np.float64)
    x = np.asarray([_row(fv) for fv in feature_vectors], dtype=np.float64)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    return x


def to_frame(feature_vectors: list[FeatureVector]) -> pd.DataFrame:
    """Matrix as a DataFrame with FEATURE_COLUMNS + disease_id / drug_id."""
    frame = pd.DataFrame(to_matrix(feature_vectors), columns=list(FEATURE_COLUMNS))
    frame.insert(0, "drug_id", [fv.drug_id for fv in feature_vectors])
    frame.insert(0, "disease_id", [fv.disease_id for fv in feature_vectors])
    return frame
