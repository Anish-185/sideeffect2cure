import { useEffect, useState } from "react";
import { ApiError, fetchCandidate } from "../api/client";
import type { RankedCandidate } from "../api/types";

export type CandidateState =
  | { status: "loading" }
  | { status: "success"; data: RankedCandidate }
  | { status: "error"; error: ApiError };

/** Deep-linkable candidate lookup for the Candidate Analysis page — requires
 * /pipeline to have been run for this disease at least once (process-local
 * cache; same requirement as the explanation/graph endpoints). */
export function useCandidate(diseaseId: string | null, drugId: string | null): CandidateState {
  const [state, setState] = useState<CandidateState>({ status: "loading" });

  useEffect(() => {
    if (!diseaseId || !drugId) return;
    let cancelled = false;
    setState({ status: "loading" });
    fetchCandidate(diseaseId, drugId)
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({ status: "error", error: err instanceof ApiError ? err : new ApiError(0, { message: "Unexpected error" }) });
      });
    return () => {
      cancelled = true;
    };
  }, [diseaseId, drugId]);

  return state;
}
