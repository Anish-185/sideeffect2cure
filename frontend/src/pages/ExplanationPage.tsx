import { CandidateBar, NeedsRun, NextStage, PageHead, Problem, Waiting } from "../components/analysis";
import { Cyanotype, Datum, IdChip, Label, Meter, Reveal, Rule, Section } from "../components/ui";
import { useCandidateExplanation } from "../hooks/useCandidateExplanation";
import { EVIDENCE_COLOR_VAR, STATUS_LABEL } from "../lib/format";
import { useFocusedCandidate, useRestoredRun } from "../state/DiscoveryContext";
import type { BiologicalEvidenceItem, CandidateExplanation, EvidenceStatus } from "../api/types";

/**
 * Stage 09. The narration — and the page most at risk of being misread, so
 * the layout keeps a hard line between what the pipeline computed and what a
 * language model wrote about it.
 *
 * The computed evidence is shown first and in full. The generated prose comes
 * after, labelled, with the provider and any validation notes attached.
 */
export function ExplanationPage() {
  const { state } = useRestoredRun();
  const { candidate } = useFocusedCandidate();

  return (
    <>
      <Section>
        <PageHead
          stage="09"
          title="AI explanation"
          lede="A written account of why a candidate is interesting — generated only from values this pipeline produced, validated against them before it is shown, and never presented as a clinical claim."
          art="inflorescence"
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
          <NeedsRun what="a grounded explanation" />
        </Section>
      ) : null}

      {candidate ? <Explanation diseaseId={candidate.disease_id} drugId={candidate.drug_id} /> : null}

      <Section>
        <NextStage from="/explanation" />
      </Section>
    </>
  );
}

function Explanation({ diseaseId, drugId }: { diseaseId: string; drugId: string }) {
  const state = useCandidateExplanation(diseaseId, drugId);

  if (state.status === "loading") {
    return (
      <Section>
        <Waiting note="Grounding the explanation in this candidate's evidence" />
      </Section>
    );
  }

  if (state.status === "error") {
    return (
      <Section>
        <div className="py-8">
          <Problem error={state.error} />
        </div>
      </Section>
    );
  }

  return <Body explanation={state.data} />;
}

