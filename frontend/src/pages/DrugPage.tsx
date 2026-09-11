import { useState } from "react";
import { NextStage, PageHead, Problem, QueryField, Waiting } from "../components/analysis";
import { Cyanotype, Datum, Figure, IdChip, Label, Reveal, Rule, Section } from "../components/ui";
import { useDrugProfile } from "../hooks/useDrugProfile";
import type { DrugProfile } from "../api/types";

/**
 * Stage 02. The counterpart to disease intelligence: what a drug is known to
 * do, independent of any disease. The page is arranged to make the point that
 * a candidate is characterised by targets and mechanisms, not by its name.
 */
export function DrugPage() {
  const { state, run } = useDrugProfile();

  return (
    <>
      <Section>
        <PageHead
          stage="02"
          title="Drug intelligence"
          lede="Identity, observed side effects, protein targets, recorded mechanisms and the pathways those targets sit in — assembled from public sources, each one kept with its provenance."
          art="drupe-branch"
        >
          <QueryField
            onSubmit={(q) => void run(q)}
            busy={state.status === "loading"}
            placeholder="Drug name, ChEMBL ID or PubChem CID"
            action="Look up"
            suggestions={["celiprolol", "salbutamol", "metformin"]}
          />
        </PageHead>
      </Section>

      {state.status === "loading" ? (
        <Section>
          <Waiting note={`Looking up ${state.query}`} />
        </Section>
      ) : null}

      {state.status === "error" ? (
        <Section>
          <div className="py-6">
            <Problem error={state.error} onRetry={(q) => void run(q)} />
          </div>
        </Section>
      ) : null}

      {state.status === "success" ? <Profile drug={state.data} /> : null}

      <Section>
        <NextStage from="/drug" />
      </Section>
    </>
  );
}

