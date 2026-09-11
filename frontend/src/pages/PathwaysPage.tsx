import { useState } from "react";
import { CandidateBar, NeedsRun, NextStage, PageHead, Problem, Waiting } from "../components/analysis";
import { Cyanotype, Figure, IdChip, Label, Reveal, Section } from "../components/ui";
import { useCandidateGraph } from "../hooks/useCandidateGraph";
import { sharedPathways } from "../lib/evidenceViews";
import { useFocusedCandidate, useRestoredRun } from "../state/DiscoveryContext";
import type { RankedCandidate } from "../api/types";

/**
 * Stage 04. The other route into a candidate: where the disease's pathways
 * and the drug's pathways are the same Reactome pathway.
 */
export function PathwaysPage() {
  const { state } = useRestoredRun();
  const { candidate } = useFocusedCandidate();

  return (
    <>
      <Section>
        <PageHead
          stage="04"
          title="Pathway analysis"
          lede="Two sets of Reactome pathways — one reached through the disease's genes, one through the drug's targets — and the intersection between them. The overlap is a direct identifier match, never a similarity score."
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
          <NeedsRun what="pathway overlap" />
        </Section>
      ) : null}

      {candidate ? <Overlap candidate={candidate} /> : null}

      <Section>
        <NextStage from="/pathways" />
      </Section>
    </>
  );
}

function Overlap({ candidate }: { candidate: RankedCandidate }) {
  const graph = useCandidateGraph(candidate.disease_id, candidate.drug_id, true);
  const pathwayComponent = candidate.fusion.components.find((c) => c.name === "pathway");
  const support = (pathwayComponent?.supporting ?? {}) as Record<string, number | undefined>;

  if (graph.status === "loading" || graph.status === "idle") {
    return (
      <Section>
        <Waiting note="Loading pathway relationships" />
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

  const shared = sharedPathways(graph.data);

  return (
    <>
      {/* the funnel, in the backend's own counts */}
      <Section tone="sunk">
        <div className="py-16">
          <Reveal>
            <div className="grid items-center gap-10 md:grid-cols-[1fr_auto_1fr_auto_1fr]">
              <Figure value={support.disease_pathway_count ?? "—"} caption="Disease pathways" />
              <span aria-hidden className="hidden text-2xl text-ink-faint md:block">
                ∩
              </span>
              <Figure value={support.matched_pathway_count ?? shared.length} caption="Shared pathways" />
              <span aria-hidden className="hidden text-2xl text-ink-faint md:block">
                ∩
              </span>
              <Figure value={support.drug_pathway_count ?? "—"} caption="Drug pathways" />
            </div>
          </Reveal>

          {pathwayComponent?.calculation_method ? (
            <Reveal delay={1}>
              <p className="mt-12 max-w-3xl border-t border-rule pt-8 font-mono text-[0.8125rem] leading-relaxed text-ink-soft">
                {pathwayComponent.calculation_method}
              </p>
            </Reveal>
          ) : null}
        </div>
      </Section>

      {/* the shared pathways themselves */}
      <Section>
        <Cyanotype art="drupe-branch" className="absolute -left-28 top-24 w-64 opacity-[0.15]" drift />
        <div className="relative py-20">
          <Reveal>
            <Label tone="ink">The intersection</Label>
            <h2 className="mt-4 max-w-2xl text-[clamp(1.75rem,4vw,2.75rem)] font-semibold">
              {shared.length === 0
                ? "No shared pathway for this pair"
                : `${shared.length} pathways both sides reach`}
            </h2>
            <p className="mt-4 max-w-xl text-ink-soft">
              {shared.length === 0
                ? "This candidate reached the ranking through gene-target evidence rather than pathway overlap."
                : "Each of these is one Reactome pathway that the disease's genes and this drug's targets both participate in."}
            </p>
          </Reveal>

          <ul className="mt-12">
            {shared.map((p, i) => (
              <Reveal key={p.nodeId} as="li" delay={((i % 3) + 1) as 1 | 2 | 3}>
                <PathwayEntry name={p.name} reactomeId={p.reactomeId} provenances={p.provenances} />
              </Reveal>
            ))}
          </ul>
        </div>
      </Section>

      {pathwayComponent?.provenance ? (
        <Section tone="navy" railed={false}>
          <div className="relative py-20">
            <Reveal>
              <Label tone="navy">Where the two sets come from</Label>
              <h3 className="mt-4 max-w-3xl text-[clamp(1.25rem,2.8vw,1.875rem)] font-semibold leading-snug text-navy-text">
                {pathwayComponent.provenance}
              </h3>
            </Reveal>
          </div>
        </Section>
      ) : null}
    </>
  );
}

function PathwayEntry({
  name,
  reactomeId,
  provenances,
}: {
  name: string;
  reactomeId: string | null;
  provenances: string[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-rule">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-baseline justify-between gap-6 py-5 text-left transition-colors hover:text-blue"
      >
        <span className="font-display text-[1.0625rem] font-semibold leading-snug tracking-tight">{name}</span>
        <span className="flex shrink-0 items-center gap-3">
          {reactomeId ? <IdChip>{reactomeId}</IdChip> : null}
          <span aria-hidden className="label">
            {open ? "−" : "+"}
          </span>
        </span>
      </button>
      {open ? (
        <div className="pb-5">
          <Label>Provenance</Label>
          <ul className="mt-2 space-y-1">
            {provenances.length ? (
              provenances.map((p) => (
                <li key={p} className="text-[0.8125rem] leading-relaxed text-ink-soft">
                  {p}
                </li>
              ))
            ) : (
              <li className="text-[0.8125rem] text-ink-soft">No provenance recorded on this edge.</li>
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
