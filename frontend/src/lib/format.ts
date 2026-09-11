import type { EvidenceComponentName, EvidenceStatus, GraphNodeType } from "../api/types";

export function formatScore(score: number): string {
  return score.toFixed(1);
}

export function formatPoints(points: number | null): string {
  if (points === null) return "—";
  return points.toFixed(1);
}

export function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return `${Math.round(value * 100)}%`;
}

export const EVIDENCE_LABEL: Record<EvidenceComponentName, string> = {
  gene_target: "Gene-target",
  pathway: "Pathway",
  ml: "ML prediction",
};

export const EVIDENCE_COLOR_VAR: Record<EvidenceComponentName, string> = {
  gene_target: "var(--color-gene)",
  pathway: "var(--color-pathway)",
  ml: "var(--color-ml)",
};

export const STATUS_LABEL: Record<EvidenceStatus, string> = {
  supported: "Supported by evidence",
  assessed_no_support: "Assessed — no overlap found",
  not_assessed: "Not assessable",
};

export const NODE_TYPE_LABEL: Record<GraphNodeType, string> = {
  disease: "Disease",
  disease_gene: "Disease gene",
  drug: "Drug",
  drug_target: "Drug target",
  pathway: "Pathway",
  prediction: "ML prediction",
  evidence_component: "Evidence component",
  score: "Repurposing score",
  rank: "Rank",
  explanation: "AI explanation",
};

/** Generic, structural descriptions of what each node TYPE represents in the
 * pipeline — never a per-instance claim about a specific gene/drug/pathway.
 * Instance-level detail always comes from the node's own real metadata. */
export const NODE_TYPE_WHY: Record<GraphNodeType, string> = {
  disease: "The disease this whole candidate was evaluated against.",
  disease_gene: "A gene associated with the disease profile — the biological starting point for candidate generation.",
  drug: "The candidate drug being evaluated for repurposing.",
  drug_target: "A protein this drug is known to act on — matched against the disease's associated genes.",
  pathway: "A Reactome pathway both the disease's genes and the drug's targets participate in.",
  prediction: "The interpretable model's output for this disease-drug pair.",
  evidence_component: "One of the independent evidence families combined into the final score.",
  score: "The fused repurposing score — every component's contribution kept alongside it.",
  rank: "This candidate's position among every drug ranked for the disease.",
  explanation: "The AI's grounded narration of the evidence above — validated before being shown.",
};

export const NODE_TYPE_AI_ELIGIBLE = new Set<GraphNodeType>(["drug", "score", "rank", "explanation", "evidence_component", "prediction"]);

export function titleCase(id: string): string {
  return id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
