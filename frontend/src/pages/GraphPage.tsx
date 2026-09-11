import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CandidateBar, NeedsRun, NextStage, PageHead, Problem, Waiting } from "../components/analysis";
import { EvidenceEdge, EvidenceNode, NODE_ACCENT, OverflowNode } from "../components/graph/nodes";
import { Cyanotype, IdChip, Label, Reveal, Section } from "../components/ui";
import { useCandidateGraph } from "../hooks/useCandidateGraph";
import { NODE_TYPE_LABEL, NODE_TYPE_WHY, titleCase } from "../lib/format";
import { layoutGraph } from "../lib/graphLayout";
import { connectedSubgraph, traceStepHighlight, tracedColumns, type HighlightSet } from "../lib/graphTrace";
import { useFocusedCandidate, useRestoredRun } from "../state/DiscoveryContext";
import type { EvidenceGraph, GraphNode } from "../api/types";

/**
 * Stage 08. The graph gets a page of its own because it is the only view
 * where the whole chain is visible at once.
 *
 * Legibility comes from progressive disclosure, not from drawing less: the
 * full graph is always rendered, and selection or the guided trace dims
 * everything that is not part of the path being followed.
 */
export function GraphPage() {
  const { state } = useRestoredRun();
  const { candidate } = useFocusedCandidate();

  return (
    <>
      <Section>
        <PageHead
          stage="08"
          title="Evidence graph"
          lede="Every relationship behind one candidate, in reading order: disease to gene to target to drug, and disease to pathway to drug. Select any node to isolate the chain it belongs to."
          art="pavilion"
        />
        {candidate ? <CandidateBar /> : null}
      </Section>

      {state.status === "loading" ? (
        <Section>
          <Waiting note="Running the pipeline" />
        </Section>
      ) : null}

      {state.status !== "success" && state.status !== "loading" ? (
        <Section>
          <NeedsRun what="the evidence graph" />
        </Section>
      ) : null}

      {candidate ? (
        <ReactFlowProvider>
          <Explorer diseaseId={candidate.disease_id} drugId={candidate.drug_id} />
        </ReactFlowProvider>
      ) : null}

      <Section>
        <NextStage from="/graph" />
      </Section>
    </>
  );
}

const NODE_TYPES = { evidence: EvidenceNode, overflow: OverflowNode };
const EDGE_TYPES = { evidence: EvidenceEdge };

function Explorer({ diseaseId, drugId }: { diseaseId: string; drugId: string }) {
  const graph = useCandidateGraph(diseaseId, drugId, true);

  if (graph.status === "loading" || graph.status === "idle") {
    return (
      <Section>
        <Waiting note="Building the graph" />
      </Section>
    );
  }

  if (graph.status === "error") {
    return (
      <Section>
        <div className="py-8">
          <Problem error={graph.error} />
        </div>
      </Section>
    );
  }

  return <Canvas graph={graph.data} />;
}

