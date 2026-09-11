const TEXT =
  "This system provides computational drug-repurposing prioritization based on available biological and model-derived evidence. It does not establish clinical efficacy, safety, treatment suitability, or a cure.";

/** Persistent, unobtrusive-but-visible scientific disclaimer. Never hidden,
 * never collapsed away — required on every screen that shows a score. */
export function DisclaimerBar() {
  return (
    <div className="border-t border-rule bg-paper-raised">
      <div className="frame py-4">
        <p className="flex items-start gap-3 text-[0.6875rem] leading-relaxed text-ink-faint">
          <span aria-hidden className="mt-1 h-1.5 w-1.5 shrink-0 bg-ink-faint" />
          <span className="max-w-4xl">{TEXT}</span>
        </p>
      </div>
    </div>
  );
}
