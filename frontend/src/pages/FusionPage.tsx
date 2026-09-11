import { CandidateBar, NeedsRun, NextStage, PageHead, Waiting } from "../components/analysis";
import { CountUp, Cyanotype, Datum, IdChip, Label, Meter, Reveal, Rule, Section } from "../components/ui";
import { EVIDENCE_COLOR_VAR, EVIDENCE_LABEL, formatPoints } from "../lib/format";
import { useFocusedCandidate, useRestoredRun } from "../state/DiscoveryContext";
import type { EvidenceComponent, RankedCandidate } from "../api/types";

/**
 * Stage 06. The arithmetic, shown rather than asserted.
 *
 * The whole page is one equation laid out vertically: each component's value,
 * the weight applied to it, the points that produced, and the sum. A reader
 * should be able to check the total with a calculator.
 */
export function FusionPage() {
  const { state } = useRestoredRun();
  const { candidate } = useFocusedCandidate();

  return (
    <>
      <Section>
        <PageHead
          stage="06"
          title="Evidence fusion"
          lede="Three independent evidence families, each scored on its own terms, then weighted into one number. Every intermediate value is kept — including the ones that were unavailable."
          art="column"
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
          <NeedsRun what="how a score was built" />
        </Section>
      ) : null}

      {candidate ? <Fusion candidate={candidate} /> : null}

      <Section>
        <NextStage from="/fusion" />
      </Section>
    </>
  );
}

function Fusion({ candidate }: { candidate: RankedCandidate }) {
  const f = candidate.fusion;

  return (
    <>
      {/* the equation */}
      <Section>
        <Cyanotype art="column" className="absolute -right-20 top-10 w-56 opacity-[0.13]" drift />
        <div className="relative py-20">
          <Reveal>
            <Label tone="ink">The calculation</Label>
            <h2 className="mt-4 max-w-2xl text-[clamp(1.75rem,4vw,2.75rem)] font-semibold">
              How {f.drug_name} reached {f.repurposing_score.toFixed(1)}
            </h2>
          </Reveal>

          <div className="mt-14">
            {f.components.map((component, i) => (
              <Reveal key={component.name} delay={((i % 3) + 1) as 1 | 2 | 3}>
                <ComponentRow component={component} />
              </Reveal>
            ))}

            <Reveal>
              <div className="mt-6 border-t-2 border-ink pt-8">
                <div className="flex flex-wrap items-end justify-between gap-6">
                  <div>
                    <Label tone="ink">Repurposing score</Label>
                    <p className="mt-2 text-sm text-ink-soft">{f.score_scale}</p>
                  </div>
                  <p className="tabular font-display text-[clamp(3rem,9vw,6rem)] font-semibold leading-none tracking-tighter text-blue">
                    <CountUp value={f.repurposing_score} decimals={1} />
                  </p>
                </div>
              </div>
            </Reveal>
          </div>
        </div>
      </Section>

      {/* availability — the honest part */}
      <Section tone="sunk">
        <div className="py-16">
          <Reveal>
            <div className="grid gap-10 md:grid-cols-[1fr_1.4fr]">
              <div>
                <Label tone="ink">Evidence availability</Label>
                <p className="mt-4 font-display text-[clamp(1.5rem,3.2vw,2.25rem)] font-semibold leading-tight tracking-tight">
                  {f.n_components_available} of {f.components.length} families available
                </p>
              </div>
              <div className="self-center">
                <p className="text-[1.0625rem] leading-relaxed text-ink-soft">
                  {f.weights_renormalized_over_available
                    ? "Weights were renormalised over the families that were actually available, so a missing family does not silently drag the score toward zero."
                    : "Every configured family was available, so the configured weights were used unchanged."}
                </p>
                <p className="mt-4 text-sm leading-relaxed text-ink-soft">{f.provenance.missing_evidence_policy}</p>
              </div>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* what the score rests on */}
      <Section>
        <div className="py-20">
          <Reveal>
            <Label tone="ink">What the score rests on</Label>
            <h3 className="mt-4 text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold">
              Every identifier behind these numbers
            </h3>
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-10 grid gap-10 md:grid-cols-2">
              <IdSet term="Matched disease genes" ids={f.matched_disease_gene_ids} />
              <IdSet term="Matched HGNC" ids={f.matched_gene_hgnc_ids} />
              <IdSet term="Matched drug targets" ids={f.matched_drug_target_ids} />
              <IdSet term="Matched Reactome pathways" ids={f.matched_pathway_reactome_ids} />
            </div>
          </Reveal>

          <Reveal delay={2}>
            <div className="mt-14 grid gap-x-14 md:grid-cols-2">
              <Datum term="Side effects on record">
                {f.side_effect_context.side_effect_count}
                {f.side_effect_context.has_sider_evidence ? " · SIDER" : ""}
              </Datum>
              <Datum term="Drug targets characterised">{f.drug_characterization.drug_target_count}</Datum>
              <Datum term="Drug pathways characterised">{f.drug_characterization.drug_pathway_count}</Datum>
              <Datum term="Mechanisms on record">{f.drug_characterization.mechanism_count}</Datum>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* method and disclaimer */}
      <Section tone="navy" railed={false}>
        <div className="relative py-20">
          <Reveal>
            <Label tone="navy">Scoring method</Label>
            <h3 className="mt-4 max-w-2xl text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold text-navy-text">
              {f.provenance.weight_scheme}
            </h3>
          </Reveal>
          <Reveal delay={1}>
            <dl className="mt-10 grid gap-x-14 md:grid-cols-2">
              <Datum tone="navy" term="Scoring version">
                {f.provenance.scoring_version}
              </Datum>
              <Datum tone="navy" term="Normalisation">
                {f.provenance.normalization}
              </Datum>
              <Datum tone="navy" term="Missing evidence">
                {f.provenance.missing_evidence_policy}
              </Datum>
              <Datum tone="navy" term="Double counting">
                {f.provenance.double_counting_policy}
              </Datum>
              <Datum tone="navy" term="Configured weights">
                {Object.entries(f.weights_configured)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}
              </Datum>
              <Datum tone="navy" term="Generated by">
                {f.generation_methods.join(", ")}
              </Datum>
            </dl>
          </Reveal>
          <Reveal delay={2}>
            <div className="mt-10">
              <Rule tone="navy" dotted />
              <p className="mt-6 max-w-3xl leading-relaxed text-navy-muted">{f.interpretation}</p>
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-navy-faint">{f.provenance.disclaimer}</p>
            </div>
          </Reveal>
        </div>
      </Section>
    </>
  );
}

