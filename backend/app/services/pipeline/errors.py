"""Typed errors for the Phase 11 pipeline-orchestration service."""

from __future__ import annotations


class PipelineError(Exception):
    """Base class for pipeline-orchestration failures."""


class PipelineNotRunError(PipelineError):
    """A candidate/explanation/graph was requested for a disease that has not
    had ``run_pipeline`` called for it (or whose cache entry expired) — the
    caller must run the pipeline first."""

    def __init__(self, disease_id: str) -> None:
        super().__init__(
            f"no cached pipeline run for disease {disease_id!r}; call run_pipeline() first"
        )
        self.disease_id = disease_id


class CandidateNotFoundError(PipelineError):
    """The disease was run, but no ranked candidate with this drug_id exists
    in it (unknown or not within the ranked top-N)."""

    def __init__(self, disease_id: str, drug_id: str) -> None:
        super().__init__(f"no ranked candidate {drug_id!r} for disease {disease_id!r}")
        self.disease_id = disease_id
        self.drug_id = drug_id
