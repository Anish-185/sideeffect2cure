"""Disease Intelligence (Level 2).

    user disease query
        -> DiseaseResolver.resolve(query)      -> ResolutionResult
        -> get_disease_profile(disease_id)     -> DiseaseProfile
        -> build_disease_profile(query)        -> DiseaseProfile   (resolve + build)

The ``DiseaseProfile`` is the canonical structured disease representation used by
every downstream level. All of its content traces back to the Level 1 processed
datasets (``diseases``, ``disease_genes``, ``disease_pathways``, ``identifiers``).

Level 2 stops at the disease profile: no candidate drugs, no scoring, no ML.
"""

from app.services.disease.errors import (
    DiseaseIntelligenceError,
    DiseaseResolutionError,
    UnknownDiseaseError,
)
from app.services.disease.profile import (
    build_disease_profile,
    get_disease_profile,
    render_summary,
    resolve_disease,
)
from app.services.disease.repository import (
    DiseaseRepository,
    default_repository,
    reset_default_repository,
)
from app.services.disease.resolver import DiseaseResolver

__all__ = [
    "DiseaseIntelligenceError",
    "DiseaseRepository",
    "DiseaseResolutionError",
    "DiseaseResolver",
    "UnknownDiseaseError",
    "build_disease_profile",
    "default_repository",
    "get_disease_profile",
    "render_summary",
    "reset_default_repository",
    "resolve_disease",
]