/** One term of the equation. Unavailable components are shown, not dropped —
 * a gap in the evidence is information the reader needs. */
function ComponentRow({ component }: { component: EvidenceComponent }) {
  const color = EVIDENCE_COLOR_VAR[component.name];
  const available = component.available && component.value !== null;

  return (
    <div className="border-t border-rule py-8">
      <div className="grid gap-x-10 gap-y-6 md:grid-cols-[1fr_1.1fr_8rem]">
        <div>
          <p className="label" style={{ color: available ? color : undefined }}>
            {EVIDENCE_LABEL[component.name]}
          </p>
          <p className="mt-3 tabular font-display text-[clamp(1.75rem,4vw,2.5rem)] font-semibold leading-none tracking-tight">
            {available ? component.value!.toFixed(3) : "unavailable"}
          </p>
          <p className="label mt-3">
            value × weight {component.effective_weight?.toFixed(2) ?? component.configured_weight.toFixed(2)}
          </p>
        </div>

        <div className="self-center">
          {available ? <Meter value={component.value!} color={color} height={6} /> : null}
          <p className="mt-4 font-mono text-[0.75rem] leading-relaxed text-ink-soft">
            {available ? component.calculation_method : component.unavailable_reason}
          </p>
        </div>

        <div className="md:text-right">
          <p className="label">Contribution</p>
          <p className="mt-3 tabular font-display text-[clamp(1.75rem,4vw,2.5rem)] font-semibold leading-none tracking-tight">
            {formatPoints(component.contribution_points)}
          </p>
          <p className="label mt-3">points</p>
        </div>
      </div>

      {available && Object.keys(component.supporting).length ? (
        <details className="mt-6 group">
          <summary className="label cursor-pointer list-none transition-colors hover:text-blue">
            Supporting values <span aria-hidden>+</span>
          </summary>
          <dl className="mt-4 grid gap-x-12 md:grid-cols-2">
            {Object.entries(component.supporting).map(([key, value]) => (
              <Datum key={key} term={key.replace(/_/g, " ")}>
                {typeof value === "number" ? value.toString() : String(value)}
              </Datum>
            ))}
          </dl>
          <p className="mt-4 text-[0.75rem] leading-relaxed text-ink-soft">{component.provenance}</p>
        </details>
      ) : null}
    </div>
  );
}

function IdSet({ term, ids }: { term: string; ids: string[] }) {
  return (
    <div>
      <Label>{term}</Label>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {ids.length ? ids.map((id) => <IdChip key={id}>{id}</IdChip>) : <span className="text-sm text-ink-soft">none</span>}
      </div>
    </div>
  );
}
