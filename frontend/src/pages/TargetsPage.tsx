import { CandidateBar, NeedsRun, NextStage, PageHead, Problem, Waiting } from "../components/analysis";
import { Cyanotype, IdChip, Label, Reveal, Section } from "../components/ui";
import { useCandidateGraph } from "../hooks/useCandidateGraph";
import { targetJoins, type TargetJoin } from "../lib/evidenceViews";
import { useFocusedCandidate, useRestoredRun } from "../state/DiscoveryContext";

/**
 * Stage 03. The join itself: which disease gene met which drug target, and on
 * what identifier. This is the page that answers "why is this drug here at
 * all" without reference to any score.
 */
export function TargetsPage() {
  const { state } = useRestoredRun();
  const { candidate } = useFocusedCandidate();

  return (
    <>
      <Section>
        <PageHead
          stage="03"
          title="Gene & target analysis"
          lede="A disease gene and a drug target are two different records in two different databases. They become one relationship only when their identifiers resolve to the same gene — and that resolution is what this page shows."
          art="leaf-sprig"
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
          <NeedsRun what="gene-to-target relationships" />
        </Section>
      ) : null}

      {candidate ? <Joins diseaseId={candidate.disease_id} drugId={candidate.drug_id} /> : null}

      <Section>
        <NextStage from="/targets" />
      </Section>
    </>
  );
}

function Joins({ diseaseId, drugId }: { diseaseId: string; drugId: string }) {
  const graph = useCandidateGraph(diseaseId, drugId, true);

  if (graph.status === "loading" || graph.status === "idle") {
    return (
      <Section>
        <Waiting note="Loading the relationships" />
      </Section>
    );
  }

  if (graph.status === "error") {
    return (
      <Section>
        <div className="py-8">
          <Problem error={graph.error} />
        </div>
      </Section>
    );
  }

  const joins = targetJoins(graph.data);

  return (
    <>
      <Section>
        <Cyanotype art="inflorescence" className="absolute -right-24 top-16 w-60 opacity-[0.16]" drift />
        <div className="relative py-20">
          <Reveal>
            <Label tone="ink">The chain</Label>
            <h2 className="mt-4 max-w-2xl text-[clamp(1.75rem,4vw,2.75rem)] font-semibold">
              {graph.data.disease_name} → gene → target → {graph.data.drug_id ? drugLabel(graph.data) : "drug"}
            </h2>
            <p className="mt-4 max-w-xl text-ink-soft">
              {joins.length === 0
                ? "No gene-target join was found for this pair. This candidate reached the ranking on pathway evidence alone."
                : `${joins.length} ${joins.length === 1 ? "relationship" : "relationships"}, each resolved on a shared HGNC identifier.`}
            </p>
          </Reveal>

          <div className="mt-14 space-y-px">
            {joins.map((join, i) => (
              <Reveal key={join.geneNodeId + join.targetNodeId} delay={((i % 3) + 1) as 1 | 2 | 3}>
                <JoinRow join={join} disease={graph.data.disease_name} drug={drugLabel(graph.data)} />
              </Reveal>
            ))}
          </div>
        </div>
      </Section>

      {joins.length ? (
        <Section tone="navy" railed={false}>
          <div className="relative py-20">
            <Reveal>
              <Label tone="navy">How the join is made</Label>
              <h3 className="mt-4 max-w-3xl text-[clamp(1.375rem,3vw,2rem)] font-semibold leading-snug text-navy-text">
                {joins[0].provenance ?? "Resolved on a shared gene identifier."}
              </h3>
              <p className="mt-6 max-w-2xl text-navy-muted">
                Both sides are normalised to HGNC before anything is compared, so a match is never made on a gene
                symbol or a name — only on an identifier that both databases agree on.
              </p>
            </Reveal>
          </div>
        </Section>
      ) : null}
    </>
  );
}

function drugLabel(graph: { nodes: { type: string; label: string }[] }): string {
  return graph.nodes.find((n) => n.type === "drug")?.label ?? "drug";
}

/** One relationship, drawn as the four-step path it actually is. */
function JoinRow({ join, disease, drug }: { join: TargetJoin; disease: string; drug: string }) {
  return (
    <div className="border-t border-rule py-8">
      <div className="grid items-start gap-x-6 gap-y-6 md:grid-cols-4">
        <Step label="Disease" value={disease} />
        <Step
          label="Disease gene"
          value={join.geneSymbol}
          chips={[join.geneId, join.ensemblId, join.geneSource ? `source · ${join.geneSource}` : null]}
          arrow
        />
        <Step
          label="Drug target"
          value={join.targetName}
          chips={[join.targetId, join.uniprotId, join.actionType]}
          arrow
        />
        <Step label="Drug" value={drug} arrow />
      </div>

      {join.hgncId ? (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Label>Joined on</Label>
          <IdChip>{join.hgncId}</IdChip>
        </div>
      ) : null}
    </div>
  );
}

function Step({
  label,
  value,
  chips = [],
  arrow = false,
}: {
  label: string;
  value: string;
  chips?: (string | null)[];
  arrow?: boolean;
}) {
  return (
    <div className="relative">
      {arrow ? (
        <span aria-hidden className="absolute -left-4 top-7 hidden text-ink-faint md:block">
          →
        </span>
      ) : null}
      <Label>{label}</Label>
      <p className="mt-2 font-display text-[1.0625rem] font-semibold leading-snug tracking-tight">{value}</p>
      {chips.filter(Boolean).length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {chips.filter(Boolean).map((chip) => (
            <IdChip key={chip}>{chip}</IdChip>
          ))}
        </div>
      ) : null}
    </div>
  );
}
