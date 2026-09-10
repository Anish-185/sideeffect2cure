"""Services: orchestration of the discovery pipeline stages.

Business logic lives here, kept out of the FastAPI route layer.

- Level 2: :mod:`app.services.disease` — disease resolver + disease profile.
- Level 3: :mod:`app.services.drug` — drug resolver + drug profile.
- Level 4: :mod:`app.services.candidates` — candidate drug generation.
- Level 5: :mod:`app.services.features` — disease-drug feature engineering.
- Phase 6: :mod:`app.services.ml` — ML prediction + interpretability.
- Phase 7: :mod:`app.services.fusion` — evidence fusion + repurposing score.
- Phase 8: :mod:`app.services.ranking` — candidate ranking.
"""

from app.services.candidates import (
    generate_candidates,
    generate_candidates_by_gene_target,
    generate_candidates_by_pathway,
)
from app.services.disease import (
    DiseaseResolver,
    build_disease_profile,
    get_disease_profile,
    resolve_disease,
)
from app.services.drug import (
    DrugResolver,
    build_drug_profile,
    get_drug_profile,
    resolve_drug,
)
from app.services.features import (
    build_feature_vector,
    build_feature_vectors,
)
from app.services.fusion import fuse_all, fuse_evidence, fuse_for_disease
from app.services.ml import predict, predict_for_disease
from app.services.ranking import rank_candidates, rank_for_disease

__all__ = [
    "DiseaseResolver",
    "DrugResolver",
    "build_disease_profile",
    "build_drug_profile",
    "build_feature_vector",
    "build_feature_vectors",
    "fuse_all",
    "fuse_evidence",
    "fuse_for_disease",
    "generate_candidates",
    "generate_candidates_by_gene_target",
    "generate_candidates_by_pathway",
    "get_disease_profile",
    "get_drug_profile",
    "predict",
    "predict_for_disease",
    "rank_candidates",
    "rank_for_disease",
    "resolve_disease",
    "resolve_drug",
]
