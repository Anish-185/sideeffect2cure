"""Phase 10 evidence graph construction.

    RankedCandidate + CandidateDrug (+ optional CandidateExplanation)
        -> build_candidate_graph(...) / build_evidence_graph(...)
        -> EvidenceGraph

Pure representation, deterministic, offline. Every node and edge is built
from a field that already exists on a Level 2-9 pipeline object; every
biological edge keeps that object's own provenance string. No score is
recalculated, no rank is reassigned, no new gene / target / pathway / drug
relationship is created, and no external call is made.

Node/edge ids are deterministic strings built from the underlying internal
ids (``disease_gene_id`` / ``drug_target_id`` / ``reactome_id`` / ...), so the
same evidence for two different candidates (e.g. two drugs sharing a target)
collapses to the same node instead of duplicating it.
"""

from __future__ import annotations

from app.core.config import DISCLAIMER
from app.models.candidate import CandidateDrug
from app.models.explanation import CandidateExplanation
from app.models.graph import (
    EvidenceGraph,
    EvidenceGraphMetadata,
    GraphEdge,
    GraphEdgeType,
    GraphNode,
    GraphNodeType,
)
from app.models.ranking import RankedCandidate
from app.services.graph.errors import InconsistentGraphInputError


class _GraphBuilder:
    """Accumulates nodes/edges with id-based dedup, preserving first-seen
    insertion order — which is what makes the output deterministic given a
    deterministic input order (every upstream phase is itself deterministic)."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}

    def add_node(self, node: GraphNode) -> None:
        self._nodes.setdefault(node.id, node)

    def add_edge(self, edge: GraphEdge) -> None:
        self._edges.setdefault(edge.id, edge)

    @property
    def nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[GraphEdge]:
        return list(self._edges.values())


def _disease_node_id(disease_id: str) -> str:
    return f"disease:{disease_id}"


def _drug_node_id(drug_id: str) -> str:
    return f"drug:{drug_id}"


def _disease_node(candidate: RankedCandidate) -> GraphNode:
    return GraphNode(
        id=_disease_node_id(candidate.disease_id),
        type=GraphNodeType.DISEASE,
        label=candidate.disease_name,
        metadata={"disease_id": candidate.disease_id},
    )


def _drug_node(candidate: RankedCandidate) -> GraphNode:
    return GraphNode(
        id=_drug_node_id(candidate.drug_id),
        type=GraphNodeType.DRUG,
        label=candidate.drug_name,
        metadata={
            "drug_id": candidate.drug_id,
            "generation_methods": list(candidate.generation_methods),
        },
    )


def _add_gene_target_evidence(
    builder: _GraphBuilder, disease_node_id: str, drug_node_id: str, generation_candidate: CandidateDrug
) -> None:
    """Disease -associated_with-> DiseaseGene -matched_to-> DrugTarget
    <-has_target- Drug, for every real GeneTargetMatch on the CandidateDrug
    (Level 4 — HGNC id join, already computed; nothing is inferred here)."""
    for reason in generation_candidate.reasons:
        m = reason.gene_target
        if m is None:
            continue
        gene_node_id = f"disease_gene:{m.disease_gene_id}"
        target_node_id = f"drug_target:{m.drug_target_id}"

        builder.add_node(
            GraphNode(
                id=gene_node_id,
                type=GraphNodeType.DISEASE_GENE,
                label=m.gene_symbol or m.hgnc_id,
                metadata={
                    "disease_gene_id": m.disease_gene_id,
                    "hgnc_id": m.hgnc_id,
                    "gene_symbol": m.gene_symbol,
                    "ensembl_id": m.disease_gene_ensembl_id,
                    "source": m.disease_gene_source,
                },
            )
        )
        builder.add_node(
            GraphNode(
                id=target_node_id,
                type=GraphNodeType.DRUG_TARGET,
                label=m.drug_target_name or m.hgnc_id,
                metadata={
                    "drug_target_id": m.drug_target_id,
                    "hgnc_id": m.hgnc_id,
                    "uniprot_id": m.drug_target_uniprot_id,
                    "action_type": m.drug_action_type,
                    "source": m.drug_target_source,
                },
            )
        )
        builder.add_edge(
            GraphEdge(
                id=f"{disease_node_id}->associated_with->{gene_node_id}",
                source=disease_node_id,
                target=gene_node_id,
                type=GraphEdgeType.ASSOCIATED_WITH,
                metadata={"gene_id": m.disease_gene_id, "gene_symbol": m.gene_symbol},
                provenance=m.disease_gene_source,
            )
        )
        builder.add_edge(
            GraphEdge(
                id=f"{gene_node_id}->matched_to->{target_node_id}",
                source=gene_node_id,
                target=target_node_id,
                type=GraphEdgeType.MATCHED_TO,
                metadata={"hgnc_id": m.hgnc_id, "gene_symbol": m.gene_symbol},
                provenance=(
                    "HGNC complete set: disease gene ensembl_gene_id -> hgnc_id ; "
                    "drug target uniprot -> hgnc_id ; overlap on hgnc_id (Level 4)"
                ),
            )
        )
        builder.add_edge(
            GraphEdge(
                id=f"{drug_node_id}->has_target->{target_node_id}",
                source=drug_node_id,
                target=target_node_id,
                type=GraphEdgeType.HAS_TARGET,
                metadata={"action_type": m.drug_action_type},
                provenance=m.drug_target_source,
            )
        )


def _add_pathway_evidence(
    builder: _GraphBuilder, disease_node_id: str, drug_node_id: str, generation_candidate: CandidateDrug
) -> None:
    """Disease -associated_with-> Pathway <-participates_in- Drug, for every
    real PathwayMatch on the CandidateDrug (Level 4 — direct Reactome id
    intersection).

    Level 4 records this as an aggregate (disease genes supporting the
    pathway / drug targets supporting the pathway), not a specific
    gene<->target pair within it — so, unlike gene-target evidence, no
    ``DrugTarget -belongs_to-> Pathway`` edge is created here (see
    docs/evidence-graph.md "Limitations"): that would assert a specific
    target-pathway membership the supplied evidence does not contain.
    """
    for reason in generation_candidate.reasons:
        p = reason.pathway
        if p is None:
            continue
        pathway_node_id = f"pathway:{p.reactome_id}"

        builder.add_node(
            GraphNode(
                id=pathway_node_id,
                type=GraphNodeType.PATHWAY,
                label=p.pathway_name or p.reactome_id,
                metadata={
                    "reactome_id": p.reactome_id,
                    "disease_gene_support_count": p.disease_gene_support_count,
                    "drug_supporting_target_count": p.drug_supporting_target_count,
                },
            )
        )
        builder.add_edge(
            GraphEdge(
                id=f"{disease_node_id}->associated_with->{pathway_node_id}",
                source=disease_node_id,
                target=pathway_node_id,
                type=GraphEdgeType.ASSOCIATED_WITH,
                metadata={"gene_support_count": p.disease_gene_support_count},
                provenance=p.disease_pathway_source,
            )
        )
        builder.add_edge(
            GraphEdge(
                id=f"{drug_node_id}->participates_in->{pathway_node_id}",
                source=drug_node_id,
                target=pathway_node_id,
                type=GraphEdgeType.PARTICIPATES_IN,
                metadata={"supporting_target_count": p.drug_supporting_target_count},
                provenance=p.drug_pathway_source,
            )
        )


def _add_prediction_and_evidence(builder: _GraphBuilder, drug_node_id: str, candidate: RankedCandidate) -> None:
    """Drug -received-> EvidenceComponent, one per Phase 7 component that was
    actually assessable (``available``) — an unavailable component has
    nothing to visualize, so no node is created for it (§3: "only create
    nodes when the corresponding evidence actually exists"). The ML
    component additionally gets its own Prediction node (Phase 6's raw model
    output), distinct from the Phase 7 evidence-component representation of
    it."""
    fusion = candidate.fusion
    for component in fusion.components:
        if not component.available:
            continue
        evidence_node_id = f"evidence:{candidate.drug_id}:{component.name}"
        builder.add_node(
            GraphNode(
                id=evidence_node_id,
                type=GraphNodeType.EVIDENCE_COMPONENT,
                label=f"{component.name} evidence",
                metadata={
                    "name": component.name,
                    "value": component.value,
                    "configured_weight": component.configured_weight,
                    "effective_weight": component.effective_weight,
                    "contribution_points": component.contribution_points,
                    "calculation_method": component.calculation_method,
                    "supporting": dict(component.supporting),
                },
            )
        )
        builder.add_edge(
            GraphEdge(
                id=f"{drug_node_id}->received->{evidence_node_id}",
                source=drug_node_id,
                target=evidence_node_id,
                type=GraphEdgeType.RECEIVED,
                metadata={"contribution_points": component.contribution_points},
                provenance=component.provenance,
            )
        )

        if component.name == "ml":
            prediction_node_id = f"prediction:{candidate.drug_id}"
            builder.add_node(
                GraphNode(
                    id=prediction_node_id,
                    type=GraphNodeType.PREDICTION,
                    label=f"{fusion.ml_model_name or 'model'} prediction",
                    metadata={
                        "model_name": fusion.ml_model_name,
                        "model_output": fusion.ml_model_output,
                        "baseline_output": fusion.ml_baseline_output,
                        "top_feature_names": list(component.supporting.get("top_feature_names") or []),
                    },
                )
            )
            builder.add_edge(
                GraphEdge(
                    id=f"{drug_node_id}->received->{prediction_node_id}",
                    source=drug_node_id,
                    target=prediction_node_id,
                    type=GraphEdgeType.RECEIVED,
                    metadata={"model_output": fusion.ml_model_output},
                    provenance="Level 6 ML prediction (GroupKFold-validated classifier over Level 5 features)",
                )
            )


def _add_score_and_rank(builder: _GraphBuilder, drug_node_id: str, candidate: RankedCandidate) -> None:
    score_node_id = f"score:{candidate.drug_id}"
    rank_node_id = f"rank:{candidate.drug_id}"

    builder.add_node(
        GraphNode(
            id=score_node_id,
            type=GraphNodeType.SCORE,
            label=f"{candidate.repurposing_score:.1f}/{candidate.fusion.score_scale.split('-')[-1]}",
            metadata={
                "repurposing_score": candidate.repurposing_score,
                "score_scale": candidate.fusion.score_scale,
                "scoring_version": candidate.fusion.scoring_version,
            },
        )
    )
    builder.add_node(
        GraphNode(
            id=rank_node_id,
            type=GraphNodeType.RANK,
            label=f"Rank #{candidate.rank}",
            metadata={"rank": candidate.rank},
        )
    )
    builder.add_edge(
        GraphEdge(
            id=f"{drug_node_id}->received->{score_node_id}",
            source=drug_node_id,
            target=score_node_id,
            type=GraphEdgeType.RECEIVED,
            metadata={"repurposing_score": candidate.repurposing_score},
            provenance="Phase 7 evidence fusion (UNCHANGED here)",
        )
    )
    builder.add_edge(
        GraphEdge(
            id=f"{drug_node_id}->ranked->{rank_node_id}",
            source=drug_node_id,
            target=rank_node_id,
            type=GraphEdgeType.RANKED,
            metadata={"rank": candidate.rank},
            provenance="Phase 8 candidate ranking (UNCHANGED here)",
        )
    )


def _add_explanation(
    builder: _GraphBuilder, drug_node_id: str, candidate: RankedCandidate, explanation: CandidateExplanation
) -> None:
    explanation_node_id = f"explanation:{candidate.drug_id}"
    builder.add_node(
        GraphNode(
            id=explanation_node_id,
            type=GraphNodeType.EXPLANATION,
            label="AI explanation",
            metadata={
                "summary": explanation.summary,
                "provider": explanation.provenance.provider,
                "limitations": list(explanation.limitations),
            },
        )
    )
    builder.add_edge(
        GraphEdge(
            id=f"{drug_node_id}->explained_by->{explanation_node_id}",
            source=drug_node_id,
            target=explanation_node_id,
            type=GraphEdgeType.EXPLAINED_BY,
            metadata={"provider": explanation.provenance.provider},
            provenance="Phase 9 AI explanation (narration only, not re-derived here)",
        )
    )


def _check_consistency(candidate: RankedCandidate, generation_candidate: CandidateDrug) -> None:
    if (candidate.disease_id, candidate.drug_id) != (
        generation_candidate.disease_id,
        generation_candidate.drug_id,
    ):
        raise InconsistentGraphInputError(
            f"ranked candidate {(candidate.disease_id, candidate.drug_id)} != "
            f"generation candidate {(generation_candidate.disease_id, generation_candidate.drug_id)}"
        )


def build_evidence_graph(
    candidates: list[RankedCandidate],
    generation_candidates: list[CandidateDrug],
    *,
    explanations: list[CandidateExplanation] | None = None,
) -> EvidenceGraph:
    """Build one evidence graph covering every candidate in ``candidates``.

    ``generation_candidates`` must contain the Level 4 ``CandidateDrug`` for
    each ranked candidate (matched by ``drug_id``) — it is what carries the
    exact gene-target / pathway matches with their provenance; Phase 8's
    ``RankedCandidate`` alone only keeps the *ids*. ``explanations`` is
    optional; if given, matched to ``candidates`` by ``drug_id`` (a candidate
    with no matching explanation simply gets no explanation node).
    """
    if not candidates:
        raise InconsistentGraphInputError("candidates must be a non-empty list[RankedCandidate]")

    disease_ids = {c.disease_id for c in candidates}
    if len(disease_ids) != 1:
        raise InconsistentGraphInputError("all candidates must share the same disease_id")

    gen_by_drug = {c.drug_id: c for c in generation_candidates}
    explanation_by_drug = {e.drug_id: e for e in (explanations or [])}

    builder = _GraphBuilder()
    disease_id = candidates[0].disease_id
    disease_node_id = _disease_node_id(disease_id)
    builder.add_node(_disease_node(candidates[0]))

    includes_ml_evidence = False
    for candidate in candidates:
        generation_candidate = gen_by_drug.get(candidate.drug_id)
        if generation_candidate is None:
            raise InconsistentGraphInputError(
                f"no CandidateDrug supplied for ranked candidate {candidate.drug_id!r}"
            )
        _check_consistency(candidate, generation_candidate)

        drug_node_id = _drug_node_id(candidate.drug_id)
        builder.add_node(_drug_node(candidate))

        _add_gene_target_evidence(builder, disease_node_id, drug_node_id, generation_candidate)
        _add_pathway_evidence(builder, disease_node_id, drug_node_id, generation_candidate)
        _add_prediction_and_evidence(builder, drug_node_id, candidate)
        _add_score_and_rank(builder, drug_node_id, candidate)

        ml_component = candidate.fusion.component("ml")
        includes_ml_evidence = includes_ml_evidence or bool(ml_component and ml_component.available)

        explanation = explanation_by_drug.get(candidate.drug_id)
        if explanation is not None:
            _add_explanation(builder, drug_node_id, candidate, explanation)

    nodes = builder.nodes
    edges = builder.edges

    node_type_counts: dict[str, int] = {}
    for n in nodes:
        node_type_counts[n.type.value] = node_type_counts.get(n.type.value, 0) + 1
    edge_type_counts: dict[str, int] = {}
    for e in edges:
        edge_type_counts[e.type.value] = edge_type_counts.get(e.type.value, 0) + 1

    drug_ids = [c.drug_id for c in candidates]
    return EvidenceGraph(
        disease_id=disease_id,
        disease_name=candidates[0].disease_name,
        drug_id=drug_ids[0] if len(drug_ids) == 1 else None,
        drug_ids=drug_ids,
        nodes=nodes,
        edges=edges,
        metadata=EvidenceGraphMetadata(
            n_nodes=len(nodes),
            n_edges=len(edges),
            n_candidates=len(candidates),
            includes_ml_evidence=includes_ml_evidence,
            includes_explanation=bool(explanation_by_drug),
            node_type_counts=node_type_counts,
            edge_type_counts=edge_type_counts,
            disclaimer=DISCLAIMER,
        ),
    )


def build_candidate_graph(
    candidate: RankedCandidate,
    generation_candidate: CandidateDrug,
    *,
    explanation: CandidateExplanation | None = None,
) -> EvidenceGraph:
    """Convenience: the evidence graph for exactly one ranked candidate."""
    return build_evidence_graph(
        [candidate],
        [generation_candidate],
        explanations=[explanation] if explanation is not None else None,
    )
