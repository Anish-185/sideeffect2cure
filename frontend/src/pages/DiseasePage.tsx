import { useState } from "react";
import { NextStage, PageHead, Problem, QueryField, Waiting } from "../components/analysis";
import { Cyanotype, Datum, Figure, IdChip, Label, Meter, Reveal, Rule, Section } from "../components/ui";
import { useDiseaseProfile } from "../hooks/useDiseaseProfile";
import type { DiseaseProfile, GeneAssociation, PathwayAssociation } from "../api/types";

/**
 * Stage 01. Answers one question: what does the system actually know about
 * this disease before any drug is considered?
 */
export function DiseasePage() {
  const { state, run } = useDiseaseProfile();

  return (
    <>
      <Section>
        <PageHead
          stage="01"
          title="Disease intelligence"
          lede="Resolve a disease to an ontology identifier, then read the gene associations and the Reactome pathways derived from them. This is the biological starting point every candidate is generated against."
          art="lotus"
        >
          <QueryField
            onSubmit={(q) => void run(q)}
            busy={state.status === "loading"}
            placeholder="Disease name or ontology ID"
            action="Resolve"
            suggestions={["asthma", "psoriasis", "rheumatoid arthritis"]}
          />
        </PageHead>
      </Section>

      {state.status === "loading" ? (
        <Section>
          <Waiting note={`Resolving ${state.query}`} />
        </Section>
      ) : null}

      {state.status === "error" ? (
        <Section>
          <div className="py-6">
            <Problem error={state.error} onRetry={(q) => void run(q)} />
          </div>
        </Section>
      ) : null}

      {state.status === "success" ? <Profile profile={state.data} /> : null}

      <Section>
        <NextStage from="/disease" />
      </Section>
    </>
  );
}

