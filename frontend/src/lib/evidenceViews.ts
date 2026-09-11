/**
 * Reads the evidence graph the backend already returns into the two shapes
 * the Gene/Target and Pathway pages display.
 *
 * These are projections, not calculations: every field below is copied from a
 * node or edge the backend built. Nothing is inferred, and a relationship
 * that is not in the graph does not appear on those pages.
 */
import type { EvidenceGraph, GraphNode } from "../api/types";

export interface TargetJoin {
  /** The disease-associated gene end of the join. */
  geneNodeId: string;
  geneSymbol: string;
  geneId: string | null;
  ensemblId: string | null;
  geneSource: string | null;
  /** The drug-target end. */
  targetNodeId: string;
  targetName: string;
  targetId: string | null;
  uniprotId: string | null;
  actionType: string | null;
  /** The identifier the two ends were joined on, and how. */
  hgncId: string | null;
  provenance: string | null;
}

function str(node: GraphNode | undefined, key: string): string | null {
  const value = node?.metadata?.[key];
  return typeof value === "string" ? value : null;
}

/** Disease gene -> drug target joins, one per `matched_to` edge. */
export function targetJoins(graph: EvidenceGraph): TargetJoin[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n] as const));

  return graph.edges
    .filter((e) => e.type === "matched_to")
    .map((edge) => {
      const gene = byId.get(edge.source);
      const target = byId.get(edge.target);
      const edgeHgnc = edge.metadata?.hgnc_id;

      return {
        geneNodeId: edge.source,
        geneSymbol: gene?.label ?? edge.source,
        geneId: str(gene, "disease_gene_id"),
        ensemblId: str(gene, "ensembl_id"),
        geneSource: str(gene, "source"),
        targetNodeId: edge.target,
        targetName: target?.label ?? edge.target,
        targetId: str(target, "drug_target_id"),
        uniprotId: str(target, "uniprot_id"),
        actionType: str(target, "action_type"),
        hgncId: typeof edgeHgnc === "string" ? edgeHgnc : str(gene, "hgnc_id"),
        provenance: edge.provenance,
      };
    });
}

export interface SharedPathway {
  nodeId: string;
  name: string;
  reactomeId: string | null;
  /** Provenance strings from the edges that put this pathway in the graph. */
  provenances: string[];
}

/** Pathways both sides reach — the `participates_in` targets in the graph. */
export function sharedPathways(graph: EvidenceGraph): SharedPathway[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n] as const));
  const provenanceByPathway = new Map<string, Set<string>>();

  for (const edge of graph.edges) {
    if (edge.type !== "participates_in") continue;
    const pathwayEnd = byId.get(edge.target)?.type === "pathway" ? edge.target : edge.source;
    if (!provenanceByPathway.has(pathwayEnd)) provenanceByPathway.set(pathwayEnd, new Set());
    if (edge.provenance) provenanceByPathway.get(pathwayEnd)!.add(edge.provenance);
  }

  return graph.nodes
    .filter((n) => n.type === "pathway")
    .map((node) => ({
      nodeId: node.id,
      name: node.label,
      reactomeId: str(node, "reactome_id") ?? node.id.replace(/^pathway:/, ""),
      provenances: [...(provenanceByPathway.get(node.id) ?? [])],
    }));
}