function Body({ explanation: e }: { explanation: CandidateExplanation }) {
  const generated = e.provenance.provider === "deepseek_featherless";

  return (
    <>
      {/* what was computed — first, deliberately */}
      <Section tone="sunk">
        <div className="py-16">
          <Reveal>
            <Label tone="ink">Computed evidence</Label>
            <h2 className="mt-4 max-w-2xl text-[clamp(1.75rem,4vw,2.75rem)] font-semibold">
              What the pipeline established, before anything was written
            </h2>
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-12 space-y-px">
              {e.biological_evidence.map((item) => (
                <BiologicalRow key={item.kind} item={item} />
              ))}

              <div className="border-t border-rule py-6">
                <div className="grid gap-x-10 gap-y-4 md:grid-cols-[12rem_1fr_7rem]">
                  <div>
                    <p className="label" style={{ color: "var(--color-ml)" }}>
                      Model signal
                    </p>
                    <p className="mt-2 text-sm text-ink-soft">{STATUS_LABEL[e.model_evidence.status]}</p>
                  </div>
                  <div className="self-center">
                    {e.model_evidence.model_output !== null ? (
                      <Meter value={e.model_evidence.model_output} color="var(--color-ml)" height={5} />
                    ) : null}
                    <p className="mt-3 text-[0.8125rem] leading-relaxed text-ink-soft">
                      {e.model_evidence.description}
                    </p>
                  </div>
                  <div className="md:text-right">
                    <p className="tabular font-display text-2xl font-semibold tracking-tight">
                      {e.model_evidence.model_output?.toFixed(3) ?? "—"}
                    </p>
                    <p className="label mt-1.5">
                      {e.model_evidence.contribution_points !== null
                        ? `${e.model_evidence.contribution_points.toFixed(1)} pts`
                        : "no points"}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* the generated narration */}
      <Section tone="navy" railed={false}>
        <Cyanotype art="lotus" deep className="absolute -right-20 -top-16 w-[28rem] opacity-20 mix-blend-screen" />
        <div className="relative py-20">
          <Reveal>
            <div className="flex flex-wrap items-center gap-3">
              <Label tone="navy">{generated ? "Generated interpretation" : "Deterministic summary"}</Label>
              <span className="border border-navy-line px-2 py-1 font-mono text-[0.625rem] uppercase tracking-widest text-navy-muted">
                {generated ? (e.provenance.model_name ?? "model") : "no model used"}
              </span>
            </div>
          </Reveal>

          <Reveal delay={1}>
            <p className="mt-10 max-w-3xl text-[clamp(1.25rem,2.6vw,1.75rem)] font-medium leading-[1.45] tracking-tight text-navy-text">
              {e.summary}
            </p>
          </Reveal>

          {!generated ? (
            <Reveal delay={2}>
              <p className="mt-8 max-w-2xl border-l-2 border-navy-line pl-5 text-sm leading-relaxed text-navy-muted">
                This text was composed from the pipeline's own values rather than by a language model
                {e.provenance.fallback_reason ? ` — ${e.provenance.fallback_reason}` : ""}. The evidence above is
                unchanged either way.
              </p>
            </Reveal>
          ) : null}
        </div>
      </Section>

      {/* limitations */}
      {e.limitations.length ? (
        <Section>
          <div className="py-20">
            <Reveal>
              <Label tone="ink">Limitations</Label>
              <h3 className="mt-4 max-w-2xl text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold">
                What this does not establish
              </h3>
            </Reveal>
            <Reveal delay={1}>
              <ul className="mt-10 max-w-3xl">
                {e.limitations.map((limitation) => (
                  <li key={limitation} className="border-t border-rule py-5 leading-relaxed text-ink-soft">
                    {limitation}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </Section>
      ) : null}

      {/* grounding */}
      <Section tone="sunk">
        <div className="py-16">
          <Reveal>
            <Label tone="ink">Grounding & provenance</Label>
            <p className="mt-5 max-w-3xl leading-relaxed text-ink-soft">{e.provenance.grounding_note}</p>
          </Reveal>

          <Reveal delay={1}>
            <dl className="mt-10 grid gap-x-14 md:grid-cols-2">
              <Datum term="Provider">{e.provenance.provider}</Datum>
              <Datum term="Model">{e.provenance.model_name ?? "—"}</Datum>
              <Datum term="Explanation version">{e.provenance.explanation_version}</Datum>
              <Datum term="Generated at">{e.provenance.generated_at}</Datum>
              <Datum term="Scoring version">{e.provenance.scoring_version}</Datum>
              <Datum term="Ranking version">{e.provenance.ranking_version}</Datum>
            </dl>
          </Reveal>

          {e.provenance.validation_notes.length ? (
            <Reveal delay={2}>
              <div className="mt-10">
                <Label>Validation notes</Label>
                <ul className="mt-3 space-y-1">
                  {e.provenance.validation_notes.map((note) => (
                    <li key={note} className="font-mono text-[0.75rem] leading-relaxed text-ink-soft">
                      {note}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ) : null}

          <Reveal delay={3}>
            <div className="mt-10">
              <Rule dotted />
              <p className="mt-6 max-w-3xl text-sm leading-relaxed text-ink-soft">{e.provenance.disclaimer}</p>
            </div>
          </Reveal>
        </div>
      </Section>
    </>
  );
}

const STATUS_COLOR: Record<EvidenceStatus, string> = {
  supported: "var(--color-positive)",
  assessed_no_support: "var(--color-ink-faint)",
  not_assessed: "var(--color-ink-faint)",
};

function BiologicalRow({ item }: { item: BiologicalEvidenceItem }) {
  const color = item.kind === "pathway" ? EVIDENCE_COLOR_VAR.pathway : EVIDENCE_COLOR_VAR.gene_target;

  return (
    <div className="border-t border-rule py-6">
      <div className="grid gap-x-10 gap-y-4 md:grid-cols-[12rem_1fr_7rem]">
        <div>
          <p className="label" style={{ color }}>
            {item.kind === "pathway" ? "Pathway evidence" : "Gene-target evidence"}
          </p>
          <p className="mt-2 text-sm" style={{ color: STATUS_COLOR[item.status] }}>
            {STATUS_LABEL[item.status]}
          </p>
        </div>

        <div className="self-center">
          {item.value !== null ? <Meter value={item.value} color={color} height={5} /> : null}
          <p className="mt-3 text-[0.8125rem] leading-relaxed text-ink-soft">{item.description}</p>
          {item.supporting_ids.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {item.supporting_ids.slice(0, 12).map((id) => (
                <IdChip key={id}>{id}</IdChip>
              ))}
            </div>
          ) : null}
        </div>

        <div className="md:text-right">
          <p className="tabular font-display text-2xl font-semibold tracking-tight">
            {item.value?.toFixed(2) ?? "—"}
          </p>
          <p className="label mt-1.5">
            {item.contribution_points !== null ? `${item.contribution_points.toFixed(1)} pts` : "no points"}
          </p>
        </div>
      </div>
    </div>
  );
}
