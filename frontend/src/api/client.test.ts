import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  fetchCandidate,
  fetchCandidateExplanation,
  fetchCandidateGraph,
  fetchDiseaseProfile,
  fetchDrugProfile,
  fetchPipeline,
} from "./client";

function mockFetchOnce(status: number, body: unknown) {
  const response = {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchPipeline", () => {
  it("returns the parsed body on success", async () => {
    const body = { disease: { disease_id: "DIS:1" }, candidate_summary: {}, ranked: { candidates: [] }, disclaimer: "x" };
    mockFetchOnce(200, body);
    const result = await fetchPipeline("Glioblastoma", 3);
    expect(result).toEqual(body);
  });

  it("passes query and top_n as query params", async () => {
    mockFetchOnce(200, {});
    await fetchPipeline("Glioblastoma", 5);
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    const url = new URL(call);
    expect(url.searchParams.get("query")).toBe("Glioblastoma");
    expect(url.searchParams.get("top_n")).toBe("5");
  });

  it("throws ApiError with the backend detail on non-2xx", async () => {
    mockFetchOnce(404, { detail: { status: "not_supported", query: "xyz", suggestions: [], message: "nope" } });
    await expect(fetchPipeline("xyz")).rejects.toMatchObject({
      status: 404,
      detail: { status: "not_supported" },
    });
  });

  it("throws ApiError(0, ...) when the network request itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    await expect(fetchPipeline("Glioblastoma")).rejects.toBeInstanceOf(ApiError);
    await expect(fetchPipeline("Glioblastoma")).rejects.toMatchObject({ status: 0 });
  });
});

describe("fetchCandidateExplanation / fetchCandidateGraph", () => {
  it("requests the explanation endpoint with disease_id + drug_id", async () => {
    mockFetchOnce(200, { summary: "x" });
    await fetchCandidateExplanation("DIS:1", "DRUG:1");
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    const url = new URL(call);
    expect(url.pathname).toContain("/candidate/explanation");
    expect(url.searchParams.get("disease_id")).toBe("DIS:1");
    expect(url.searchParams.get("drug_id")).toBe("DRUG:1");
  });

  it("requests the graph endpoint with include_explanation", async () => {
    mockFetchOnce(200, { nodes: [], edges: [] });
    await fetchCandidateGraph("DIS:1", "DRUG:1", false);
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    const url = new URL(call);
    expect(url.searchParams.get("include_explanation")).toBe("false");
  });

  it("surfaces a 409 'pipeline not run' error", async () => {
    mockFetchOnce(409, { detail: { message: "Run the pipeline for this disease first." } });
    await expect(fetchCandidateExplanation("DIS:1", "DRUG:1")).rejects.toMatchObject({ status: 409 });
  });
});

describe("fetchCandidate", () => {
  it("requests the standalone candidate endpoint with disease_id + drug_id", async () => {
    mockFetchOnce(200, { rank: 1, drug_id: "DRUG:1" });
    await fetchCandidate("DIS:1", "DRUG:1");
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    const url = new URL(call);
    expect(url.pathname).toContain("/candidate");
    expect(url.pathname).not.toContain("/candidate/");
    expect(url.searchParams.get("disease_id")).toBe("DIS:1");
    expect(url.searchParams.get("drug_id")).toBe("DRUG:1");
  });
});

describe("fetchDiseaseProfile / fetchDrugProfile", () => {
  it("requests /disease/profile with the query", async () => {
    mockFetchOnce(200, { disease_id: "DIS:1" });
    await fetchDiseaseProfile("Glioblastoma");
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    const url = new URL(call);
    expect(url.pathname).toContain("/disease/profile");
    expect(url.searchParams.get("query")).toBe("Glioblastoma");
  });

  it("requests /drug/profile with the query", async () => {
    mockFetchOnce(200, { drug_id: "DRUG:1" });
    await fetchDrugProfile("Aspirin");
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    const url = new URL(call);
    expect(url.pathname).toContain("/drug/profile");
    expect(url.searchParams.get("query")).toBe("Aspirin");
  });
});
