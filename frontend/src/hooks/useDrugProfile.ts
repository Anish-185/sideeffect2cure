import { useCallback, useState } from "react";
import { ApiError, fetchDrugProfile } from "../api/client";
import type { DrugProfile } from "../api/types";

export type DrugProfileState =
  | { status: "idle" }
  | { status: "loading"; query: string }
  | { status: "success"; data: DrugProfile }
  | { status: "error"; error: ApiError; query: string };

export function useDrugProfile() {
  const [state, setState] = useState<DrugProfileState>({ status: "idle" });

  const run = useCallback(async (query: string) => {
    setState({ status: "loading", query });
    try {
      const data = await fetchDrugProfile(query);
      setState({ status: "success", data });
    } catch (err) {
      const apiError = err instanceof ApiError ? err : new ApiError(0, { message: "Unexpected error" });
      setState({ status: "error", error: apiError, query });
    }
  }, []);

  return { state, run };
}
