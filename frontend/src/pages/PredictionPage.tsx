import { CandidateBar, NeedsRun, NextStage, PageHead, Waiting } from "../components/analysis";
import { Cyanotype, Datum, Label, Meter, Reveal, Rule, Section } from "../components/ui";
import { useFocusedCandidate, useRestoredRun } from "../state/DiscoveryContext";
import type { RankedCandidate } from "../api/types";

/**
 * Stage 05. The model's output, kept deliberately separate from the biology.
 *
 * The wording on this page is load-bearing: the model produces a signal over
 * engineered features, and calling it anything clinical would misrepresent
 * what the pipeline computed. Every phrase here stays at that altitude.
 */
export function PredictionPage() {
  const { state } = useRestoredRun();
  const { candidate } = useFocusedCandidate();

  return (
    <>
      <Section>
        <PageHead
          stage="05"
          title="ML prediction"
          lede="One interpretable model, one output per disease-drug pair. It is a learned signal over the features the pipeline engineered — held apart from the biological evidence rather than blended into it."
          art="ridges"
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
          <NeedsRun what="the model's output" />
        </Section>
      ) : null}

      {candidate ? <Prediction candidate={candidate} /> : null}

      <Section>
        <NextStage from="/prediction" />
      </Section>
    </>
  );
}

function Prediction({ candidate }: { candidate: RankedCandidate }) {
  const fusion = candidate.fusion;
  const ml = fusion.components.find((c) => c.name === "ml");
  const supporting = (ml?.supporting ?? {}) as Record<string, unknown>;
  const topFeatures = Array.isArray(supporting.top_feature_names)
    ? (supporting.top_feature_names as string[])
    : [];

  if (!ml?.available || ml.value === null) {
    return (
      <Section>
        <div className="py-20">
          <Label tone="ink">Not assessed</Label>
          <h2 className="mt-4 max-w-2xl text-[clamp(1.75rem,4vw,2.75rem)] font-semibold">
            No model signal for this pair
          </h2>
          <p className="mt-5 max-w-xl text-ink-soft">
            {ml?.unavailable_reason ??
              "The model could not be applied to this candidate, so the score was built from the biological evidence alone."}
          </p>
        </div>
      </Section>
    );
  }

  return (
    <>
      {/* the output */}
      <Section tone="navy" railed={false}>
        <Cyanotype art="ridges" deep className="absolute -right-16 -top-10 w-96 opacity-25 mix-blend-screen" />
        <div className="relative py-20">
          <Reveal>
            <Label tone="navy">Model output</Label>
            <p className="mt-6 tabular font-display text-[clamp(4rem,14vw,9rem)] font-semibold leading-none tracking-tighter text-navy-text">
              {ml.value.toFixed(3)}
            </p>
            <p className="mt-6 max-w-xl text-navy-muted">
              A value between 0 and 1 from {fusion.ml_model_name ?? "the pipeline's model"}, over the engineered
              features for this pair.
            </p>
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-12 max-w-2xl">
              <Meter value={ml.value} color="var(--color-ml)" tone="navy" height={8} />
              <div className="mt-3 flex justify-between">
                <span className="label label-on-navy">0.000</span>
                {fusion.ml_baseline_output !== null ? (
                  <span className="label label-on-navy">
                    baseline {fusion.ml_baseline_output.toFixed(3)}
                  </span>
                ) : null}
                <span className="label label-on-navy">1.000</span>
              </div>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* the distinction — the most important content on the page */}
      <Section>
        <div className="py-20">
          <Reveal>
            <Label tone="ink">Read this correctly</Label>
            <h2 className="mt-4 max-w-3xl text-[clamp(1.75rem,4vw,2.75rem)] font-semibold">
              A model signal is not a statement about treatment.
            </h2>
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-12 grid gap-x-16 gap-y-10 md:grid-cols-2">
              <div>
                <p className="label" style={{ color: "var(--color-ml)" }}>
                  Model signal
                </p>
                <p className="mt-4 text-[1.0625rem] leading-relaxed text-ink-soft">
                  A learned score over engineered features. It reflects patterns in the training data — not a
                  measurement of this drug acting on this disease. It carries no clinical meaning on its own.
                </p>
                <div className="mt-6">
                  <Rule dotted />
                  <p className="mt-4 font-mono text-[0.8125rem] leading-relaxed text-ink-soft">
                    {ml.calculation_method}
                  </p>
                </div>
              </div>

              <div>
                <p className="label" style={{ color: "var(--color-gene)" }}>
                  Biological evidence
                </p>
                <p className="mt-4 text-[1.0625rem] leading-relaxed text-ink-soft">
                  Named identifiers that matched: this gene, this target, this pathway. It can be checked by
                  hand against the source databases, and it is what the gene-target and pathway components
                  measure.
                </p>
                <div className="mt-6">
                  <Rule dotted />
                  <p className="mt-4 text-[0.8125rem] leading-relaxed text-ink-soft">
                    Both are weighted into the final score, and both are always shown separately — so a strong
                    model signal can never be mistaken for biological support that is not there.
                  </p>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* interpretability */}
      {topFeatures.length ? (
        <Section tone="sunk">
          <div className="py-20">
            <Reveal>
              <Label tone="ink">Interpretability</Label>
              <h3 className="mt-4 text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold">
                Features weighing most on this output
              </h3>
            </Reveal>
            <Reveal delay={1}>
              <ol className="mt-10 max-w-2xl">
                {topFeatures.map((feature, i) => (
                  <li
                    key={feature}
                    className="flex items-baseline gap-6 border-t border-rule py-4 font-mono text-[0.875rem]"
                  >
                    <span className="label tabular">{String(i + 1).padStart(2, "0")}</span>
                    <span>{feature}</span>
                  </li>
                ))}
              </ol>
            </Reveal>
          </div>
        </Section>
      ) : null}

      {/* provenance */}
      <Section>
        <div className="py-20">
          <Reveal>
            <Label tone="ink">Model provenance</Label>
            <dl className="mt-8 grid gap-x-14 md:grid-cols-2">
              <Datum term="Model">{fusion.ml_model_name ?? "—"}</Datum>
              <Datum term="Output">{fusion.ml_model_output?.toFixed(6) ?? "—"}</Datum>
              <Datum term="Baseline output">{fusion.ml_baseline_output?.toFixed(6) ?? "—"}</Datum>
              <Datum term="Prediction schema">{fusion.provenance.prediction_schema_version ?? "—"}</Datum>
              <Datum term="Feature schema">{fusion.provenance.feature_schema_version ?? "—"}</Datum>
              <Datum term="Source">{ml.provenance}</Datum>
            </dl>
          </Reveal>
        </div>
      </Section>
    </>
  );
}
