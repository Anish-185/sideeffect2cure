/**
 * Thin fetch wrapper over the backend's Phase 11 API. No scientific logic
 * lives here or anywhere else in this frontend — every function below only
 * requests and parses a backend response.
 */
import type {
  AmbiguousDiseaseDetail,
  AmbiguousDrugDetail,
  CandidateExplanation,
  DiseaseProfile,
  DrugProfile,
  EmptyQueryDetail,
  EvidenceGraph,
  PipelineRunResponse,
  PlainDetail,
  RankedCandidate,
  UnsupportedDiseaseDetail,
  UnsupportedDrugDetail,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000/api";

export type ApiErrorDetail =
  | EmptyQueryDetail
  | AmbiguousDiseaseDetail
  | UnsupportedDiseaseDetail
  | AmbiguousDrugDetail
  | UnsupportedDrugDetail
  | PlainDetail
  | string;

/** Carries the parsed HTTP status + backend `detail` body so the UI can
 * render a specific state (empty / ambiguous / not supported / not run /
 * not found) instead of one generic error message. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: ApiErrorDetail;

  constructor(status: number, detail: ApiErrorDetail) {
    super(typeof detail === "string" ? detail : detail.message ?? `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, params: Record<string, string | number | boolean>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, String(value));
  }

  let response: Response;
  try {
    response = await fetch(url.toString());
  } catch {
    throw new ApiError(0, { message: "Could not reach the backend. Is it running?" });
  }

  if (!response.ok) {
    let detail: ApiErrorDetail = { message: `Request failed (${response.status})` };
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // non-JSON error body — keep the generic detail
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

/** Levels 2-8: resolve the disease and run candidate generation -> ranking.
 * Does not request explanations or graphs (those are fetched lazily, per
 * candidate, only when the user opens one). */
export function fetchPipeline(query: string, topN = 10): Promise<PipelineRunResponse> {
  return request<PipelineRunResponse>("/pipeline", { query, top_n: topN });
}

/** Phase 9, lazily, for exactly one candidate. */
export function fetchCandidateExplanation(diseaseId: string, drugId: string): Promise<CandidateExplanation> {
  return request<CandidateExplanation>("/candidate/explanation", { disease_id: diseaseId, drug_id: drugId });
}

/** Phase 10, lazily, for exactly one candidate. */
export function fetchCandidateGraph(
  diseaseId: string,
  drugId: string,
  includeExplanation = true,
): Promise<EvidenceGraph> {
  return request<EvidenceGraph>("/candidate/graph", {
    disease_id: diseaseId,
    drug_id: drugId,
    include_explanation: includeExplanation,
  });
}

/** One already-ranked candidate on its own — requires /pipeline to have run
 * for this disease at least once (same process-local cache as explanation/
 * graph). Lets the Candidate Analysis page be a deep-linkable route. */
export function fetchCandidate(diseaseId: string, drugId: string): Promise<RankedCandidate> {
  return request<RankedCandidate>("/candidate", { disease_id: diseaseId, drug_id: drugId });
}

/** Level 2 alone: a disease's full profile (genes, pathways, provenance),
 * independent of any candidate pipeline run. */
export function fetchDiseaseProfile(query: string): Promise<DiseaseProfile> {
  return request<DiseaseProfile>("/disease/profile", { query });
}

/** Level 3 alone: a drug's full profile (side effects, targets, mechanisms,
 * optional pathway context), independent of any disease. */
export function fetchDrugProfile(query: string): Promise<DrugProfile> {
  return request<DrugProfile>("/drug/profile", { query });
}
