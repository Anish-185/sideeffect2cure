"""Drug Intelligence (Level 3).

    user drug query
        -> DrugResolver.resolve(query)     -> DrugResolutionResult
        -> get_drug_profile(drug_id)       -> DrugProfile
        -> build_drug_profile(query)       -> DrugProfile   (resolve + build)

The ``DrugProfile`` is built from the Level 1 processed datasets (``drugs``,
``drug_side_effects``, ``drug_targets``, ``identifiers``) plus ONE optional
enrichment source (Reactome, for drug -> target -> pathway context). Optional
context never causes the core profile to fail.

Level 3 stops at the drug profile: no candidate generation, no drug-disease
matching, no scoring, no ML.
"""

from app.services.drug.enrichment import (
    PathwayEnrichmentUnavailable,
    get_reactome_index,
    reset_reactome_index,
)
from app.services.drug.errors import (
    DrugIntelligenceError,
    DrugResolutionError,
    UnknownDrugError,
)
from app.services.drug.profile import (
    build_drug_profile,
    get_drug_profile,
    render_summary,
    resolve_drug,
)
from app.services.drug.repository import (
    DrugRepository,
    default_repository,
    reset_default_repository,
)
from app.services.drug.resolver import DrugResolver

__all__ = [
    "DrugIntelligenceError",
    "DrugRepository",
    "DrugResolutionError",
    "DrugResolver",
    "PathwayEnrichmentUnavailable",
    "UnknownDrugError",
    "build_drug_profile",
    "default_repository",
    "get_drug_profile",
    "get_reactome_index",
    "render_summary",
    "reset_default_repository",
    "reset_reactome_index",
    "resolve_drug",
]
