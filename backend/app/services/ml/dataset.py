"""Assemble the Phase 6 training dataset.

For every ingested disease:  DiseaseProfile -> Level 4 candidates -> Level 5
feature vectors -> Level 6 preprocessing -> matrix rows, each labelled with the
Open Targets clinical-candidate target (:mod:`app.services.ml.labels`).

Nothing biological is recomputed here — Levels 2-5 are called as-is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.models.feature import FeatureVector
from app.services.candidates import default_index, generate_candidates
from app.services.candidates.repository import CandidateIndex
from app.services.disease import build_disease_profile
from app.services.disease.repository import default_repository as disease_repository
from app.services.features import build_feature_vectors
from app.services.ml.labels import known_chembl_ids
from app.services.ml.preprocessing import FEATURE_COLUMNS, to_matrix


@dataclass
class TrainingDataset:
    X: np.ndarray
    y: np.ndarray
    groups: np.ndarray  # disease_id per row (for grouped CV)
    ids: pd.DataFrame  # disease_id, drug_id, chembl_id, disease_name, drug_name
    feature_names: tuple[str, ...]
    feature_vectors: list[FeatureVector] = field(default_factory=list, repr=False)

    @property
    def n_rows(self) -> int:
        return int(self.X.shape[0])

    @property
    def n_positive(self) -> int:
        return int(self.y.sum())

    @property
    def positive_prevalence(self) -> float:
        return float(self.y.mean()) if self.n_rows else 0.0

    @property
    def n_diseases(self) -> int:
        return len(set(self.groups))


def _disease_ontology_ids(index: CandidateIndex) -> list[tuple[str, str, str]]:
    repo = disease_repository()
    return sorted(
        (r["disease_id"], r.get("ontology_id") or "", r["disease_name"])
        for r in repo._by_id.values()
        if r.get("ontology_id")
    )


def build_training_dataset(
    *,
    index: CandidateIndex | None = None,
    disease_ids: list[str] | None = None,
) -> TrainingDataset:
    idx = index or default_index()
    triples = _disease_ontology_ids(idx)
    if disease_ids is not None:
        wanted = set(disease_ids)
        triples = [t for t in triples if t[0] in wanted]

    all_vectors: list[FeatureVector] = []
    id_rows: list[dict] = []
    labels: list[int] = []
    groups: list[str] = []

    for disease_id, ontology_id, disease_name in triples:
        profile = build_disease_profile(disease_id)
        result = generate_candidates(profile, index=idx)
        if not result.candidates:
            continue
        vectors = build_feature_vectors(profile, result.candidates, index=idx)
        known = known_chembl_ids(ontology_id)
        for cand, fv in zip(result.candidates, vectors, strict=True):
            rec = idx.drug_repo.get_drug(cand.drug_id) or {}
            chembl_id = rec.get("chembl_id")
            all_vectors.append(fv)
            id_rows.append(
                {
                    "disease_id": disease_id,
                    "drug_id": cand.drug_id,
                    "chembl_id": chembl_id,
                    "disease_name": disease_name,
                    "drug_name": cand.drug_name,
                    "ontology_id": ontology_id,
                }
            )
            labels.append(int(bool(chembl_id) and chembl_id in known))
            groups.append(disease_id)

    return TrainingDataset(
        X=to_matrix(all_vectors),
        y=np.asarray(labels, dtype=np.int64),
        groups=np.asarray(groups, dtype=object),
        ids=pd.DataFrame(id_rows),
        feature_names=FEATURE_COLUMNS,
        feature_vectors=all_vectors,
    )
