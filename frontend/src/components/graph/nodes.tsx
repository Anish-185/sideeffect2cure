/**
 * The node and edge renderers for the evidence graph.
 *
 * Readability is the whole job here: a node is a labelled plate, not a
 * bubble, and dimming is done with opacity so an unhighlighted node stays
 * present (the reader can still see the shape of the graph) without competing
 * with the traced path.
 */
import { BaseEdge, Handle, Position, getBezierPath, type EdgeProps, type NodeProps } from "@xyflow/react";
import type { GraphNodeType } from "../../api/types";
import type { EvidenceRFEdge, LayoutNodeData, OverflowNodeData } from "../../lib/graphLayout";
import { NODE_TYPE_LABEL } from "../../lib/format";

/** One hue per family, matching the evidence colours used site-wide. */
export const NODE_ACCENT: Record<GraphNodeType, string> = {
  disease: "var(--color-ink)",
  disease_gene: "var(--color-gene)",
  drug_target: "var(--color-gene)",
  pathway: "var(--color-pathway)",
  drug: "var(--color-blue)",
  prediction: "var(--color-ml)",
  evidence_component: "var(--color-ink-soft)",
  score: "var(--color-blue)",
  rank: "var(--color-ink-soft)",
  explanation: "var(--color-ink-soft)",
};

export function EvidenceNode({ data, selected }: NodeProps & { data: LayoutNodeData }) {
  const { node } = data;
  const dimmed = data.dimmed === true;
  const traced = data.traced === true;
  const accent = NODE_ACCENT[node.type];

  return (
    <div
      className="relative transition-opacity duration-300"
      style={{ opacity: dimmed ? 0.16 : 1 }}
    >
      <Handle type="target" position={Position.Left} className="!h-1 !w-1 !border-0 !bg-transparent" />
      <div
        className="min-w-[10rem] max-w-[14rem] border bg-paper-raised px-3 py-2"
        style={{
          borderColor: traced || selected ? accent : "var(--color-rule)",
          borderWidth: traced || selected ? 1.5 : 1,
          boxShadow: selected ? `0 0 0 3px color-mix(in srgb, ${accent} 18%, transparent)` : undefined,
        }}
      >
        <p className="label" style={{ color: traced ? accent : undefined, fontSize: "0.5625rem" }}>
          {NODE_TYPE_LABEL[node.type]}
        </p>
        <p className="mt-1 text-[0.8125rem] font-medium leading-snug text-ink">{node.label}</p>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1 !w-1 !border-0 !bg-transparent" />
    </div>
  );
}

/** The "+N more" plate. The diagram caps each column for legibility; this
 * makes the cap visible rather than silently dropping real nodes. */
export function OverflowNode({ data }: NodeProps & { data: OverflowNodeData }) {
  return (
    <div className="min-w-[10rem] border border-dashed border-rule px-3 py-2 text-center">
      <p className="label" style={{ fontSize: "0.5625rem" }}>
        +{data.overflowCount} more {NODE_TYPE_LABEL[data.nodeType].toLowerCase()}
      </p>
    </div>
  );
}

export function EvidenceEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps & { data?: EvidenceRFEdge["data"] & { dimmed?: boolean; traced?: boolean } }) {
  const [path] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const traced = data?.traced === true;
  const dimmed = data?.dimmed === true;

  return (
    <BaseEdge
      path={path}
      style={{
        stroke: traced ? "var(--color-blue)" : "var(--color-rule)",
        strokeWidth: traced ? 1.6 : 1,
        opacity: dimmed ? 0.12 : 1,
        transition: "opacity 300ms ease, stroke 300ms ease",
      }}
    />
  );
}
