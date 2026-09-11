/**
 * The chrome every analysis page shares: the query field, the states a
 * backend call can land in, and the forward link to the next stage.
 *
 * None of this interprets scientific values — it only routes between the
 * backend's own states so each page can stay about its own subject.
 */
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ApiError } from "../api/client";
import { nextDestination } from "../content/nav";
import { useDiscovery, useFocusedCandidate } from "../state/DiscoveryContext";
import { Cyanotype, Label, Rule } from "./ui";

// -- query field ---------------------------------------------------------

export function QueryField({
  onSubmit,
  placeholder,
  initial = "",
  busy = false,
  suggestions = [],
  action = "Run",
}: {
  onSubmit: (value: string) => void;
  placeholder: string;
  initial?: string;
  busy?: boolean;
  suggestions?: string[];
  action?: string;
}) {
  const [value, setValue] = useState(initial);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed) onSubmit(trimmed);
  };

  return (
    <div>
      <form onSubmit={submit} className="flex flex-wrap items-stretch gap-px bg-rule">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          // basis keeps the field readable: below it the row wraps and the
          // button drops to its own line rather than squeezing the input.
          className="min-w-0 flex-1 basis-64 bg-paper-raised px-5 py-4 font-display text-lg tracking-tight outline-none placeholder:text-ink-faint"
        />
        <button type="submit" className="btn btn-primary grow justify-center px-7 sm:grow-0" disabled={busy || !value.trim()}>
          {busy ? "Working" : action}
          <span aria-hidden>→</span>
        </button>
      </form>

      {suggestions.length ? (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          <Label>Try</Label>
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setValue(s);
                onSubmit(s);
              }}
              className="text-[0.8125rem] text-ink-soft underline decoration-rule underline-offset-4 transition-colors hover:text-blue hover:decoration-blue"
            >
              {s}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// -- states --------------------------------------------------------------

export function Waiting({ note }: { note: string }) {
  return (
    <div className="flex items-center gap-4 py-16">
      <span className="relative flex h-2.5 w-2.5">
        <span className="pulse-slow absolute inline-flex h-full w-full bg-blue" />
      </span>
      <p className="label">{note}</p>
    </div>
  );
}

/**
 * Renders the backend's own error shapes. `ambiguous` and `not_supported`
 * carry real alternatives, so they become choices the user can act on rather
 * than a dead end.
 */
export function Problem({ error, onRetry }: { error: ApiError; onRetry?: (query: string) => void }) {
  const detail = error.detail;
  const structured = typeof detail === "object" ? detail : null;
  const status = structured && "status" in structured ? structured.status : null;

  const options: string[] =
    status === "ambiguous" && "candidates" in structured!
      ? structured!.candidates.map((c) => ("disease_name" in c ? c.disease_name : c.drug_name))
      : status === "not_supported" && "suggestions" in structured!
        ? structured!.suggestions
        : [];

  return (
    <div className="max-w-xl border-l-2 border-negative py-2 pl-5">
      <Label>{status ? status.replace(/_/g, " ") : "Could not complete"}</Label>
      <p className="mt-3 text-[1.0625rem] leading-relaxed text-ink">{error.message}</p>
      {options.length && onRetry ? (
        <div className="mt-5 flex flex-wrap gap-2">
          {options.slice(0, 8).map((option) => (
            <button key={option} type="button" onClick={() => onRetry(option)} className="btn btn-ghost bracket">
              {option}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Shown when a page needs a pipeline run that has not happened yet. */
export function NeedsRun({ what }: { what: string }) {
  return (
    <div className="relative flex flex-col items-start gap-6 py-16">
      <Cyanotype art="inflorescence" className="absolute -top-8 right-0 w-44 opacity-20" drift />
      <Label>No analysis yet</Label>
      <p className="max-w-lg font-display text-[1.75rem] font-semibold leading-tight tracking-tight">
        Run a disease to see {what}.
      </p>
      <Link to="/candidates" className="btn btn-primary">
        Choose a disease <span aria-hidden>→</span>
      </Link>
    </div>
  );
}

// -- candidate context ---------------------------------------------------

/**
 * The focused disease and candidate, with a picker. Rendered by every page
 * downstream of ranking so the reader always knows which pair the numbers on
 * screen belong to, and can change it without going back.
 */
export function CandidateBar() {
  const { state } = useDiscovery();
  const { candidate, candidates, select } = useFocusedCandidate();
  if (state.status !== "success" || !candidate) return null;

  return (
    <div className="rule-b rule-t bg-paper-raised">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4 py-5">
        <div>
          <Label>Disease</Label>
          <p className="mt-1.5 font-display text-lg font-semibold tracking-tight">{state.data.disease.disease_name}</p>
        </div>

        <div className="min-w-0">
          <Label>Candidate</Label>
          <select
            value={candidate.drug_id}
            onChange={(e) => select(e.target.value)}
            aria-label="Focused candidate"
            className="mt-1 block w-full max-w-xs cursor-pointer border-b border-rule bg-transparent py-1 font-display text-lg font-semibold tracking-tight text-blue outline-none"
          >
            {candidates.map((c) => (
              <option key={c.drug_id} value={c.drug_id}>
                {String(c.rank).padStart(2, "0")} · {c.drug_name}
              </option>
            ))}
          </select>
        </div>

        <div className="ml-auto flex items-center gap-6">
          <div className="text-right">
            <Label>Score</Label>
            <p className="tabular mt-1.5 font-display text-lg font-semibold tracking-tight">
              {candidate.repurposing_score.toFixed(1)}
            </p>
          </div>
          <Link to="/candidates" className="label label-ink hover:underline">
            All candidates →
          </Link>
        </div>
      </div>
    </div>
  );
}

// -- page frame ----------------------------------------------------------

export function PageHead({
  stage,
  title,
  lede,
  art,
  children,
}: {
  stage: string;
  title: string;
  lede: string;
  art: string;
  children?: ReactNode;
}) {
  return (
    <div className="relative grid gap-10 py-16 md:grid-cols-[1.55fr_1fr] md:items-end md:py-24">
      <div>
        <Label tone="ink">Stage {stage}</Label>
        <h1 className="mt-5 text-[clamp(2.5rem,5.5vw,4.25rem)] font-semibold">{title}</h1>
        <p className="mt-6 max-w-xl text-[1.0625rem] leading-relaxed text-ink-soft">{lede}</p>
        {children ? <div className="mt-9 max-w-xl">{children}</div> : null}
      </div>
      <div className="relative hidden h-full min-h-56 md:block">
        <Cyanotype
          art={art}
          drift
          className="fade-mask-radial absolute bottom-0 right-0 w-[min(22rem,100%)] opacity-70"
        />
      </div>
    </div>
  );
}

/** The forward link, so the pipeline can be walked end to end by clicking. */
export function NextStage({ from }: { from: string }) {
  const next = nextDestination(from);
  if (!next) return null;
  return (
    <div className="py-14">
      <Rule />
      <Link to={next.path} className="group flex flex-wrap items-end justify-between gap-4 pt-6">
        <div>
          <Label>Next · stage {next.stage}</Label>
          <p className="mt-3 font-display text-[clamp(1.5rem,3vw,2.25rem)] font-semibold tracking-tight transition-colors group-hover:text-blue">
            {next.title}
          </p>
          <p className="mt-2 max-w-md text-sm text-ink-soft">{next.blurb}</p>
        </div>
        <span aria-hidden className="label label-ink pb-2 transition-transform group-hover:translate-x-1">
          →
        </span>
      </Link>
    </div>
  );
}
