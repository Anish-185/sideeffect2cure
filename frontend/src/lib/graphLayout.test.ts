import { describe, expect, it } from "vitest";
import { layoutGraph } from "./graphLayout";
import type { EvidenceGraph, GraphNode } from "../api/types";

function node(id: string, type: GraphNode["type"], overrides: Partial<GraphNode> = {}): GraphNode {
  return { id, type, label: id, metadata: {}, ...overrides };
}

function baseGraph(overrides: Partial<EvidenceGraph> = {}): EvidenceGraph {
  return {
    disease_id: "DIS:1",
    disease_name: "d",
    drug_id: "DRUG:1",
    drug_ids: ["DRUG:1"],
    nodes: [node("disease:DIS:1", "disease"), node("drug:DRUG:1", "drug")],
    edges: [],
    metadata: {
      graph_schema_version: "1.0",
      n_nodes: 2,
      n_edges: 0,
      n_candidates: 1,
      includes_ml_evidence: false,
      includes_explanation: false,
      node_type_counts: {},
      edge_type_counts: {},
      disclaimer: "x",
      interpretation: "i",
    },
    ...overrides,
  };
}

describe("layoutGraph", () => {
  it("places every real node exactly once", () => {
    const graph = baseGraph();
    const { nodes } = layoutGraph(graph);
    const evidenceNodes = nodes.filter((n) => n.type === "evidence");
    expect(evidenceNodes).toHaveLength(2);
    expect(new Set(evidenceNodes.map((n) => n.id))).toEqual(new Set(["disease:DIS:1", "drug:DRUG:1"]));
  });

  it("assigns disease and drug to different x columns in reading order", () => {
    const { nodes } = layoutGraph(baseGraph());
    const disease = nodes.find((n) => n.id === "disease:DIS:1")!;
    const drug = nodes.find((n) => n.id === "drug:DRUG:1")!;
    expect(disease.position.x).toBeLessThan(drug.position.x);
  });

  it("is deterministic for the same input", () => {
    const graph = baseGraph();
    const a = layoutGraph(graph);
    const b = layoutGraph(graph);
    expect(a.nodes.map((n) => [n.id, n.position.x, n.position.y])).toEqual(
      b.nodes.map((n) => [n.id, n.position.x, n.position.y]),
    );
  });

  it("caps a dense column and adds a single overflow marker instead of dropping data silently", () => {
    const pathwayNodes = Array.from({ length: 20 }, (_, i) => node(`pathway:${i}`, "pathway"));
    const graph = baseGraph({
      nodes: [...baseGraph().nodes, ...pathwayNodes],
      edges: pathwayNodes.map((p, i) => ({
        id: `e${i}`,
        source: "drug:DRUG:1",
        target: p.id,
        type: "participates_in" as const,
        metadata: {},
        provenance: null,
      })),
    });
    const { nodes } = layoutGraph(graph);
    const visiblePathways = nodes.filter((n) => n.type === "evidence" && n.id.startsWith("pathway:"));
    const overflow = nodes.filter((n) => n.type === "overflow");
    expect(visiblePathways.length).toBeLessThan(20);
    expect(overflow).toHaveLength(1);
  });

  it("never emits an edge referencing a node that isn't in the diagram (no dangling / fabricated edges)", () => {
    const graph = baseGraph({
      edges: [
        { id: "e1", source: "disease:DIS:1", target: "drug:DRUG:1", type: "associated_with", metadata: {}, provenance: "p" },
        // references a node that doesn't exist in `nodes` — must be dropped, not fabricated into the diagram
        { id: "e2", source: "disease:DIS:1", target: "nonexistent", type: "associated_with", metadata: {}, provenance: "p" },
      ],
    });
    const { nodes, edges } = layoutGraph(graph);
    const nodeIds = new Set(nodes.map((n) => n.id));
    for (const e of edges) {
      expect(nodeIds.has(e.source)).toBe(true);
      expect(nodeIds.has(e.target)).toBe(true);
    }
    expect(edges.map((e) => e.id)).toEqual(["e1"]);
  });

  it("passes through node id/type/label/metadata unchanged (no relationship invented)", () => {
    const graph = baseGraph({
      nodes: [...baseGraph().nodes, node("disease_gene:GENE:1", "disease_gene", { label: "BRAF", metadata: { hgnc_id: "HGNC:1097" } })],
    });
    const { nodes } = layoutGraph(graph);
    const gene = nodes.find((n) => n.id === "disease_gene:GENE:1");
    expect(gene?.type).toBe("evidence");
    const evidenceGene = gene?.type === "evidence" ? gene : undefined;
    expect(evidenceGene?.data.node.label).toBe("BRAF");
    expect(evidenceGene?.data.node.metadata).toEqual({ hgnc_id: "HGNC:1097" });
  });
});