function Profile({ drug }: { drug: DrugProfile }) {
  const ctx = drug.biological_context;

  return (
    <>
      <Section tone="sunk">
        <div className="py-16">
          <Reveal>
            <div className="flex flex-wrap items-end justify-between gap-6">
              <div>
                <Label tone="ink">Resolved</Label>
                <h2 className="mt-4 text-[clamp(2rem,5vw,3.5rem)] font-semibold">{drug.drug_name}</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <IdChip>{drug.drug_id}</IdChip>
                {drug.chembl_id ? <IdChip>{drug.chembl_id}</IdChip> : null}
                {drug.pubchem_cid ? <IdChip>CID {drug.pubchem_cid}</IdChip> : null}
              </div>
            </div>
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-12 grid gap-10 border-t border-rule pt-10 sm:grid-cols-2 lg:grid-cols-4">
              <Figure value={drug.target_count} caption="Protein targets" />
              <Figure value={drug.mechanisms.length} caption="Recorded mechanisms" />
              <Figure value={ctx.pathways.length} caption="Pathways reached" />
              <Figure value={drug.side_effect_count} caption="Observed side effects" />
            </div>
          </Reveal>
        </div>
      </Section>

      {/* targets and mechanisms — the substance of the page */}
      <Section>
        <Cyanotype art="leaf-sprig" className="absolute -left-24 top-20 w-64 opacity-20" drift />
        <div className="relative py-20">
          <Reveal>
            <Label tone="ink">Targets</Label>
            <h3 className="mt-4 max-w-2xl text-[clamp(1.5rem,3.4vw,2.5rem)] font-semibold">
              The proteins this drug is known to act on
            </h3>
            <p className="mt-4 max-w-xl text-ink-soft">
              These UniProt identifiers are what a disease's genes are matched against. No target, no gene-target
              evidence — the system will say so rather than guess.
            </p>
          </Reveal>

          <Reveal delay={1}>
            <ul className="mt-12">
              {drug.targets.map((t) => (
                <li
                  key={t.target_id}
                  className="grid items-baseline gap-x-6 gap-y-2 border-t border-rule py-5 md:grid-cols-[1.4fr_0.8fr_1fr]"
                >
                  <span className="font-display text-lg font-semibold tracking-tight">
                    {t.target_name ?? t.target_id}
                  </span>
                  <span className="label">{t.action_type ?? "action not recorded"}</span>
                  <span className="flex flex-wrap justify-start gap-2 md:justify-end">
                    {t.uniprot_id ? <IdChip>{t.uniprot_id}</IdChip> : null}
                    <IdChip>{t.target_id}</IdChip>
                  </span>
                </li>
              ))}
              {drug.targets.length === 0 ? (
                <li className="border-t border-rule py-6 text-ink-soft">
                  No targets recorded for this drug in the snapshot. {drug.provenance.target_coverage_note}
                </li>
              ) : null}
            </ul>
          </Reveal>
        </div>
      </Section>

      {drug.mechanisms.length ? (
        <Section tone="navy" railed={false}>
          <div className="relative py-20">
            <Reveal>
              <Label tone="navy">Mechanisms of action</Label>
              <h3 className="mt-4 max-w-2xl text-[clamp(1.5rem,3.4vw,2.5rem)] font-semibold text-navy-text">
                What the record says it does
              </h3>
            </Reveal>
            <Reveal delay={1}>
              <ul className="mt-12 space-y-px">
                {drug.mechanisms.map((m, i) => (
                  <li key={`${m.target_id}-${i}`} className="border-t border-navy-line py-5">
                    <p className="text-[1.0625rem] leading-relaxed text-navy-text">{m.description}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
                      <span className="label label-on-navy">{m.action_type ?? "action not recorded"}</span>
                      <span className="label text-navy-faint">{m.target_name ?? m.target_id}</span>
                      <span className="label text-navy-faint">source · {m.source}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </Section>
      ) : null}

      {/* pathway context */}
      <Section>
        <div className="py-20">
          <Reveal>
            <Label tone="ink">Pathway context</Label>
            <h3 className="mt-4 text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold">
              {ctx.pathway_context_available
                ? "Reactome pathways reached through those targets"
                : "Pathway context unavailable"}
            </h3>
          </Reveal>

          {ctx.pathway_context_available ? (
            <Reveal delay={1}>
              <ul className="mt-10 grid gap-x-12 md:grid-cols-2">
                {ctx.pathways.map((p) => (
                  <li key={p.reactome_id} className="border-t border-rule py-4">
                    <p className="text-[0.9375rem] leading-snug">{p.pathway_name}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="label tabular">{p.supporting_target_count} targets</span>
                      <IdChip>{p.reactome_id}</IdChip>
                    </div>
                  </li>
                ))}
              </ul>
            </Reveal>
          ) : (
            <Reveal delay={1}>
              <p className="mt-6 max-w-xl text-ink-soft">
                {ctx.unavailable_reason ?? "No pathway context could be derived for this drug."}
              </p>
            </Reveal>
          )}
        </div>
      </Section>

      {/* side effects */}
      {drug.side_effects.length ? <SideEffects drug={drug} /> : null}

      {/* provenance */}
      <Section tone="sunk">
        <div className="py-20">
          <Reveal>
            <Label tone="ink">Provenance</Label>
            <h3 className="mt-4 text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold">Sources behind this profile</h3>
          </Reveal>
          <Reveal delay={1}>
            <dl className="mt-10 grid gap-x-14 md:grid-cols-2">
              <Datum term="Identity">{drug.provenance.identity_source}</Datum>
              <Datum term="Targets">{drug.provenance.target_source}</Datum>
              <Datum term="Mechanisms">{drug.provenance.mechanism_source}</Datum>
              <Datum term="Side effects">{drug.provenance.side_effect_source}</Datum>
              <Datum term="Pathways">{drug.provenance.pathway_source}</Datum>
              <Datum term="Pathway derivation">{drug.provenance.pathway_derivation}</Datum>
              <Datum term="Datasets">{drug.provenance.datasets_used.join(", ")}</Datum>
              <Datum term="Optional sources used">
                {drug.provenance.optional_sources_used.length ? drug.provenance.optional_sources_used.join(", ") : "none"}
              </Datum>
            </dl>
          </Reveal>
          <Reveal delay={2}>
            <div className="mt-10">
              <Rule dotted />
              <p className="mt-6 max-w-3xl text-sm leading-relaxed text-ink-soft">
                {drug.provenance.target_coverage_note}
              </p>
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-ink-soft">{drug.provenance.disclaimer}</p>
            </div>
          </Reveal>
        </div>
      </Section>
    </>
  );
}

/** Side effects are the product's namesake, so they get their own field —
 * shown in full only on request because the lists run long. */
function SideEffects({ drug }: { drug: DrugProfile }) {
  const [all, setAll] = useState(false);
  const shown = all ? drug.side_effects : drug.side_effects.slice(0, 36);

  return (
    <Section tone="navy" railed={false}>
      <Cyanotype art="ridges" deep className="absolute -right-24 top-0 w-80 opacity-25 mix-blend-screen" />
      <div className="relative py-20">
        <Reveal>
          <Label tone="navy">Observed side effects</Label>
          <h3 className="mt-4 max-w-2xl text-[clamp(1.5rem,3.4vw,2.5rem)] font-semibold text-navy-text">
            {drug.side_effect_count} recorded effects
          </h3>
          <p className="mt-4 max-w-xl text-navy-muted">
            Each one is a system this molecule demonstrably touches. They are shown as context for the drug's
            reach — the score does not treat a side effect as evidence for a disease.
          </p>
        </Reveal>

        <Reveal delay={1}>
          <ul className="mt-12 flex flex-wrap gap-x-2 gap-y-2">
            {shown.map((s) => (
              <li
                key={s.side_effect_id}
                className="border border-navy-line px-3 py-1.5 text-[0.8125rem] text-navy-text/90"
              >
                {s.side_effect_name}
              </li>
            ))}
          </ul>
          {drug.side_effects.length > 36 ? (
            <button type="button" onClick={() => setAll((v) => !v)} className="btn btn-on-navy bracket mt-8">
              {all ? "Show fewer" : `Show all ${drug.side_effects.length}`}
            </button>
          ) : null}
        </Reveal>
      </div>
    </Section>
  );
}
