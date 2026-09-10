"""Services: orchestration of the discovery pipeline stages.

Business logic lives here, kept out of the FastAPI route layer.

Level 2 provides :mod:`app.services.disease` — the Disease Resolver and
Disease Profile builder.
"""

from app.services.disease import (
    DiseaseResolver,
    build_disease_profile,
    get_disease_profile,
    resolve_disease,
)

__all__ = [
    "DiseaseResolver",
    "build_disease_profile",
    "get_disease_profile",
    "resolve_disease",
]
