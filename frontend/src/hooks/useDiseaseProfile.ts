import { useCallback, useState } from "react";
import { ApiError, fetchDiseaseProfile } from "../api/client";
import type { DiseaseProfile } from "../api/types";

export type DiseaseProfileState =
  | { status: "idle" }
  | { status: "loading"; query: string }
  | { status: "success"; data: DiseaseProfile }
  | { status: "error"; error: ApiError; query: string };

export function useDiseaseProfile() {
  const [state, setState] = useState<DiseaseProfileState>({ status: "idle" });

  const run = useCallback(async (query: string) => {
    setState({ status: "loading", query });
    try {
      const data = await fetchDiseaseProfile(query);
      setState({ status: "success", data });
    } catch (err) {
      const apiError = err instanceof ApiError ? err : new ApiError(0, { message: "Unexpected error" });
      setState({ status: "error", error: apiError, query });
    }
  }, []);

  return { state, run };
}