function Canvas({ graph }: { graph: EvidenceGraph }) {
  const { fitView } = useReactFlow();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [traceStep, setTraceStep] = useState<number | null>(null);

  const columns = useMemo(() => tracedColumns(graph), [graph]);
  const base = useMemo(() => layoutGraph(graph), [graph]);

  /** Exactly one thing is emphasised at a time: an explicit selection wins,
   * otherwise the guided trace, otherwise nothing is dimmed. */
  const highlight: HighlightSet | null = useMemo(() => {
    if (selectedId) return connectedSubgraph(graph, selectedId);
    if (traceStep !== null) return traceStepHighlight(graph, columns, traceStep);
    return null;
  }, [graph, selectedId, traceStep, columns]);

  const nodes = useMemo(
    () =>
      base.nodes.map((n) => ({
        ...n,
        selected: n.id === selectedId,
        data: {
          ...n.data,
          dimmed: highlight ? !highlight.nodeIds.has(n.id) : false,
          traced: highlight ? highlight.nodeIds.has(n.id) : false,
        },
      })),
    [base.nodes, highlight, selectedId],
  );

  const edges = useMemo(
    () =>
      base.edges.map((e) => ({
        ...e,
        data: {
          ...e.data,
          dimmed: highlight ? !highlight.edgeIds.has(e.id) : false,
          traced: highlight ? highlight.edgeIds.has(e.id) : false,
        },
      })),
    [base.edges, highlight],
  );

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
    setTraceStep(null);
    setSelectedId((current) => (current === node.id ? null : node.id));
  }, []);

  const selectedNode = graph.nodes.find((n) => n.id === selectedId) ?? null;

  const stepTrace = useCallback(
    (direction: 1 | -1) => {
      setSelectedId(null);
      setTraceStep((current) => {
        const next = current === null ? 0 : current + direction;
        if (next < 0) return null;
        return Math.min(next, columns.length - 1);
      });
    },
    [columns.length],
  );

  /**
   * Keep the viewport on whatever is currently emphasised.
   *
   * Fitting the whole ten-column graph into the canvas drops the zoom low
   * enough that no label can be read, which defeats the point of the page. So
   * the fit is floored at a legible zoom, and once something is highlighted
   * the viewport moves to that subset instead — the graph is explored by
   * following a path, not by squinting at all of it at once.
   */
  useEffect(() => {
    const ids = highlight ? [...highlight.nodeIds].map((id) => ({ id })) : undefined;
    const id = window.setTimeout(() => {
      void fitView(
        ids?.length
          ? { nodes: ids, padding: 0.3, minZoom: 0.55, maxZoom: 1.15, duration: 500 }
          : { padding: 0.15, minZoom: 0.62, duration: 400 },
      );
    }, 60);
    return () => window.clearTimeout(id);
  }, [graph, fitView, highlight]);

  return (
    <>
      <Section railed={false}>
        <div className="py-10">
          {/* controls */}
          <Reveal>
            <div className="flex flex-wrap items-end justify-between gap-6">
              <div>
                <Label tone="ink">Guided trace</Label>
                <p className="mt-3 font-display text-[clamp(1.25rem,2.6vw,1.75rem)] font-semibold tracking-tight">
                  {traceStep === null
                    ? "Walk the chain one stage at a time"
                    : `${traceStep + 1} of ${columns.length} · ${NODE_TYPE_LABEL[columns[traceStep]]}`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => stepTrace(-1)} className="btn btn-ghost bracket">
                  ← Back
                </button>
                <button type="button" onClick={() => stepTrace(1)} className="btn btn-primary">
                  {traceStep === null ? "Start trace" : "Next stage"} <span aria-hidden>→</span>
                </button>
                {selectedId || traceStep !== null ? (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedId(null);
                      setTraceStep(null);
                    }}
                    className="btn btn-ghost bracket"
                  >
                    Show all
                  </button>
                ) : null}
              </div>
            </div>
          </Reveal>

          {/* the canvas */}
          <div className="mt-8 h-[clamp(26rem,68vh,44rem)] border border-rule bg-paper-raised">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={NODE_TYPES}
              edgeTypes={EDGE_TYPES}
              onNodeClick={onNodeClick}
              onPaneClick={() => setSelectedId(null)}
              proOptions={{ hideAttribution: true }}
              minZoom={0.2}
              maxZoom={2.5}
              fitView
              fitViewOptions={{ padding: 0.15, minZoom: 0.62 }}
              nodesDraggable={false}
              nodesConnectable={false}
            >
              <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="var(--color-rule)" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>

          {/* legend */}
          <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2">
            <Label>Reading order</Label>
            {columns.map((type, i) => (
              <span key={type} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5" style={{ background: NODE_ACCENT[type] }} aria-hidden />
                <span className="label" style={{ color: "var(--color-ink-soft)" }}>
                  {NODE_TYPE_LABEL[type]}
                </span>
                {i < columns.length - 1 ? (
                  <span aria-hidden className="text-ink-faint">
                    ›
                  </span>
                ) : null}
              </span>
            ))}
          </div>
        </div>
      </Section>

      {/* the inspector — what the selected node actually is */}
      <Section tone="sunk">
        <div className="py-16">
          {selectedNode ? (
            <Inspector node={selectedNode} graph={graph} />
          ) : (
            <div className="max-w-2xl">
              <Label tone="ink">Nothing selected</Label>
              <p className="mt-4 font-display text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold leading-tight tracking-tight">
                Select any node to isolate the chain it belongs to.
              </p>
              <p className="mt-4 text-ink-soft">
                Everything not on that chain dims, so a single relationship can be followed from the disease all
                the way to the explanation without losing the shape of the whole graph.
              </p>
            </div>
          )}
        </div>
      </Section>

      {/* graph provenance */}
      <Section>
        <Cyanotype art="range" className="absolute -right-24 top-8 w-64 opacity-[0.14]" drift />
        <div className="relative py-16">
          <Reveal>
            <Label tone="ink">This graph</Label>
            <div className="mt-6 flex flex-wrap gap-x-12 gap-y-6">
              <GraphStat value={graph.metadata.n_nodes} caption="Nodes" />
              <GraphStat value={graph.metadata.n_edges} caption="Edges" />
              <GraphStat value={graph.metadata.graph_schema_version} caption="Schema version" />
              <GraphStat value={graph.metadata.includes_ml_evidence ? "included" : "absent"} caption="ML evidence" />
            </div>
            <p className="mt-10 max-w-3xl leading-relaxed text-ink-soft">{graph.metadata.interpretation}</p>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-ink-soft">{graph.metadata.disclaimer}</p>
          </Reveal>
        </div>
      </Section>
    </>
  );
}

