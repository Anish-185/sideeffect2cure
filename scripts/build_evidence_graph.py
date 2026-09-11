#!/usr/bin/env python3
"""Phase 10 demo: run the full pipeline for one disease and build the
evidence graph for its top-N ranked candidates.

    python scripts/build_evidence_graph.py                        # GBM, top 1
    python scripts/build_evidence_graph.py "Alzheimer disease" --top-n 3

Runs candidate generation -> features -> ML -> evidence fusion -> ranking ->
AI explanation (Levels 4-9, unchanged), then Phase 10: builds one
``EvidenceGraph`` (nodes + edges) that represents that evidence — no new
relationship is discovered, no score/rank is recalculated.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from app.services.disease.errors import DiseaseIntelligenceError
from app.services.graph import build_graph_for_disease
from app.services.ml.model import ModelNotTrainedError


def _print_tree(graph) -> None:
    for drug_id in graph.drug_ids:
        drug_node = graph.node(f"drug:{drug_id}")
        rank_node = graph.node(f"rank:{drug_id}")
        score_node = graph.node(f"score:{drug_id}")
        print(f"\n{'=' * 70}")
        print(f"{rank_node.label if rank_node else '?'}  —  {drug_node.label}  "
              f"({score_node.label if score_node else '?'})")
        print(f"{'=' * 70}")

        gene_ids = {
            e.target for e in graph.edges if e.type == "associated_with"
            and graph.node(e.target) and graph.node(e.target).type == "disease_gene"
        }
        target_ids = {e.target for e in graph.edges_from(f"drug:{drug_id}") if e.type == "has_target"}
        pathway_ids = {e.target for e in graph.edges_from(f"drug:{drug_id}") if e.type == "participates_in"}

        if gene_ids and target_ids:
            print("\n  DISEASE GENES -> DRUG TARGETS")
            for edge in graph.edges:
                if edge.type != "matched_to":
                    continue
                if edge.target not in target_ids:
                    continue
                gene = graph.node(edge.source)
                target = graph.node(edge.target)
                print(f"    {gene.label} ({gene.metadata.get('hgnc_id')})  ->  "
                      f"{target.label}  [{target.metadata.get('action_type')}]")

        if pathway_ids:
            print("\n  PATHWAYS")
            for pid in pathway_ids:
                p = graph.node(pid)
                print(f"    {p.label}  (disease support={p.metadata.get('disease_gene_support_count')}, "
                      f"drug support={p.metadata.get('drug_supporting_target_count')})")

        prediction = graph.node(f"prediction:{drug_id}")
        if prediction:
            print(f"\n  ML PREDICTION: {prediction.label} "
                  f"(output={prediction.metadata.get('model_output')}, "
                  f"baseline={prediction.metadata.get('baseline_output')})")

        evidence_nodes = [
            graph.node(e.target) for e in graph.edges_from(f"drug:{drug_id}")
            if e.type == "received" and graph.node(e.target) and graph.node(e.target).type == "evidence_component"
        ]
        if evidence_nodes:
            print("\n  EVIDENCE COMPONENTS")
            for n in evidence_nodes:
                print(f"    {n.label}: value={n.metadata.get('value')} "
                      f"contribution={n.metadata.get('contribution_points')} pts")

        explanation = graph.node(f"explanation:{drug_id}")
        if explanation:
            print(f"\n  AI EXPLANATION ({explanation.metadata.get('provider')})")
            print(f"    {explanation.metadata.get('summary')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "disease", nargs="?", default="Glioblastoma",
        help='disease name, alias, or MONDO id (default: "Glioblastoma" / MONDO_0018177)',
    )
    parser.add_argument("--top-n", type=int, default=1, help="how many ranked candidates to graph")
    parser.add_argument("--no-explanations", action="store_true", help="skip Phase 9 explanation nodes")
    args = parser.parse_args()

    try:
        graph = build_graph_for_disease(
            args.disease, top_n=args.top_n, include_explanations=not args.no_explanations,
        )
    except ModelNotTrainedError:
        print("No trained model found. Train it first:\n    python scripts/train_model.py",
              file=sys.stderr)
        return 1
    except DiseaseIntelligenceError as exc:
        print(f"Could not resolve disease {args.disease!r}: {exc}", file=sys.stderr)
        return 1

    print(f"Disease: {graph.disease_name} ({graph.disease_id})")
    print(f"Candidates graphed: {graph.metadata.n_candidates}  ({', '.join(graph.drug_ids)})")
    print(f"Nodes: {graph.metadata.n_nodes}   Edges: {graph.metadata.n_edges}")
    print(f"Node types: {graph.metadata.node_type_counts}")
    print(f"Edge types: {graph.metadata.edge_type_counts}")

    _print_tree(graph)

    print(f"\n{graph.metadata.disclaimer}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
