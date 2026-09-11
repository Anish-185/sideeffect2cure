"""Pipeline orchestration for the Phase 11 dashboard API.

    disease query -> run_pipeline(...) -> cached CachedRun (Levels 2-8)
        -> explain(disease_id, drug_id)        -> Phase 9 CandidateExplanation
        -> graph_for_candidate(disease_id, drug_id) -> Phase 10 EvidenceGraph

This is glue, not new science: every value returned traces to the existing
Level 2-10 services. Its only original contribution is the small in-memory
cache that lets the dashboard request one candidate's explanation/graph
without recomputing candidate generation/features/ML/fusion/ranking for the
whole disease again.
"""

from app.services.pipeline.cache import CachedRun
from app.services.pipeline.errors import CandidateNotFoundError, PipelineError, PipelineNotRunError
from app.services.pipeline.run import (
    explain,
    get_candidate,
    get_run,
    graph_for_candidate,
    ranked_result_for,
    run_pipeline,
)

__all__ = [
    "CachedRun",
    "CandidateNotFoundError",
    "PipelineError",
    "PipelineNotRunError",
    "explain",
    "get_candidate",
    "get_run",
    "graph_for_candidate",
    "ranked_result_for",
    "run_pipeline",
]
