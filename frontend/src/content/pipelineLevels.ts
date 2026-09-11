/**
 * The 10 pipeline levels, condensed from docs/architecture.md — the single
 * source of truth for what this system actually does. Used by both the Home
 * page (short form) and the About page (full form). Nothing here is
 * aspirational; every level is already implemented.
 */

export interface PipelineLevel {
  n: string;
  name: string;
  what: string;
  data: string;
  output: string;
  why: string;
}

export const PIPELINE_LEVELS: PipelineLevel[] = [
  {
    n: "01",
    name: "Data foundation",
    what: "Ingests and normalizes real biomedical datasets into six processed tables, plus an identifier crosswalk.",
    data: "SIDER, ChEMBL, Open Targets, Reactome",
    output: "drugs, diseases, drug_targets, drug_side_effects, disease_genes, disease_pathways",
    why: "Nothing downstream is fabricated — every later level traces back to a real, versioned row here.",
  },
  {
    n: "02",
    name: "Disease intelligence",
    what: "Resolves a disease name, alias, or ontology id to a canonical profile — no fuzzy matching, ever.",
    data: "Level 1 disease + disease_genes + disease_pathways tables",
    output: "DiseaseProfile: associated genes, derived pathways, provenance, deterministic summary",
    why: "Every downstream level needs one unambiguous, structured disease representation.",
  },
  {
    n: "03",
    name: "Drug intelligence",
    what: "Resolves a drug name or external id to its side effects, targets, and mechanisms of action.",
    data: "Level 1 drugs + drug_side_effects + drug_targets, optional Reactome enrichment",
    output: "DrugProfile: side effects, targets, mechanisms, optional target-pathway context, provenance",
    why: "Candidate generation and feature engineering need the same structured view, for every drug in the universe.",
  },
  {
    n: "04",
    name: "Candidate generation",
    what: "Reduces the full drug universe to the drugs biologically connected to the disease.",
    data: "Disease genes ∩ drug targets (HGNC-joined); disease pathways ∩ drug pathways (Reactome-joined)",
    output: "CandidateGenerationResult: every candidate keeps the exact relationship(s) that generated it",
    why: "No score or rank yet — this step only asks \"is there any biological connection at all?\"",
  },
  {
    n: "05",
    name: "Feature engineering",
    what: "Turns each (disease, drug) pair into a deterministic numeric feature vector.",
    data: "Counts, ratios, and source-availability flags across every prior level",
    output: "FeatureVector — flat, documented, null-safe on zero denominators",
    why: "The ML model and evidence fusion both need one consistent, versioned feature schema.",
  },
  {
    n: "06",
    name: "ML prediction",
    what: "A small interpretable classifier scores each candidate against a real, defensible label.",
    data: "Open Targets drugAndClinicalCandidates — known clinical indication (positive/unlabeled)",
    output: "PredictionResult: model output, baseline, and the top contributing features for that row",
    why: "GroupKFold by disease so the model is validated on diseases it has never seen — not a repurposing score by itself.",
  },
  {
    n: "07",
    name: "Evidence fusion",
    what: "Combines gene-target, pathway, and ML evidence into one transparent score.",
    data: "Level 5 features, Level 6 model output — 3 independent families, no double counting",
    output: "EvidenceFusionResult: a 0–100 repurposing_score with every component's value, weight, and formula kept",
    why: "Missing evidence is excluded and weights renormalized — never treated as a negative signal.",
  },
  {
    n: "08",
    name: "Candidate ranking",
    what: "Pure deterministic ordering of the fused scores — no recalculation.",
    data: "Level 7 EvidenceFusionResults for one disease",
    output: "RankedCandidate list: 1-based rank, ties broken by drug id",
    why: "Ranking is presentation only — the score it sorts by was already final at Level 7.",
  },
  {
    n: "09",
    name: "AI explanation",
    what: "Asks an LLM to narrate why a candidate was prioritized, using only the structured evidence it's handed.",
    data: "DeepSeek V4 Flash via Featherless — grounded in Level 7/8 output only",
    output: "CandidateExplanation: prose that passes identity/score/no-fabrication validation, or a deterministic fallback",
    why: "Every structural field stays deterministic; the model supplies prose only, and never invents an identifier.",
  },
  {
    n: "10",
    name: "Evidence graph",
    what: "Turns one ranked candidate into a frontend-ready graph of exactly how it was prioritized.",
    data: "Every field Levels 4–9 already computed, with its real provenance",
    output: "EvidenceGraph: nodes[] + edges[], deterministic ids, identical evidence dedups to one node",
    why: "A pure representation layer — nothing is inferred, no score or rank is recalculated for display.",
  },
];
