import { Link, useNavigate } from "react-router-dom";
import { QueryField } from "../components/analysis";
import { Cyanotype, CountUp, DigitArt, Figure, Label, Reveal, Rule, Section, SectionHead } from "../components/ui";
import { DESTINATIONS, GROUPS, GROUP_LABEL, destinationsIn } from "../content/nav";
import { formatScore } from "../lib/format";
import { useDiscovery } from "../state/DiscoveryContext";

/** The chain the product actually walks, told as a sentence the eye can follow. */
const CHAIN = [
  "Disease",
  "Genes",
  "Targets",
  "Pathways",
  "Drugs",
  "Model",
  "Fusion",
  "Candidates",
  "Graph",
  "Explanation",
];

export function HomePage() {
  const { state, run } = useDiscovery();
  const navigate = useNavigate();

  const onRun = (query: string) => {
    void run(query);
    navigate("/candidates");
  };

  return (
    <>
      <Hero onRun={onRun} busy={state.status === "loading"} />
      <ChainBand />
      <Premise />
      <LiveResult />
      <CapabilityIndex />
      <Honesty />
    </>
  );
}

// -- hero ----------------------------------------------------------------

function Hero({ onRun, busy }: { onRun: (q: string) => void; busy: boolean }) {
  return (
    <Section className="pb-0">
      <Cyanotype
        art="lotus"
        drift
        className="fade-mask-radial pointer-events-none absolute -right-10 top-4 w-[min(34rem,48vw)] opacity-60 md:opacity-80"
      />

      <div className="relative grid items-end gap-y-12 pb-20 pt-16 md:pb-28 md:pt-24">
        <div className="max-w-3xl">
          <Reveal>
            <span className="bracket inline-flex items-center gap-3 bg-paper-raised px-4 py-2">
              <span className="h-1.5 w-1.5 bg-blue" aria-hidden />
              <span className="label">Drug repurposing · research prototype</span>
            </span>
          </Reveal>

          <Reveal delay={1}>
            <h1 className="mt-9 text-[clamp(2.75rem,7.2vw,5.75rem)] font-semibold">
              Discover hidden
              <br />
              possibilities in
              <br />
              <span className="text-blue">existing drugs.</span>
            </h1>
          </Reveal>

          <Reveal delay={2}>
            <p className="mt-8 max-w-xl text-[1.125rem] leading-relaxed text-ink-soft">
              Start from a disease. SideEffect2Cure AI walks its genes, its targets and its pathways through
              public biomedical data, scores every drug already in the world against that biology, and shows
              you the evidence behind each one — not just the answer.
            </p>
          </Reveal>

          <Reveal delay={3}>
            <div className="mt-10 max-w-xl">
              <QueryField
                onSubmit={onRun}
                busy={busy}
                placeholder="Enter a disease — asthma, psoriasis…"
                action="Run pipeline"
                suggestions={["asthma", "psoriasis", "type 2 diabetes mellitus"]}
              />
            </div>
          </Reveal>

          <Reveal delay={4}>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
              <Link to="/how-it-works" className="label label-ink hover:underline">
                See how it works →
              </Link>
              <Link to="/graph" className="label hover:text-blue">
                Open the evidence graph →
              </Link>
            </div>
          </Reveal>
        </div>
      </div>
    </Section>
  );
}

// -- the chain -----------------------------------------------------------

