/**
 * Turns the backend's `EvidenceGraph` (nodes[] + edges[], no positions) into
 * a deterministic, readable left-to-right layout for React Flow.
 *
 * This is presentation only: a fixed reading order (disease -> disease gene
 * -> drug target -> pathway -> drug -> prediction -> evidence -> score ->
 * rank -> explanation) and simple column/row coordinates. No relationship is
 * added or changed — every node/edge id, type, label and metadata value is
 * passed through unmodified.
 */
import type { Edge, Node } from "@xyflow/react";
import type { EvidenceGraph, GraphEdge, GraphNode, GraphNodeType } from "../api/types";

export const COLUMN_ORDER: GraphNodeType[] = [
  "disease",
  "disease_gene",
  "drug_target",
  "pathway",
  "drug",
  "prediction",
  "evidence_component",
  "score",
  "rank",
  "explanation",
];

const COLUMN_X_GAP = 300;
const ROW_Y_GAP = 92;
// Columns that can legitimately have dozens of real nodes (every disease
// gene / drug target / pathway match). Capped in the DIAGRAM ONLY so the
// canvas stays legible; nothing is removed from the underlying data — the
// evidence panel / candidate detail view still lists all of them.
const MAX_VISIBLE_PER_COLUMN = 14;

export interface LayoutNodeData extends Record<string, unknown> {
  node: GraphNode;
}
export interface OverflowNodeData extends Record<string, unknown> {
  overflowCount: number;
  nodeType: GraphNodeType;
}

export type EvidenceRFNode = Node<LayoutNodeData, "evidence"> | Node<OverflowNodeData, "overflow">;
export type EvidenceRFEdge = Edge<{ edge: GraphEdge }, "evidence">;

function relevance(node: GraphNode): number {
  const m = node.metadata;
  const candidates = [
    m.contribution_points,
    m.drug_supporting_target_count,
    m.disease_gene_support_count,
    m.value,
  ];
  for (const c of candidates) {
    if (typeof c === "number") return c;
  }
  return 0;
}

export function layoutGraph(graph: EvidenceGraph): { nodes: EvidenceRFNode[]; edges: EvidenceRFEdge[] } {
  const byType = new Map<GraphNodeType, GraphNode[]>();
  for (const node of graph.nodes) {
    const list = byType.get(node.type) ?? [];
    list.push(node);
    byType.set(node.type, list);
  }

  const nodes: EvidenceRFNode[] = [];
  const visibleIds = new Set<string>();

  COLUMN_ORDER.forEach((type, columnIndex) => {
    const columnNodes = (byType.get(type) ?? []).slice().sort((a, b) => relevance(b) - relevance(a));
    const visible = columnNodes.slice(0, MAX_VISIBLE_PER_COLUMN);
    const overflow = columnNodes.length - visible.length;
    const x = columnIndex * COLUMN_X_GAP;
    const totalRows = visible.length + (overflow > 0 ? 1 : 0);
    const startY = -((totalRows - 1) * ROW_Y_GAP) / 2;

    visible.forEach((node, rowIndex) => {
      visibleIds.add(node.id);
      nodes.push({
        id: node.id,
        type: "evidence",
        position: { x, y: startY + rowIndex * ROW_Y_GAP },
        data: { node },
      });
    });

    if (overflow > 0) {
      nodes.push({
        id: `${type}__overflow`,
        type: "overflow",
        position: { x, y: startY + visible.length * ROW_Y_GAP },
        data: { overflowCount: overflow, nodeType: type },
        selectable: false,
        draggable: false,
      });
    }
  });

  const edges: EvidenceRFEdge[] = graph.edges
    .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
    .map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "evidence",
      data: { edge },
    }));

  return { nodes, edges };
}
