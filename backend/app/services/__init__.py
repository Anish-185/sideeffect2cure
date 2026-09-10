"""Services: orchestration of the discovery pipeline stages.

Business logic lives here, kept out of the FastAPI route layer.

- Level 2: :mod:`app.services.disease` — disease resolver + disease profile.
- Level 3: :mod:`app.services.drug` — drug resolver + drug profile.
"""

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

__all__ = [
    "DiseaseResolver",
    "DrugResolver",
    "build_disease_profile",
    "build_drug_profile",
    "get_disease_profile",
    "get_drug_profile",
    "resolve_disease",
    "resolve_drug",
]
