"""Candidate Drug Generation (Level 4).

    DiseaseProfile  ->  generate_candidates(profile)  ->  CandidateGenerationResult

Reduces the 1,430-drug universe to the drugs biologically connected to a
disease, via two deterministic routes that are UNION-ed:

* gene-target : a disease gene and a drug target are the same gene (HGNC id)
* pathway     : the disease and the drug share a Reactome pathway

Every candidate carries the exact relationship(s) that put it in the pool.
There is NO scoring, ranking or probability at this level — that is Level 5+.
"""

from app.services.candidates.bridge import (
    HGNCBridge,
    HGNCBridgeUnavailable,
    get_hgnc_bridge,
    reset_hgnc_bridge,
)
from app.services.candidates.errors import (
    CandidateGenerationError,
    InvalidDiseaseProfileError,
)
from app.services.candidates.generator import (
    generate_candidates,
    generate_candidates_by_gene_target,
    generate_candidates_by_pathway,
)
from app.services.candidates.repository import (
    CandidateIndex,
    default_index,
    reset_default_index,
)

__all__ = [
    "CandidateGenerationError",
    "CandidateIndex",
    "HGNCBridge",
    "HGNCBridgeUnavailable",
    "InvalidDiseaseProfileError",
    "default_index",
    "generate_candidates",
    "generate_candidates_by_gene_target",
    "generate_candidates_by_pathway",
    "get_hgnc_bridge",
    "reset_default_index",
    "reset_hgnc_bridge",
]
