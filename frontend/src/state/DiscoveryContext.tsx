import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, fetchPipeline } from "../api/client";
import type { PipelineRunResponse } from "../api/types";

/**
 * One disease run, shared across Discovery / Rankings / Predictions / AI
 * Explanation so moving between those pages never re-runs the pipeline or
 * asks the user to pick the disease again.
 *
 * The last query is remembered for the tab (not the result — that always
 * comes back from the backend) so a hard refresh on /rankings can restore
 * itself instead of dead-ending.
 */

export type DiscoveryState =
  | { status: "idle" }
  | { status: "loading"; query: string }
  | { status: "success"; data: PipelineRunResponse }
  | { status: "error"; error: ApiError; query: string };

interface DiscoveryValue {
  state: DiscoveryState;
  lastQuery: string | null;
  run: (query: string, topN?: number) => Promise<void>;
  reset: () => void;
  /** The candidate the analysis pages are currently focused on. Fusion,
   * Evidence Graph and AI Explanation all read this, so moving between them
   * never asks the user to pick the same drug three times. */
  selectedDrugId: string | null;
  select: (drugId: string | null) => void;
}

const STORAGE_KEY = "s2c:last-disease-query";
const DiscoveryCtx = createContext<DiscoveryValue | null>(null);

function readStoredQuery(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function DiscoveryProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DiscoveryState>({ status: "idle" });
  const [lastQuery, setLastQuery] = useState<string | null>(() => readStoredQuery());
  const [selectedDrugId, setSelectedDrugId] = useState<string | null>(null);

  const run = useCallback(async (query: string, topN = 10) => {
    setState({ status: "loading", query });
    setLastQuery(query);
    setSelectedDrugId(null);
    try {
      sessionStorage.setItem(STORAGE_KEY, query);
    } catch {
      // Private-mode storage failures must never block a real analysis run.
    }
    try {
      const data = await fetchPipeline(query, topN);
      setState({ status: "success", data });
    } catch (err) {
      const apiError = err instanceof ApiError ? err : new ApiError(0, { message: "Unexpected error" });
      setState({ status: "error", error: apiError, query });
    }
  }, []);

  const reset = useCallback(() => {
    setState({ status: "idle" });
    setLastQuery(null);
    setSelectedDrugId(null);
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo(
    () => ({ state, lastQuery, run, reset, selectedDrugId, select: setSelectedDrugId }),
    [state, lastQuery, run, reset, selectedDrugId],
  );
  return <DiscoveryCtx.Provider value={value}>{children}</DiscoveryCtx.Provider>;
}

export function useDiscovery(): DiscoveryValue {
  const ctx = useContext(DiscoveryCtx);
  if (!ctx) throw new Error("useDiscovery must be used inside <DiscoveryProvider>");
  return ctx;
}

/**
 * For the analysis pages (Rankings / Predictions / AI Explanation): if the
 * tab remembers a disease but this page has no result yet, re-run it once so
 * the page can stand on its own when opened directly.
 */
/**
 * The focused candidate, resolved against the current run. Falls back to the
 * top-ranked candidate so every analysis page has something real to show the
 * moment a disease finishes running, without the user picking first.
 */
export function useFocusedCandidate() {
  const { state, selectedDrugId, select } = useDiscovery();
  const candidates = state.status === "success" ? state.data.ranked.candidates : [];
  const candidate = candidates.find((c) => c.drug_id === selectedDrugId) ?? candidates[0] ?? null;
  return { candidate, candidates, select, isExplicit: selectedDrugId !== null };
}

export function useRestoredRun() {
  const { state, lastQuery, run } = useDiscovery();

  useEffect(() => {
    if (state.status === "idle" && lastQuery) void run(lastQuery);
  }, [state.status, lastQuery, run]);

  return useDiscovery();
}
