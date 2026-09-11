import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { DESTINATIONS } from "./content/nav";
import type {
  CandidateExplanation,
  EvidenceComponent,

  PipelineRunResponse,
  RankedCandidate,
} from "./api/types";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function makeComponent(name: EvidenceComponent["name"], value: number | null, points: number | null): EvidenceComponent {
  return {
    name,
    available: value !== null,
    value,
    configured_weight: 0.3,
    effective_weight: value !== null ? 0.3 : null,
    contribution_points: points,
    calculation_method: "m",
    supporting: {},
    provenance: "p",
    unavailable_reason: value === null ? "not assessable" : null,
  };
}

function makeCandidate(overrides: Partial<RankedCandidate> = {}): RankedCandidate {
  const rank = overrides.rank ?? 1;
  const score = overrides.repurposing_score ?? 84.9;
  return {
    rank,
    disease_id: "DIS:000035",
    drug_id: overrides.drug_id ?? `DRUG:${rank}`,
    disease_name: "glioblastoma",
    drug_name: overrides.drug_name ?? `drug-${rank}`,
    repurposing_score: score,
    matched_gene_hgnc_ids: ["HGNC:1097"],
    matched_disease_gene_ids: ["GENE:1"],
    matched_drug_target_ids: ["TGT:1"],
    matched_pathway_reactome_ids: ["R-HSA-1"],
    generation_methods: ["gene_target", "pathway"],
    fusion: {
      disease_id: "DIS:000035",
      drug_id: overrides.drug_id ?? `DRUG:${rank}`,
      disease_name: "glioblastoma",
      drug_name: overrides.drug_name ?? `drug-${rank}`,
      repurposing_score: score,
      score_scale: "0-100",
      components: [makeComponent("gene_target", 0.87, 39.0), makeComponent("pathway", 0.74, 18.6), makeComponent("ml", 0.91, 27.3)],
      n_components_available: 3,
      n_components_unavailable: 0,
      weights_configured: { gene_target: 0.45, pathway: 0.25, ml: 0.3 },
      weights_renormalized_over_available: false,
      side_effect_context: { side_effect_count: 1, has_sider_evidence: true, note: "" },
      drug_characterization: { drug_target_count: 1, drug_pathway_count: 1, mechanism_count: 1, action_type_counts: {}, note: "" },
      matched_gene_hgnc_ids: ["HGNC:1097"],
      matched_disease_gene_ids: ["GENE:1"],
      matched_drug_target_ids: ["TGT:1"],
      matched_pathway_reactome_ids: ["R-HSA-1"],
      generation_methods: ["gene_target", "pathway"],
      ml_model_name: "random_forest",
      ml_model_output: 0.91,
      ml_baseline_output: 0.5,
      scoring_version: "1.0",
      provenance: {
        scoring_version: "1.0",
        feature_schema_version: "1.0",
        prediction_schema_version: "1.0",
        weight_scheme: "w",
        normalization: "n",
        missing_evidence_policy: "p",
        double_counting_policy: "d",
        disclaimer: "not clinical",
      },
      interpretation: "i",
    },
    ...overrides,
  };
}

function makePipelineResponse(candidates: RankedCandidate[]): PipelineRunResponse {
  return {
    disease: {
      disease_id: "DIS:000035",
      disease_name: "glioblastoma",
      ontology_id: "MONDO_0018177",
      gene_count: 200,
      pathway_count: 346,
      genes_truncated: true,
      summary_text: "Disease: glioblastoma\n\nAssociated genes...",
    },
    candidate_summary: {
      candidates_discovered: 132,
      candidates_ranked: candidates.length,
      counts_by_method: { gene_target: 19, pathway: 131 },
      n_with_gene_target_evidence: candidates.length,
      n_with_pathway_evidence: candidates.length,
      n_with_ml_evidence: candidates.length,
    },
    ranked: {
      disease_id: "DIS:000035",
      disease_name: "glioblastoma",
      candidates,
      n_candidates: candidates.length,
      provenance: {
        ranking_version: "1.0",
        ranking_signal: "score",
        tie_breaker: "drug_id",
        scores_recalculated: false,
        biology_recalculated: false,
        n_input: candidates.length,
        n_ranked: candidates.length,
        top_n_requested: candidates.length,
        top_n_applied: candidates.length,
        scoring_version: "1.0",
        disclaimer: "not clinical",
        interpretation: "i",
      },
    },
    disclaimer: "SideEffect2Cure AI is a research prototype...",
  };
}

