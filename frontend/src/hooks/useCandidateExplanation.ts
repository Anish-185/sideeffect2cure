import { useEffect, useState } from "react";
import { ApiError, fetchCandidateExplanation } from "../api/client";
import type { CandidateExplanation } from "../api/types";

export type ExplanationState =
  | { status: "loading" }
  | { status: "success"; data: CandidateExplanation }
  | { status: "error"; error: ApiError };

// Module-level cache: re-selecting a candidate already viewed this session
// must not re-call the backend (which would re-call the LLM provider).
const cache = new Map<string, CandidateExplanation>();

function cacheKey(diseaseId: string, drugId: string): string {
  return `${diseaseId}:${drugId}`;
}

export function useCandidateExplanation(diseaseId: string, drugId: string): ExplanationState {
  const key = cacheKey(diseaseId, drugId);
  const [state, setState] = useState<ExplanationState>(() => {
    const cached = cache.get(key);
    return cached ? { status: "success", data: cached } : { status: "loading" };
  });

  useEffect(() => {
    const cached = cache.get(key);
    if (cached) {
      setState({ status: "success", data: cached });
      return;
    }
    let cancelled = false;
    setState({ status: "loading" });
    fetchCandidateExplanation(diseaseId, drugId)
      .then((data) => {
        if (cancelled) return;
        cache.set(key, data);
        setState({ status: "success", data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({ status: "error", error: err instanceof ApiError ? err : new ApiError(0, { message: "Unexpected error" }) });
      });
    return () => {
      cancelled = true;
    };
  }, [key, diseaseId, drugId]);

  return state;
}