function GraphStat({ value, caption }: { value: string | number; caption: string }) {
  return (
    <div>
      <p className="tabular font-display text-2xl font-semibold tracking-tight">{value}</p>
      <p className="label mt-2">{caption}</p>
    </div>
  );
}

/** Instance detail for the selected node: its own metadata, plus every real
 * edge touching it with that edge's provenance string. */
function Inspector({ node, graph }: { node: GraphNode; graph: EvidenceGraph }) {
  const byId = new Map(graph.nodes.map((n) => [n.id, n] as const));
  const touching = graph.edges.filter((e) => e.source === node.id || e.target === node.id);

  return (
    <div className="grid gap-12 md:grid-cols-[1fr_1.2fr]">
      <div>
        <Label tone="ink">{NODE_TYPE_LABEL[node.type]}</Label>
        <h3 className="mt-4 font-display text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold leading-tight tracking-tight">
          {node.label}
        </h3>
        <p className="mt-4 max-w-md leading-relaxed text-ink-soft">{NODE_TYPE_WHY[node.type]}</p>

        {Object.keys(node.metadata).length ? (
          <dl className="mt-8">
            {Object.entries(node.metadata).map(([key, value]) => (
              <div key={key} className="flex flex-wrap items-baseline justify-between gap-4 border-t border-rule py-2.5">
                <dt className="label">{titleCase(key)}</dt>
                <dd className="tabular text-right text-sm">
                  {Array.isArray(value) ? value.join(", ") : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>

      <div>
        <Label tone="ink">Relationships ({touching.length})</Label>
        <ul className="mt-4">
          {touching.map((edge) => {
            const other = byId.get(edge.source === node.id ? edge.target : edge.source);
            const outgoing = edge.source === node.id;
            return (
              <li key={edge.id} className="border-t border-rule py-4">
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <span className="label label-ink">{titleCase(edge.type)}</span>
                  <span aria-hidden className="text-ink-faint">
                    {outgoing ? "→" : "←"}
                  </span>
                  <span className="text-[0.9375rem] font-medium">{other?.label ?? "—"}</span>
                  {other ? <IdChip>{NODE_TYPE_LABEL[other.type]}</IdChip> : null}
                </div>
                {edge.provenance ? (
                  <p className="mt-2 text-[0.75rem] leading-relaxed text-ink-soft">{edge.provenance}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