function ChainBand() {
  return (
    <Section tone="navy" railed={false}>
      <DigitArt
        art="lotus"
        className="fade-mask-r absolute -top-10 left-0 opacity-[0.18]"
        style={{ fontSize: "0.5rem" }}
      />

      <div className="relative py-20 md:py-28">
        <Reveal>
          <SectionHead
            tone="navy"
            kicker="The path from a disease to a candidate"
            title="Ten stages. Every one of them shows its work."
            lede="Nothing here is a black box that emits a number. Each stage takes a named input, produces a named output, and keeps the identifiers that connect the two."
          />
        </Reveal>

        <Reveal delay={1}>
          <ol className="mt-16 flex flex-wrap items-center gap-x-3 gap-y-5">
            {CHAIN.map((step, i) => (
              <li key={step} className="flex items-center gap-3">
                <span className="font-display text-[clamp(1.125rem,2.4vw,1.875rem)] font-semibold tracking-tight text-navy-text">
                  {step}
                </span>
                {i < CHAIN.length - 1 ? (
                  <span aria-hidden className="text-navy-faint">
                    →
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </Reveal>

        <Reveal delay={2}>
          <div className="mt-16 grid gap-10 border-t border-navy-line pt-10 sm:grid-cols-3">
            <Figure tone="navy" value="3" caption="Independent evidence families" />
            <Figure tone="navy" value="0" caption="Values invented by this frontend" />
            <Figure tone="navy" value={<CountUp value={DESTINATIONS.length} />} caption="Capabilities you can open" />
          </div>
        </Reveal>
      </div>
    </Section>
  );
}

// -- premise -------------------------------------------------------------

function Premise() {
  return (
    <Section>
      <Cyanotype art="drupe-branch" className="absolute -left-24 top-24 w-72 opacity-20" drift />

      <div className="relative grid gap-16 py-24 md:grid-cols-[1fr_1.15fr]">
        <Reveal>
          <SectionHead
            kicker="The premise"
            title={
              <>
                A side effect is a drug
                <br />
                doing something real.
              </>
            }
          />
        </Reveal>

        <Reveal delay={1} className="space-y-8 self-center">
          <p className="text-[1.125rem] leading-relaxed text-ink-soft">
            Every unwanted effect is evidence that a molecule touches a biological system it was never
            prescribed for. That is the same signal a repurposing search is looking for — read in the other
            direction.
          </p>
          <p className="text-[1.125rem] leading-relaxed text-ink-soft">
            So the system characterises drugs by what they actually do: the proteins they bind, the
            mechanisms recorded against them, the pathways those proteins sit in, and the side effects
            already observed. Then it asks which of those drugs meet a given disease's biology.
          </p>
          <Rule />
          <p className="text-[0.9375rem] leading-relaxed text-ink-soft">
            <span className="font-medium text-ink">It is not predicting from a name.</span> A candidate only
            appears because specific identifiers matched — and the page will show you which ones.
          </p>
        </Reveal>
      </div>
    </Section>
  );
}

// -- live result ---------------------------------------------------------

/** Only rendered once a real run exists. The homepage never shows numbers it
 * has not received from the backend. */
function LiveResult() {
  const { state } = useDiscovery();
  if (state.status !== "success") return null;

  const { disease, candidate_summary: summary, ranked } = state.data;
  const top = ranked.candidates[0];

  return (
    <Section tone="sunk">
      <div className="py-20">
        <Reveal>
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <Label tone="ink">Your last run</Label>
              <h2 className="mt-4 text-[clamp(1.75rem,4vw,3rem)] font-semibold">{disease.disease_name}</h2>
            </div>
            <Link to="/candidates" className="btn btn-ghost bracket">
              Open the analysis <span aria-hidden>→</span>
            </Link>
          </div>
        </Reveal>

        <Reveal delay={1}>
          <div className="mt-12 grid gap-10 border-t border-rule pt-10 sm:grid-cols-2 lg:grid-cols-4">
            <Figure value={<CountUp value={disease.gene_count} />} caption="Associated genes" />
            <Figure value={<CountUp value={disease.pathway_count} />} caption="Derived pathways" />
            <Figure value={<CountUp value={summary.candidates_discovered} />} caption="Candidates discovered" />
            <Figure value={<CountUp value={summary.candidates_ranked} />} caption="Candidates ranked" />
          </div>
        </Reveal>

        {top ? (
          <Reveal delay={2}>
            <div className="mt-12 border-t border-rule pt-10">
              <Label>Top ranked</Label>
              <div className="mt-4 flex flex-wrap items-baseline gap-x-6 gap-y-2">
                <p className="font-display text-[clamp(1.75rem,4vw,2.75rem)] font-semibold tracking-tight">
                  {top.drug_name}
                </p>
                <p className="tabular text-lg text-blue">{formatScore(top.repurposing_score)} / 100</p>
              </div>
              <p className="mt-3 max-w-xl text-sm text-ink-soft">
                Prioritised for further investigation from {top.generation_methods.join(" and ")} evidence.
                This is a research score, not a measure of clinical efficacy.
              </p>
            </div>
          </Reveal>
        ) : null}
      </div>
    </Section>
  );
}

// -- capability index ----------------------------------------------------

function CapabilityIndex() {
  return (
    <Section>
      <div className="py-24">
        <Reveal>
          <SectionHead
            kicker="Everything you can open"
            title="Nine capabilities, not one dashboard."
            lede="Each stage of the pipeline has its own page, because each one answers a different question and carries its own evidence."
          />
        </Reveal>

        <div className="mt-16 space-y-16">
          {GROUPS.map((group, gi) => (
            <Reveal key={group} delay={((gi % 3) + 1) as 1 | 2 | 3}>
              <div>
                <Label tone="ink">{GROUP_LABEL[group]}</Label>
                <ul className="mt-5">
                  {destinationsIn(group).map((d) => (
                    <li key={d.path}>
                      <Link
                        to={d.path}
                        className="group grid items-baseline gap-x-6 gap-y-2 border-t border-rule py-6 transition-colors hover:border-blue md:grid-cols-[4rem_1fr_1.2fr]"
                      >
                        <span className="label tabular">{d.stage}</span>
                        <span className="font-display text-[clamp(1.25rem,2.6vw,1.75rem)] font-semibold tracking-tight transition-colors group-hover:text-blue">
                          {d.title}
                        </span>
                        <span className="text-[0.9375rem] leading-relaxed text-ink-soft">{d.blurb}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </Section>
  );
}

// -- honesty -------------------------------------------------------------

function Honesty() {
  return (
    <Section tone="navy" railed={false}>
      <Cyanotype art="ridges" deep className="absolute -right-20 top-0 w-96 opacity-30 mix-blend-screen" />

      <div className="relative grid gap-14 py-24 md:grid-cols-[1fr_1fr]">
        <Reveal>
          <SectionHead
            tone="navy"
            kicker="What this is, precisely"
            title={
              <>
                A prioritisation tool.
                <br />
                Not a claim about treatment.
              </>
            }
          />
        </Reveal>

        <Reveal delay={1} className="self-center space-y-6">
          {[
            "The repurposing score ranks candidates for further investigation. It is not efficacy, not probability of treatment, and not a cure.",
            "The model's output is one signal among three, weighted alongside gene-target and pathway evidence — and shown separately from them everywhere.",
            "Missing evidence is reported as missing. The system never fills a gap with an assumption.",
            "The AI explanation narrates values the pipeline produced, and is validated against them before it is shown.",
          ].map((line) => (
            <div key={line} className="border-t border-navy-line pt-5">
              <p className="text-[1.0625rem] leading-relaxed text-navy-muted">{line}</p>
            </div>
          ))}
        </Reveal>
      </div>
    </Section>
  );
}