function Profile({ profile }: { profile: DiseaseProfile }) {
  const { molecular_profile: mp } = profile;

  return (
    <>
      {/* identity */}
      <Section tone="sunk">
        <div className="py-16">
          <Reveal>
            <div className="flex flex-wrap items-end justify-between gap-6">
              <div>
                <Label tone="ink">Resolved</Label>
                <h2 className="mt-4 text-[clamp(2rem,5vw,3.5rem)] font-semibold">{profile.disease_name}</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <IdChip>{profile.disease_id}</IdChip>
                {profile.ontology_id ? <IdChip>{profile.ontology_id}</IdChip> : null}
              </div>
            </div>
          </Reveal>

          <Reveal delay={1}>
            <div className="mt-12 grid gap-10 border-t border-rule pt-10 sm:grid-cols-2 lg:grid-cols-4">
              <Figure value={mp.gene_count} caption="Associated genes" />
              <Figure value={mp.pathway_count} caption="Derived pathways" />
              <Figure
                value={mp.mean_gene_association_score === null ? "—" : mp.mean_gene_association_score.toFixed(2)}
                caption="Mean association score"
              />
              <Figure
                value={mp.max_gene_association_score === null ? "—" : mp.max_gene_association_score.toFixed(2)}
                caption="Strongest association"
              />
            </div>
          </Reveal>

          {profile.external_identifiers.length ? (
            <Reveal delay={2}>
              <div className="mt-12 border-t border-rule pt-8">
                <Label>Cross-references</Label>
                <div className="mt-4 flex flex-wrap gap-2">
                  {profile.external_identifiers.map((x) => (
                    <span key={`${x.source}:${x.external_id}`} className="id-chip">
                      {x.source} · {x.external_id}
                      {x.is_primary ? " ·primary" : ""}
                    </span>
                  ))}
                </div>
              </div>
            </Reveal>
          ) : null}
        </div>
      </Section>

      {/* genes */}
      <Section>
        <Cyanotype art="inflorescence" className="absolute -right-20 top-10 w-64 opacity-20" drift />
        <div className="relative py-20">
          <Reveal>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <Label tone="ink">Gene associations</Label>
                <h3 className="mt-4 text-[clamp(1.5rem,3.4vw,2.5rem)] font-semibold">
                  {profile.genes.length} genes, strongest first
                </h3>
              </div>
              {mp.genes_truncated ? (
                <p className="label max-w-xs text-right">Capped at the pipeline's per-disease gene limit</p>
              ) : null}
            </div>
          </Reveal>

          <Reveal delay={1}>
            <ul className="mt-10">
              {profile.genes.slice(0, 40).map((gene) => (
                <GeneRow key={gene.gene_id} gene={gene} />
              ))}
            </ul>
          </Reveal>

          {profile.genes.length > 40 ? (
            <p className="label mt-6">Showing the first 40 of {profile.genes.length}</p>
          ) : null}
        </div>
      </Section>

      {/* pathways */}
      <Section tone="navy" railed={false}>
        <div className="relative py-20">
          <Reveal>
            <Label tone="navy">Derived pathways</Label>
            <h3 className="mt-4 max-w-2xl text-[clamp(1.5rem,3.4vw,2.5rem)] font-semibold text-navy-text">
              The biology these genes participate in
            </h3>
            <p className="mt-4 max-w-xl text-navy-muted">
              Not curated disease-pathway assertions — these are Reactome pathways reached through the disease's
              own genes, which is why each one carries the number of genes supporting it.
            </p>
          </Reveal>

          <Reveal delay={1}>
            <ul className="mt-12 grid gap-x-10 md:grid-cols-2">
              {profile.pathways.slice(0, 24).map((pathway) => (
                <PathwayRow key={pathway.pathway_id} pathway={pathway} />
              ))}
            </ul>
          </Reveal>
        </div>
      </Section>

      {/* provenance */}
      <Section>
        <div className="py-20">
          <Reveal>
            <Label tone="ink">Provenance</Label>
            <h3 className="mt-4 text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold">Where every number came from</h3>
          </Reveal>
          <Reveal delay={1}>
            <dl className="mt-10 grid gap-x-14 md:grid-cols-2">
              <Datum term="Disease source">{profile.provenance.disease_source}</Datum>
              <Datum term="Gene source">{profile.provenance.gene_source}</Datum>
              <Datum term="Score semantics">{profile.provenance.gene_score_semantics}</Datum>
              <Datum term="Pathway source">{profile.provenance.pathway_source}</Datum>
              <Datum term="Pathway derivation">{profile.provenance.pathway_derivation}</Datum>
              <Datum term="Min gene support">{profile.provenance.pathway_min_gene_support}</Datum>
              <Datum term="Gene cap">{profile.provenance.genes_capped_per_disease}</Datum>
              <Datum term="Datasets">{profile.provenance.datasets_used.join(", ")}</Datum>
            </dl>
          </Reveal>
          <Reveal delay={2}>
            <div className="mt-10">
              <Rule dotted />
              <p className="mt-6 max-w-3xl text-sm leading-relaxed text-ink-soft">{profile.provenance.snapshot_note}</p>
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-ink-soft">{profile.provenance.disclaimer}</p>
            </div>
          </Reveal>
        </div>
      </Section>
    </>
  );
}

function GeneRow({ gene }: { gene: GeneAssociation }) {
  const [open, setOpen] = useState(false);
  const score = gene.association_score;

  return (
    <li className="border-t border-rule">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="grid w-full items-center gap-x-6 gap-y-2 py-4 text-left transition-colors hover:text-blue sm:grid-cols-[10rem_1fr_5rem]"
      >
        <span className="font-display text-lg font-semibold tracking-tight">{gene.gene_name ?? gene.gene_id}</span>
        <span className="hidden sm:block">
          <Meter value={score ?? 0} color="var(--color-gene)" />
        </span>
        <span className="tabular text-right text-sm text-ink-soft">{score === null ? "—" : score.toFixed(3)}</span>
      </button>
      {open ? (
        <div className="flex flex-wrap gap-2 pb-4">
          <IdChip>{gene.gene_id}</IdChip>
          {gene.ensembl_id ? <IdChip>{gene.ensembl_id}</IdChip> : null}
          <IdChip>source · {gene.source}</IdChip>
        </div>
      ) : null}
    </li>
  );
}

function PathwayRow({ pathway }: { pathway: PathwayAssociation }) {
  return (
    <li className="border-t border-navy-line py-4">
      <p className="text-[0.9375rem] leading-snug text-navy-text">{pathway.pathway_name}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="label label-on-navy tabular">
          {pathway.gene_support_count === null ? "—" : `${pathway.gene_support_count} genes`}
        </span>
        {pathway.reactome_id ? (
          <span className="label tabular text-navy-faint">{pathway.reactome_id}</span>
        ) : null}
      </div>
    </li>
  );
}