function makeExplanation(candidate: RankedCandidate): CandidateExplanation {
  return {
    disease_id: candidate.disease_id,
    drug_id: candidate.drug_id,
    disease_name: candidate.disease_name,
    drug_name: candidate.drug_name,
    rank: candidate.rank,
    repurposing_score: candidate.repurposing_score,
    summary: `${candidate.drug_name} was computationally prioritized at rank ${candidate.rank}.`,
    biological_evidence: [
      { kind: "gene_target", status: "supported", value: 0.87, contribution_points: 39.0, supporting_ids: ["HGNC:1097"], description: "gene-target evidence text" },
      { kind: "pathway", status: "supported", value: 0.74, contribution_points: 18.6, supporting_ids: ["R-HSA-1"], description: "pathway evidence text" },
    ],
    model_evidence: {
      status: "supported",
      model_name: "random_forest",
      model_output: 0.91,
      baseline_output: 0.5,
      contribution_points: 27.3,
      top_feature_names: ["f1"],
      description: "ml evidence text",
    },
    limitations: ["This score is not a measure of clinical efficacy."],
    provenance: {
      explanation_version: "1.0",
      provider: "deterministic_fallback",
      model_name: null,
      generated_at: "2026-01-01T00:00:00Z",
      scoring_version: "1.0",
      ranking_version: "1.0",
      fallback_reason: null,
      validation_notes: [],
      grounding_note: "note",
      disclaimer: "not clinical",
    },
  };
}

/** A minimal, well-formed explanation — used as the default response for any
 * test that doesn't care about explanation content itself, so the always-
 * mounted AIExplanationPanel never sees a malformed body (the real backend
 * guarantees this shape via FastAPI's response_model validation). */
function defaultExplanation(diseaseId: string, drugId: string): CandidateExplanation {
  return makeExplanation(makeCandidate({ disease_id: diseaseId, drug_id: drugId } as Partial<RankedCandidate>));
}

type MockResult = { ok?: boolean; status?: number; body: unknown };

function mockBackend(handlers: {
  pipeline?: () => MockResult;
  candidate?: (drugId: string) => MockResult;
  explanation?: () => MockResult;
  graph?: () => MockResult;
}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL) => {
      const url = new URL(input);
      if (url.pathname.endsWith("/pipeline")) {
        const result = handlers.pipeline?.() ?? { ok: true, body: {} };
        return jsonResponse(result);
      }
      if (url.pathname.endsWith("/candidate/explanation")) {
        const diseaseId = url.searchParams.get("disease_id") ?? "DIS:000035";
        const drugId = url.searchParams.get("drug_id") ?? "DRUG:1";
        const result = handlers.explanation?.() ?? { body: defaultExplanation(diseaseId, drugId) };
        return jsonResponse(result);
      }
      if (url.pathname.endsWith("/candidate/graph")) {
        const result = handlers.graph?.() ?? { ok: true, body: {} };
        return jsonResponse(result);
      }
      if (url.pathname.endsWith("/candidate")) {
        const drugId = url.searchParams.get("drug_id") ?? "DRUG:1";
        const result = handlers.candidate?.(drugId) ?? { ok: true, body: {} };
        return jsonResponse(result);
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    }),
  );
}

function jsonResponse(result: MockResult) {
  const ok = result.ok ?? true;
  const status = result.status ?? (ok ? 200 : 400);
  return { ok, status, json: async () => result.body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // The app remembers the last disease for the tab so a refresh on an
  // analysis page can restore itself. Left in place, that makes one test's
  // run leak into the next one's idle state.
  sessionStorage.clear();
});

describe("home page", () => {
  it("leads with the product's proposition and carries the disclaimer", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/existing drugs/i);
    expect(screen.getByText(/does not establish clinical efficacy/i)).toBeInTheDocument();
  });

  it("indexes every capability so none is reachable only by URL", () => {
    renderAt("/");
    for (const destination of DESTINATIONS) {
      expect(screen.getAllByRole("link", { name: new RegExp(destination.title, "i") }).length).toBeGreaterThan(0);
    }
  });
});

