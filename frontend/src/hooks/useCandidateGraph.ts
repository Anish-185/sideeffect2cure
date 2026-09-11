import { useEffect, useState } from "react";
import { ApiError, fetchCandidateGraph } from "../api/client";
import type { EvidenceGraph } from "../api/types";

export type GraphState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: EvidenceGraph }
  | { status: "error"; error: ApiError };

// Module-level cache, mirrors useCandidateExplanation — opening the graph
// panel for the same candidate twice must not rebuild it server-side twice.
const cache = new Map<string, EvidenceGraph>();

function cacheKey(diseaseId: string, drugId: string): string {
  return `${diseaseId}:${drugId}`;
}

/** Lazy: does nothing until `enabled` is true (the graph panel is opened). */
export function useCandidateGraph(diseaseId: string, drugId: string, enabled: boolean): GraphState {
  const key = cacheKey(diseaseId, drugId);
  const [state, setState] = useState<GraphState>(() => {
    const cached = cache.get(key);
    return cached ? { status: "success", data: cached } : { status: "idle" };
  });

  useEffect(() => {
    if (!enabled) return;
    const cached = cache.get(key);
    if (cached) {
      setState({ status: "success", data: cached });
      return;
    }
    let cancelled = false;
    setState({ status: "loading" });
    fetchCandidateGraph(diseaseId, drugId)
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
  }, [enabled, key, diseaseId, drugId]);

  return state;
}
