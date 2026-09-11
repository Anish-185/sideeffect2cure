import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { DESTINATIONS, GROUPS, GROUP_LABEL, destinationsIn } from "../../content/nav";
import { useDiscovery } from "../../state/DiscoveryContext";

/**
 * One panel holds every capability in pipeline order. The product's whole
 * argument is its depth, so the nav shows the depth rather than hiding nine
 * pages behind a generic "Dashboard" link.
 */
export function NavBar() {
  const [open, setOpen] = useState(false);
  const { state, lastQuery } = useDiscovery();
  const location = useLocation();
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => setOpen(false), [location.pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const activeDisease = state.status === "success" ? state.data.disease.disease_name : null;

  return (
    <div ref={panelRef} className="sticky top-0 z-50">
      <nav className="rule-b bg-paper-raised/90 backdrop-blur-md">
        <div className="frame flex h-16 items-center justify-between gap-6">
          <Link to="/" className="group flex items-center gap-3" aria-label="SideEffect2Cure AI — home">
            <Mark />
            {/* The wordmark is the first thing to go on a narrow screen — the
             * mark still identifies the product, and the nav has to keep both
             * the capabilities menu and the CTA reachable. */}
            <span className="hidden font-display text-[0.9375rem] font-semibold tracking-tight xs:inline">
              SideEffect2Cure<span className="text-blue"> AI</span>
            </span>
          </Link>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              className="label px-3 py-2 text-ink transition-colors hover:text-blue"
            >
              Capabilities <span aria-hidden className="ml-1 inline-block">{open ? "−" : "+"}</span>
            </button>
            <NavLink
              to="/how-it-works"
              className={({ isActive }) =>
                `label hidden px-3 py-2 transition-colors sm:block ${isActive ? "text-blue" : "text-ink hover:text-blue"}`
              }
            >
              How it works
            </NavLink>
            <Link to="/candidates" className="btn btn-primary ml-2">
              <span className="hidden sm:inline">
                {activeDisease ?? lastQuery ? "Open analysis" : "Run analysis"}
              </span>
              <span className="sm:hidden">{activeDisease ?? lastQuery ? "Open" : "Run"}</span>
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </nav>

      {open ? (
        <div className="rule-b bg-paper-raised shadow-[0_24px_48px_-24px_rgba(10,16,36,0.25)]">
          <div className="frame grid gap-x-10 gap-y-8 py-10 md:grid-cols-3">
            {GROUPS.map((group) => (
              <div key={group}>
                <p className="label label-ink">{GROUP_LABEL[group]}</p>
                <ul className="mt-4 space-y-px">
                  {destinationsIn(group).map((d) => (
                    <li key={d.path}>
                      <Link
                        to={d.path}
                        className="group block border-t border-rule py-3 transition-colors hover:border-blue"
                      >
                        <span className="flex items-baseline gap-3">
                          <span className="label tabular">{d.stage}</span>
                          <span className="font-display text-[0.9375rem] font-semibold tracking-tight transition-colors group-hover:text-blue">
                            {d.title}
                          </span>
                        </span>
                        <span className="mt-1 block pl-9 text-[0.8125rem] leading-snug text-ink-soft">
                          {d.blurb}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="rule-t bg-paper">
            <div className="frame flex flex-wrap items-center justify-between gap-4 py-4">
              <p className="label">
                {DESTINATIONS.length} capabilities · one pipeline · every number traced to a source
              </p>
              <Link to="/how-it-works" className="label label-ink hover:underline">
                See the architecture →
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** The mark: a molecule reread as a side effect turning into a lead — one
 * node branching into three, the middle branch carried through. */
function Mark() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden className="shrink-0">
      <g stroke="var(--color-blue)" strokeWidth="1.6" fill="none" strokeLinecap="square">
        <path d="M4 13h6M16 13h6M13 4v6M13 16v6" />
        <path d="M8.6 8.6l3 3M17.4 17.4l-3-3" opacity="0.45" />
      </g>
      <circle cx="13" cy="13" r="2.6" fill="var(--color-blue)" />
    </svg>
  );
}
