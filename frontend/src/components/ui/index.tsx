/**
 * The primitive vocabulary the whole site is composed from.
 *
 * Deliberately small: a framed section, a mono label, a rule, a meter, and
 * the two artwork primitives. Pages are built by arranging these against
 * whitespace rather than by nesting cards.
 */
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { useReveal } from "../../hooks/useScrollMotion";

// -- section ------------------------------------------------------------

export function Section({
  children,
  tone = "paper",
  railed = true,
  className = "",
  id,
}: {
  children: ReactNode;
  tone?: "paper" | "navy" | "sunk";
  railed?: boolean;
  className?: string;
  id?: string;
}) {
  const bg =
    tone === "navy" ? "bg-navy text-navy-text" : tone === "sunk" ? "bg-paper-sunk text-ink" : "bg-paper text-ink";
  return (
    <section id={id} className={`relative overflow-hidden ${bg} ${className}`}>
      <div className={`frame ${railed ? "frame--railed" : ""} relative`}>{children}</div>
    </section>
  );
}

/** A section's opening line: mono kicker over a display heading. */
export function SectionHead({
  kicker,
  title,
  lede,
  tone = "paper",
  align = "left",
}: {
  kicker: string;
  title: ReactNode;
  lede?: ReactNode;
  tone?: "paper" | "navy";
  align?: "left" | "center";
}) {
  const onNavy = tone === "navy";
  return (
    <header className={align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-3xl"}>
      <p className={`label ${onNavy ? "label-on-navy" : "label-ink"}`}>{kicker}</p>
      <h2
        className={`mt-5 text-[clamp(2rem,4.4vw,3.5rem)] font-semibold ${onNavy ? "text-navy-text" : "text-ink"}`}
      >
        {title}
      </h2>
      {lede ? (
        <p
          className={`mt-5 text-[1.0625rem] leading-relaxed ${onNavy ? "text-navy-muted" : "text-ink-soft"} ${
            align === "center" ? "mx-auto" : ""
          } max-w-2xl`}
        >
          {lede}
        </p>
      ) : null}
    </header>
  );
}

// -- reveal -------------------------------------------------------------

export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: 0 | 1 | 2 | 3 | 4;
  className?: string;
  as?: "div" | "li" | "section" | "article";
}) {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  const delayClass = delay ? `reveal-${delay}` : "";
  return (
    <Tag
      ref={ref as never}
      className={`reveal ${delayClass} ${revealed ? "is-in" : ""} ${className}`}
    >
      {children}
    </Tag>
  );
}

// -- labels and rules ---------------------------------------------------

export function Label({
  children,
  tone = "faint",
  className = "",
}: {
  children: ReactNode;
  tone?: "faint" | "ink" | "navy";
  className?: string;
}) {
  const toneClass = tone === "ink" ? "label-ink" : tone === "navy" ? "label-on-navy" : "";
  return <p className={`label ${toneClass} ${className}`}>{children}</p>;
}

export function Rule({ tone = "paper", dotted = false }: { tone?: "paper" | "navy"; dotted?: boolean }) {
  return (
    <hr
      className="border-0 border-t"
      style={{
        borderTopWidth: 1,
        borderTopStyle: dotted ? "dashed" : "solid",
        borderTopColor: tone === "navy" ? "var(--color-navy-line)" : "var(--color-rule)",
      }}
    />
  );
}

// -- artwork ------------------------------------------------------------

/**
 * A cyanotype cutout placed as ambient artwork. Always decorative — every
 * one of these is a derived asset, never a carrier of information — so it is
 * hidden from assistive tech and never intercepts pointer events.
 */
export function Cyanotype({
  art,
  deep = false,
  className = "",
  style,
  drift = false,
}: {
  art: string;
  deep?: boolean;
  className?: string;
  style?: CSSProperties;
  drift?: boolean;
}) {
  return (
    <img
      src={`/art/${art}${deep ? "-deep" : ""}.png`}
      alt=""
      aria-hidden
      loading="lazy"
      draggable={false}
      className={`pointer-events-none select-none ${drift ? "drift" : ""} ${className}`}
      style={style}
    />
  );
}

/**
 * The numeral texture from the reference's full-bleed bands. The asset is a
 * plain text file so it streams as text rather than as another image, and it
 * degrades to nothing if the fetch fails.
 */
export function DigitArt({ art, className = "", style }: { art: string; className?: string; style?: CSSProperties }) {
  const [text, setText] = useState("");

  useEffect(() => {
    let live = true;
    fetch(`/art/${art}.txt`)
      .then((r) => (r.ok ? r.text() : ""))
      .then((t) => {
        if (live) setText(t);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [art]);

  if (!text) return null;
  return (
    <pre aria-hidden className={`digit-art ${className}`} style={style}>
      {text}
    </pre>
  );
}

// -- data display -------------------------------------------------------

/** A horizontal evidence meter. Width animates from zero once on screen. */
export function Meter({
  value,
  color,
  tone = "paper",
  height = 6,
}: {
  value: number;
  color: string;
  tone?: "paper" | "navy";
  height?: number;
}) {
  const { ref, revealed } = useReveal<HTMLDivElement>(0.3);
  return (
    <div
      ref={ref}
      className="w-full overflow-hidden"
      style={{ height, background: tone === "navy" ? "var(--color-navy-line)" : "var(--color-rule-soft)" }}
    >
      <div
        className="h-full"
        style={{
          width: revealed ? `${Math.max(0, Math.min(1, value)) * 100}%` : "0%",
          background: color,
          transition: "width 900ms cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      />
    </div>
  );
}

/** A label/value pair on a hairline — the site's substitute for a table row. */
export function Datum({
  term,
  children,
  tone = "paper",
}: {
  term: string;
  children: ReactNode;
  tone?: "paper" | "navy";
}) {
  return (
    <div
      className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-t py-3"
      style={{ borderColor: tone === "navy" ? "var(--color-navy-line)" : "var(--color-rule)" }}
    >
      <dt className={`label ${tone === "navy" ? "label-on-navy" : ""}`}>{term}</dt>
      <dd
        className={`tabular text-right text-sm ${tone === "navy" ? "text-navy-text" : "text-ink"}`}
      >
        {children}
      </dd>
    </div>
  );
}

/** A monospace identifier, so provenance always looks like provenance. */
export function IdChip({ children }: { children: ReactNode }) {
  return <span className="id-chip">{children}</span>;
}

/** A big number set at display size — the site's headline statistic. */
export function Figure({
  value,
  caption,
  tone = "paper",
}: {
  value: ReactNode;
  caption: string;
  tone?: "paper" | "navy";
}) {
  return (
    <div>
      <p
        className={`tabular font-display text-[clamp(2.25rem,4vw,3.25rem)] font-semibold leading-none tracking-tight ${
          tone === "navy" ? "text-navy-text" : "text-ink"
        }`}
      >
        {value}
      </p>
      <p className={`label mt-3 ${tone === "navy" ? "label-on-navy" : ""}`}>{caption}</p>
    </div>
  );
}

// -- counting number ----------------------------------------------------

/** Counts up to `value` once visible. Skipped entirely under reduced motion
 * by useReveal, which reports revealed immediately in that case. */
export function CountUp({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const { ref, revealed } = useReveal<HTMLSpanElement>(0.4);
  const [shown, setShown] = useState(0);
  const frame = useRef(0);

  useEffect(() => {
    if (!revealed) return;
    const start = performance.now();
    const duration = 900;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      setShown(value * (1 - (1 - t) ** 3));
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [revealed, value]);

  return (
    <span ref={ref} className="tabular">
      {shown.toFixed(decimals)}
    </span>
  );
}
