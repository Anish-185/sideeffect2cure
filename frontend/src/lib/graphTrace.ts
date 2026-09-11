/**
 * Presentation-only graph traversal over the already-fetched EvidenceGraph.
 * Never adds, removes, or reinterprets a node/edge — it only decides which
 * of the real ones to emphasize for a given selection or trace step.
 */
import type { EvidenceGraph, GraphNodeType } from "../api/types";
import { COLUMN_ORDER } from "./graphLayout";

export interface HighlightSet {
  nodeIds: Set<string>;
  edgeIds: Set<string>;
}

/** The full reasoning chain touching `nodeId`: every ancestor (what led to
 * it) and every descendant (what it led to), walked transitively over real
 * edges only. This is what "select a node, see why it matters" renders. */
export function connectedSubgraph(graph: EvidenceGraph, nodeId: string): HighlightSet {
  const outgoing = new Map<string, typeof graph.edges>();
  const incoming = new Map<string, typeof graph.edges>();
  for (const e of graph.edges) {
    outgoing.set(e.source, [...(outgoing.get(e.source) ?? []), e]);
    incoming.set(e.target, [...(incoming.get(e.target) ?? []), e]);
  }

  const nodeIds = new Set([nodeId]);
  const edgeIds = new Set<string>();

  let frontier = [nodeId];
  const seenBack = new Set([nodeId]);
  while (frontier.length) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const e of incoming.get(id) ?? []) {
        edgeIds.add(e.id);
        nodeIds.add(e.source);
        if (!seenBack.has(e.source)) {
          seenBack.add(e.source);
          next.push(e.source);
        }
      }
    }
    frontier = next;
  }

  frontier = [nodeId];
  const seenFwd = new Set([nodeId]);
  while (frontier.length) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const e of outgoing.get(id) ?? []) {
        edgeIds.add(e.id);
        nodeIds.add(e.target);
        if (!seenFwd.has(e.target)) {
          seenFwd.add(e.target);
          next.push(e.target);
        }
      }
    }
    frontier = next;
  }

  return { nodeIds, edgeIds };
}

/** Just the one edge and its two endpoints. */
export function edgeHighlight(sourceId: string, targetId: string, edgeId: string): HighlightSet {
  return { nodeIds: new Set([sourceId, targetId]), edgeIds: new Set([edgeId]) };
}

/** The node types that actually appear in this graph, in the fixed reading
 * order — the sequence Trace Path steps through. */
export function tracedColumns(graph: EvidenceGraph): GraphNodeType[] {
  const present = new Set(graph.nodes.map((n) => n.type));
  return COLUMN_ORDER.filter((t) => present.has(t));
}

/** Cumulative highlight for a trace step: every node in columns[0..stepIndex]
 * and every edge fully contained within that set. */
export function traceStepHighlight(graph: EvidenceGraph, columns: GraphNodeType[], stepIndex: number): HighlightSet {
  const activeTypes = new Set(columns.slice(0, stepIndex + 1));
  const nodeIds = new Set(graph.nodes.filter((n) => activeTypes.has(n.type)).map((n) => n.id));
  const edgeIds = new Set(graph.edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target)).map((e) => e.id));
  return { nodeIds, edgeIds };
}