describe("candidate ranking", () => {
  it("runs the pipeline and lists ranked candidates with their evidence", async () => {
    const candidates = [makeCandidate({ rank: 1, drug_name: "alpha" }), makeCandidate({ rank: 2, drug_name: "beta" })];
    mockBackend({ pipeline: () => ({ body: makePipelineResponse(candidates) }) });

    renderAt("/candidates");
    await userEvent.type(screen.getByLabelText(/disease to rank/i), "glioblastoma");
    await userEvent.click(screen.getByRole("button", { name: /run pipeline/i }));

    await waitFor(() => expect(screen.getByRole("button", { name: /alpha/i })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /beta/i })).toBeInTheDocument();
    // The backend's own funnel counts, not anything recomputed here.
    expect(screen.getByText("132")).toBeInTheDocument();
  });

  it("reports an empty ranking as a result rather than an error", async () => {
    mockBackend({ pipeline: () => ({ body: makePipelineResponse([]) }) });

    renderAt("/candidates");
    await userEvent.type(screen.getByLabelText(/disease to rank/i), "glioblastoma");
    await userEvent.click(screen.getByRole("button", { name: /run pipeline/i }));

    await waitFor(() => expect(screen.getByText(/no candidate met the evidence requirements/i)).toBeInTheDocument());
  });

  it("surfaces an ambiguous disease as the backend's own alternatives", async () => {
    mockBackend({
      pipeline: () => ({
        ok: false,
        status: 409,
        body: {
          detail: {
            status: "ambiguous",
            query: "cancer",
            candidates: [
              { disease_id: "DIS:1", disease_name: "lung cancer", ontology_id: null, matched_on: "alias", matched_value: "cancer" },
            ],
            message: "More than one disease matched.",
          },
        },
      }),
    });

    renderAt("/candidates");
    await userEvent.type(screen.getByLabelText(/disease to rank/i), "cancer");
    await userEvent.click(screen.getByRole("button", { name: /run pipeline/i }));

    await waitFor(() => expect(screen.getByText(/more than one disease matched/i)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "lung cancer" })).toBeInTheDocument();
  });
});

describe("pages downstream of ranking", () => {
  it("invite a run rather than rendering an empty analysis", async () => {
    for (const path of ["/fusion", "/graph", "/explanation", "/targets", "/pathways", "/prediction"]) {
      renderAt(path);
      // /graph is code-split, so its first paint is the Suspense fallback.
      await waitFor(() => expect(screen.getByText(/no analysis yet/i)).toBeInTheDocument());
      cleanup();
    }
  });

  it("show the selected candidate's fusion arithmetic from backend values only", async () => {
    const candidate = makeCandidate({ rank: 1, drug_name: "alpha" });
    mockBackend({ pipeline: () => ({ body: makePipelineResponse([candidate]) }) });

    renderAt("/candidates");
    await userEvent.type(screen.getByLabelText(/disease to rank/i), "glioblastoma");
    await userEvent.click(screen.getByRole("button", { name: /run pipeline/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /alpha/i })).toBeInTheDocument());

    await userEvent.click(screen.getByRole("link", { name: /how this score was built/i }));

    await waitFor(() => expect(screen.getByText(/how alpha reached 84.9/i)).toBeInTheDocument());
    // Each component's contribution is displayed as the backend computed it.
    expect(screen.getByText("39.0")).toBeInTheDocument();
    expect(screen.getByText("18.6")).toBeInTheDocument();
    expect(screen.getByText("27.3")).toBeInTheDocument();
  });
});

describe("disease intelligence", () => {
  it("shows the resolved profile and its provenance", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          body: {
            disease_id: "DIS:000035",
            disease_name: "glioblastoma",
            ontology_id: "MONDO_0018177",
            external_identifiers: [{ external_id: "MONDO_0018177", source: "mondo", is_primary: true }],
            genes: [{ gene_id: "GENE:1", gene_name: "EGFR", ensembl_id: "ENSG1", association_score: 0.82, source: "opentargets" }],
            pathways: [{ pathway_id: "P:1", pathway_name: "Signaling by EGFR", reactome_id: "R-HSA-177929", gene_support_count: 12, association_score: null, source: "reactome" }],
            molecular_profile: {
              gene_count: 200,
              pathway_count: 346,
              mean_gene_association_score: 0.41,
              max_gene_association_score: 0.82,
              top_gene_symbols: ["EGFR"],
              top_pathway_names: ["Signaling by EGFR"],
              genes_truncated: true,
            },
            provenance: {
              disease_source: "opentargets",
              datasets_used: ["opentargets", "reactome"],
              gene_source: "opentargets",
              gene_score_semantics: "association score",
              genes_capped_per_disease: 200,
              genes_truncated: true,
              pathway_source: "reactome",
              pathway_derivation: "derived from disease genes",
              pathway_min_gene_support: 3,
              snapshot_note: "snapshot note",
              disclaimer: "not clinical",
            },
            summary_text: "Disease: glioblastoma",
          },
        }),
      ),
    );

    renderAt("/disease");
    await userEvent.type(screen.getByLabelText(/disease name or ontology/i), "glioblastoma");
    await userEvent.click(screen.getByRole("button", { name: /resolve/i }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "glioblastoma" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /EGFR/ })).toBeInTheDocument();
    expect(screen.getByText("Signaling by EGFR")).toBeInTheDocument();
    expect(screen.getByText(/snapshot note/i)).toBeInTheDocument();
  });
});

describe("how it works", () => {
  it("expands a level to reveal what it consumes and produces", async () => {
    renderAt("/how-it-works");
    const row = screen.getByRole("button", { name: /drug intelligence/i });
    expect(row).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(row);

    expect(row).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByText(/what it produces/i).length).toBeGreaterThan(0);
  });
});
