"""Evidence Graph (Phase 10).

    RankedCandidate + CandidateDrug (+ optional CandidateExplanation)
        -> build_candidate_graph(...) / build_evidence_graph(...)
        -> EvidenceGraph  (nodes[] + edges[], frontend-ready)

A **pure representation layer** over evidence Levels 2-9 already computed.
It discovers no new relationship: every node/edge is built from a field that
already exists on a real pipeline object, and every biological edge keeps
that object's own provenance. No score is recalculated, no rank is
reassigned, no graph database is used — this is a plain in-memory structure.

Build for one candidate (``build_candidate_graph``), an explicit top-N
(``build_graph_for_candidates`` / ``build_graph_for_disease(top_n=...)``) —
never automatically for the whole drug universe. See ``docs/evidence-graph.md``.
"""

from app.models.graph import (
    GRAPH_SCHEMA_VERSION,
    EvidenceGraph,
    EvidenceGraphMetadata,
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from app.services.graph.build import build_candidate_graph, build_evidence_graph
from app.services.graph.errors import EvidenceGraphError, InconsistentGraphInputError
from app.services.graph.service import build_graph_for_candidates, build_graph_for_disease

__all__ = [
    "GRAPH_SCHEMA_VERSION",
    "EvidenceGraph",
    "EvidenceGraphError",
    "EvidenceGraphMetadata",
    "GraphEdge",
    "GraphEdgeType",
    "GraphNode",
    "GraphNodeType",
    "InconsistentGraphInputError",
    "build_candidate_graph",
    "build_evidence_graph",
    "build_graph_for_candidates",
    "build_graph_for_disease",
]
