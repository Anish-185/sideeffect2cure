/**
 * The site map, in pipeline order.
 *
 * This list is the single source for the nav menu, the footer, the home
 * page's capability index and the "next stage" links at the foot of each
 * analysis page — so a capability cannot be added to the product without
 * appearing in every place a visitor might go looking for it.
 */

export interface Destination {
  path: string;
  title: string;
  /** Mono stage number shown beside the entry. */
  stage: string;
  /** One line, plain language — what a visitor gets on this page. */
  blurb: string;
  group: "intelligence" | "scoring" | "evidence";
}

export const DESTINATIONS: Destination[] = [
  {
    path: "/disease",
    title: "Disease intelligence",
    stage: "01",
    blurb: "What the system knows about a disease: identifiers, associated genes, derived pathways.",
    group: "intelligence",
  },
  {
    path: "/drug",
    title: "Drug intelligence",
    stage: "02",
    blurb: "A drug's identity, side effects, protein targets, mechanisms and pathway context.",
    group: "intelligence",
  },
  {
    path: "/targets",
    title: "Gene & target analysis",
    stage: "03",
    blurb: "The disease-gene to drug-target joins, resolved on HGNC identifiers.",
    group: "intelligence",
  },
  {
    path: "/pathways",
    title: "Pathway analysis",
    stage: "04",
    blurb: "Where disease pathways and drug pathways intersect in Reactome.",
    group: "intelligence",
  },
  {
    path: "/prediction",
    title: "ML prediction",
    stage: "05",
    blurb: "The interpretable model's output for a pair, and the features behind it.",
    group: "scoring",
  },
  {
    path: "/fusion",
    title: "Evidence fusion",
    stage: "06",
    blurb: "How three independent evidence families combine into one repurposing score.",
    group: "scoring",
  },
  {
    path: "/candidates",
    title: "Candidate ranking",
    stage: "07",
    blurb: "Every ranked candidate for a disease, with its evidence side by side.",
    group: "scoring",
  },
  {
    path: "/graph",
    title: "Evidence graph",
    stage: "08",
    blurb: "Follow disease to gene to target to drug, one relationship at a time.",
    group: "evidence",
  },
  {
    path: "/explanation",
    title: "AI explanation",
    stage: "09",
    blurb: "A grounded narration of the evidence, validated against the numbers it cites.",
    group: "evidence",
  },
];

export const GROUP_LABEL: Record<Destination["group"], string> = {
  intelligence: "Biological intelligence",
  scoring: "Scoring",
  evidence: "Evidence & explanation",
};

export const GROUPS = ["intelligence", "scoring", "evidence"] as const;

export function destinationsIn(group: Destination["group"]): Destination[] {
  return DESTINATIONS.filter((d) => d.group === group);
}

/** The stage after `path`, for the forward link at the foot of each page. */
export function nextDestination(path: string): Destination | null {
  const index = DESTINATIONS.findIndex((d) => d.path === path);
  if (index < 0 || index === DESTINATIONS.length - 1) return null;
  return DESTINATIONS[index + 1];
}
