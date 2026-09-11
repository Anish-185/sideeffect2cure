import { useState } from "react";
import { Link } from "react-router-dom";
import { Cyanotype, DigitArt, Label, Reveal, Rule, Section, SectionHead } from "../components/ui";
import { PIPELINE_LEVELS, type PipelineLevel } from "../content/pipelineLevels";
import { DESTINATIONS } from "../content/nav";

/**
 * The architecture, walkable. Each level opens to show what it consumes,
 * what it emits and why it exists — which is the part that makes the depth
 * of the system legible to someone who will not read the source.
 */
export function HowItWorksPage() {
  const [open, setOpen] = useState<string | null>(PIPELINE_LEVELS[0]?.n ?? null);

  return (
    <>
      <Section>
        <Cyanotype
          art="column"
          drift
          className="fade-mask-radial absolute -right-8 top-0 w-[min(24rem,40vw)] opacity-50"
        />
        <div className="relative grid gap-10 py-20 md:py-28">
          <div className="max-w-3xl">
            <Reveal>
              <Label tone="ink">Architecture</Label>
            </Reveal>
            <Reveal delay={1}>
              <h1 className="mt-6 text-[clamp(2.5rem,6.5vw,4.75rem)] font-semibold">
                Ten levels, each one
                <br />
                accountable to the last.
              </h1>
            </Reveal>
            <Reveal delay={2}>
              <p className="mt-8 max-w-xl text-[1.125rem] leading-relaxed text-ink-soft">
                The pipeline is built so that any number on any page can be walked backwards to the row it came
                from. Open a level to see what it consumes, what it produces, and why it exists.
              </p>
            </Reveal>
          </div>
        </div>
      </Section>

      {/* the levels */}
      <Section>
        <div className="py-16">
          <ol>
            {PIPELINE_LEVELS.map((level, i) => (
              <Reveal key={level.n} as="li" delay={((i % 3) + 1) as 1 | 2 | 3}>
                <LevelRow
                  level={level}
                  open={open === level.n}
                  onToggle={() => setOpen((c) => (c === level.n ? null : level.n))}
                />
              </Reveal>
            ))}
          </ol>
        </div>
      </Section>

      {/* principles */}
      <Section tone="navy" railed={false}>
        <DigitArt
          art="inflorescence"
          className="fade-mask-r absolute -top-8 left-0 opacity-[0.16]"
          style={{ fontSize: "0.48rem" }}
        />
        <div className="relative py-24">
          <Reveal>
            <SectionHead
              tone="navy"
              kicker="Design rules"
              title="What the pipeline is not allowed to do."
              lede="These constraints are why the output can be trusted to mean what it says."
            />
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-16 grid gap-x-14 gap-y-10 md:grid-cols-2">
              {[
                [
                  "No fuzzy matching",
                  "Diseases and drugs resolve on identifiers or exact names. An ambiguous query returns the alternatives rather than silently picking one.",
                ],
                [
                  "No invented relationships",
                  "A gene meets a target only through a shared HGNC id; a pathway overlaps only through a shared Reactome id.",
                ],
                [
                  "No hidden signal",
                  "Everything that moves the score is displayed alongside it, with its weight and its contribution in points.",
                ],
                [
                  "No filled gaps",
                  "Missing evidence is reported as missing and the weights renormalise over what is actually there.",
                ],
                [
                  "No clinical language",
                  "The score prioritises candidates for investigation. It is never described as efficacy or probability of treatment.",
                ],
                [
                  "No ungrounded prose",
                  "The written explanation is generated from pipeline values and validated against them before display.",
                ],
              ].map(([title, body]) => (
                <div key={title} className="border-t border-navy-line pt-6">
                  <p className="font-display text-lg font-semibold tracking-tight text-navy-text">{title}</p>
                  <p className="mt-3 leading-relaxed text-navy-muted">{body}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </Section>

      {/* where to go */}
      <Section>
        <div className="py-24">
          <Reveal>
            <SectionHead
              kicker="See it running"
              title="Each level has a page."
              lede="The architecture above is not a diagram of intent — every stage below is something you can open and interrogate right now."
            />
          </Reveal>
          <Reveal delay={1}>
            <ul className="mt-14">
              {DESTINATIONS.map((d) => (
                <li key={d.path}>
                  <Link
                    to={d.path}
                    className="group grid items-baseline gap-x-6 gap-y-1 border-t border-rule py-5 transition-colors hover:border-blue md:grid-cols-[4rem_1fr_1.2fr]"
                  >
                    <span className="label tabular">{d.stage}</span>
                    <span className="font-display text-[1.125rem] font-semibold tracking-tight transition-colors group-hover:text-blue">
                      {d.title}
                    </span>
                    <span className="text-sm leading-relaxed text-ink-soft">{d.blurb}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </Section>
    </>
  );
}

function LevelRow({ level, open, onToggle }: { level: PipelineLevel; open: boolean; onToggle: () => void }) {
  return (
    <div className="border-t transition-colors" style={{ borderColor: open ? "var(--color-blue)" : "var(--color-rule)" }}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="group grid w-full items-baseline gap-x-8 gap-y-2 py-7 text-left md:grid-cols-[4rem_1fr_2rem]"
      >
        <span className="label tabular">{level.n}</span>
        <span>
          <span
            className="block font-display text-[clamp(1.375rem,3.2vw,2.25rem)] font-semibold tracking-tight transition-colors group-hover:text-blue"
            style={open ? { color: "var(--color-blue)" } : undefined}
          >
            {level.name}
          </span>
          <span className="mt-2 block max-w-2xl text-[0.9375rem] leading-relaxed text-ink-soft">{level.what}</span>
        </span>
        <span aria-hidden className="label text-right text-lg">
          {open ? "−" : "+"}
        </span>
      </button>

      {open ? (
        <div className="grid gap-x-10 gap-y-8 pb-10 md:grid-cols-[4rem_1fr] ">
          <span aria-hidden />
          <div className="grid gap-x-12 gap-y-8 md:grid-cols-3">
            <Detail term="Data it uses" value={level.data} />
            <Detail term="What it produces" value={level.output} />
            <Detail term="Why it matters" value={level.why} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Detail({ term, value }: { term: string; value: string }) {
  return (
    <div>
      <Label tone="ink">{term}</Label>
      <Rule />
      <p className="mt-3 text-[0.875rem] leading-relaxed text-ink-soft">{value}</p>
    </div>
  );
}
