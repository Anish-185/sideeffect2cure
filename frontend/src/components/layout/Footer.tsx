import { Link } from "react-router-dom";
import { GROUPS, GROUP_LABEL, destinationsIn } from "../../content/nav";
import { Cyanotype, DigitArt } from "../ui";

export function Footer() {
  return (
    <footer className="relative overflow-hidden bg-navy text-navy-text">
      <DigitArt
        art="ridges"
        className="fade-mask-b absolute -top-6 right-0 opacity-[0.13]"
        style={{ fontSize: "0.44rem" }}
      />
      <Cyanotype
        art="leaf-sprig"
        deep
        className="absolute -bottom-16 -left-16 w-80 opacity-25 mix-blend-screen"
      />

      <div className="frame relative py-16">
        <div className="grid gap-12 md:grid-cols-[1.2fr_2fr]">
          <div>
            <p className="font-display text-2xl font-semibold tracking-tight">
              SideEffect2Cure<span className="text-navy-muted"> AI</span>
            </p>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-navy-muted">
              A drug-repurposing intelligence pipeline. Public biomedical data in, traceable evidence out.
            </p>
          </div>

          <div className="grid gap-8 sm:grid-cols-3">
            {GROUPS.map((group) => (
              <div key={group}>
                <p className="label label-on-navy">{GROUP_LABEL[group]}</p>
                <ul className="mt-4 space-y-2">
                  {destinationsIn(group).map((d) => (
                    <li key={d.path}>
                      <Link to={d.path} className="text-sm text-navy-text/80 transition-colors hover:text-navy-text">
                        {d.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-14 flex flex-wrap items-center justify-between gap-4 border-t border-navy-line pt-6">
          <p className="label label-on-navy">Research prototype · not clinical decision support</p>
          <Link to="/how-it-works" className="label label-on-navy hover:text-navy-text">
            How it works →
          </Link>
        </div>
      </div>
    </footer>
  );
}
