"""Phase 10 schemas: the evidence graph.

A **visualization/representation layer** over evidence the pipeline
(Levels 2-9) already computed for one or more already-ranked candidates. It
never discovers, infers, or fabricates a relationship: every node and edge is
built from a field that already exists on a real pipeline object
(``CandidateDrug`` / ``EvidenceFusionResult`` / ``RankedCandidate`` /
``CandidateExplanation``), and every biological edge keeps that object's own
provenance string. No score is recalculated here, no rank is reassigned, and
no new gene / target / pathway / drug relationship is created.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

GRAPH_SCHEMA_VERSION = "1.0"

_INTERPRETATION = (
    "A visual representation of evidence Levels 2-9 already computed for the "
    "candidate(s) below. It discovers no new relationship and recalculates no "
    "score or rank."
)


class GraphNodeType(str, Enum):
    DISEASE = "disease"
    DISEASE_GENE = "disease_gene"
    DRUG = "drug"
    DRUG_TARGET = "drug_target"
    PATHWAY = "pathway"
    PREDICTION = "prediction"
    EVIDENCE_COMPONENT = "evidence_component"
    SCORE = "score"
    RANK = "rank"
    EXPLANATION = "explanation"


class GraphEdgeType(str, Enum):
    ASSOCIATED_WITH = "associated_with"  # disease -> disease_gene | pathway
    MATCHED_TO = "matched_to"  # disease_gene -> drug_target (HGNC id join)
    HAS_TARGET = "has_target"  # drug -> drug_target
    PARTICIPATES_IN = "participates_in"  # drug -> pathway
    RECEIVED = "received"  # drug -> prediction | evidence_component | score
    RANKED = "ranked"  # drug -> rank
    EXPLAINED_BY = "explained_by"  # drug -> explanation


class GraphNode(BaseModel):
    """A frontend-friendly graph node. ``metadata`` carries everything a
    future dashboard needs on click: identifiers, source, evidence type,
    score contribution — never anything not already on the source object."""

    id: str = Field(description="stable, deterministic id — see build.py's id scheme")
    type: GraphNodeType
    label: str
    metadata: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A frontend-friendly graph edge."""

    id: str
    source: str = Field(description="a GraphNode.id")
    target: str = Field(description="a GraphNode.id")
    type: GraphEdgeType
    metadata: dict = Field(default_factory=dict)
    provenance: str | None = Field(
        default=None,
        description="which pipeline level/source produced this relationship "
        "(e.g. a Level 1 dataset name, an EvidenceComponent.provenance string)",
    )


class EvidenceGraphMetadata(BaseModel):
    graph_schema_version: str = GRAPH_SCHEMA_VERSION
    n_nodes: int
    n_edges: int
    n_candidates: int = Field(description="how many ranked candidates this graph covers")
    includes_ml_evidence: bool
    includes_explanation: bool
    node_type_counts: dict[str, int] = Field(default_factory=dict)
    edge_type_counts: dict[str, int] = Field(default_factory=dict)
    disclaimer: str
    interpretation: str = _INTERPRETATION


class EvidenceGraph(BaseModel):
    """The graph for one disease and one or more (an explicit top-N of) its
    ranked candidates."""

    disease_id: str
    disease_name: str
    drug_id: str | None = Field(
        default=None, description="set iff this graph covers exactly one candidate"
    )
    drug_ids: list[str] = Field(description="every drug (candidate) represented in this graph")

    nodes: list[GraphNode]
    edges: list[GraphEdge]

    metadata: EvidenceGraphMetadata

    model_config = {"protected_namespaces": ()}

    def node(self, node_id: str) -> GraphNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def edges_from(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.source == node_id]

    def edges_to(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.target == node_id]

    def to_frontend_dict(self) -> dict:
        """``{"nodes": [...], "edges": [...]}`` shape most graph-visualization
        libraries (react-flow, cytoscape, vis-network, d3) accept directly."""
        return {
            "nodes": [n.model_dump(mode="json") for n in self.nodes],
            "edges": [e.model_dump(mode="json") for e in self.edges],
        }
