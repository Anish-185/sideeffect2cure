"""Phase 11 — dashboard API tests.

Exercises the real backend (real Level 1 data + trained model where
present), the same way the rest of the suite's end-to-end tests do — skipped
gracefully if that data/model isn't present locally.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.disease import DiseaseMatch, MatchType, ResolutionResult, ResolutionStatus
from app.services.pipeline import cache as pipeline_cache

client = TestClient(app)

_BANNED_PHRASES = ("cures", "will treat", "clinically proven", "safe", "safely", "guaranteed", "effective")


def _contains_banned_word(text: str, phrase: str) -> bool:
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
    return re.search(pattern, text) is not None


@pytest.fixture(autouse=True)
def _clear_pipeline_cache():
    pipeline_cache.clear()
    yield
    pipeline_cache.clear()


def _run(query: str = "Glioblastoma", top_n: int = 3):
    resp = client.get("/api/pipeline", params={"query": query, "top_n": top_n})
    if resp.status_code == 404:
        pytest.skip("Level 1 processed data not present; run scripts/ingest_data.py")
    return resp


# --- disease search / pipeline run -----------------------------------------


def test_valid_disease_returns_200():
    resp = _run("Glioblastoma", top_n=3)
    assert resp.status_code == 200


def test_empty_query_returns_400():
    resp = client.get("/api/pipeline", params={"query": ""})
    assert resp.status_code == 400
    assert resp.json()["detail"]["status"] == "empty_query"


def test_unsupported_disease_returns_404():
    resp = client.get("/api/pipeline", params={"query": "totally unknown disease xyz 12345"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["status"] == "not_supported"


def test_ambiguous_resolution_maps_to_409():
    """Unit-tests the AMBIGUOUS -> 409 mapping directly (real ingested data
    has no known name collision to trigger this over HTTP end-to-end)."""
    from app.api.pipeline import _resolution_error_to_http
    from app.services.disease.errors import DiseaseResolutionError

    result = ResolutionResult(
        status=ResolutionStatus.AMBIGUOUS,
        query="test glioma",
        normalized_query="test glioma",
        candidates=[
            DiseaseMatch(disease_id="DIS:001", disease_name="test glioma", matched_on=MatchType.EXACT_NAME, matched_value="test glioma"),
            DiseaseMatch(disease_id="DIS:002", disease_name="test glioma", matched_on=MatchType.EXACT_NAME, matched_value="test glioma"),
        ],
        message="ambiguous",
    )
    http_exc = _resolution_error_to_http(DiseaseResolutionError(result))
    assert http_exc.status_code == 409
    assert http_exc.detail["status"] == "ambiguous"
    assert len(http_exc.detail["candidates"]) == 2


def test_disease_overview_uses_real_profile_data():
    resp = _run("Glioblastoma", top_n=1)
    body = resp.json()
    disease = body["disease"]
    assert disease["disease_id"] and disease["disease_name"]
    assert disease["gene_count"] > 0
    assert disease["pathway_count"] > 0
    assert disease["summary_text"]


def test_candidate_summary_matches_ranked_list():
    resp = _run("Glioblastoma", top_n=5)
    body = resp.json()
    summary = body["candidate_summary"]
    ranked = body["ranked"]["candidates"]
    assert summary["candidates_ranked"] == len(ranked)
    assert summary["candidates_discovered"] >= summary["candidates_ranked"]
    assert 0 <= summary["n_with_gene_target_evidence"] <= len(ranked)
    assert 0 <= summary["n_with_pathway_evidence"] <= len(ranked)
    assert 0 <= summary["n_with_ml_evidence"] <= len(ranked)


def test_ranked_candidates_have_rank_and_score():
    resp = _run("Glioblastoma", top_n=5)
    candidates = resp.json()["ranked"]["candidates"]
    assert candidates == sorted(candidates, key=lambda c: c["rank"])
    assert [c["rank"] for c in candidates] == list(range(1, len(candidates) + 1))
    scores = [c["repurposing_score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_score_breakdown_present_on_each_candidate():
    resp = _run("Glioblastoma", top_n=3)
    for c in resp.json()["ranked"]["candidates"]:
        names = {comp["name"] for comp in c["fusion"]["components"]}
        assert names == {"gene_target", "pathway", "ml"}


def test_other_supported_disease_works():
    resp = _run("Alzheimer disease", top_n=3)
    assert resp.status_code == 200
    assert resp.json()["disease"]["disease_name"]


# --- candidate explanation ---------------------------------------------------


def test_candidate_explanation_matches_rank_and_score():
    run_resp = _run("Glioblastoma", top_n=3)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    top = body["ranked"]["candidates"][0]

    resp = client.get("/api/candidate/explanation", params={"disease_id": disease_id, "drug_id": top["drug_id"]})
    assert resp.status_code == 200
    explanation = resp.json()
    assert explanation["disease_id"] == disease_id
    assert explanation["drug_id"] == top["drug_id"]
    assert explanation["rank"] == top["rank"]
    assert explanation["repurposing_score"] == top["repurposing_score"]


def test_candidate_explanation_no_clinical_claims():
    run_resp = _run("Glioblastoma", top_n=1)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    top = body["ranked"]["candidates"][0]

    resp = client.get("/api/candidate/explanation", params={"disease_id": disease_id, "drug_id": top["drug_id"]})
    explanation = resp.json()
    text = " ".join(
        [explanation["summary"], *explanation["limitations"]]
        + [item["description"] for item in explanation["biological_evidence"]]
        + [explanation["model_evidence"]["description"]]
    ).lower()
    for banned in _BANNED_PHRASES:
        assert not _contains_banned_word(text, banned), f"found banned phrase {banned!r} in: {text!r}"


def test_candidate_explanation_without_pipeline_run_returns_409():
    resp = client.get("/api/candidate/explanation", params={"disease_id": "DIS:999999", "drug_id": "DRUG:000001"})
    assert resp.status_code == 409


def test_candidate_explanation_unknown_drug_returns_404():
    run_resp = _run("Glioblastoma", top_n=1)
    disease_id = run_resp.json()["disease"]["disease_id"]
    resp = client.get("/api/candidate/explanation", params={"disease_id": disease_id, "drug_id": "DRUG:nonexistent"})
    assert resp.status_code == 404


# --- candidate graph -----------------------------------------------------------


def test_candidate_graph_matches_disease_and_drug():
    run_resp = _run("Glioblastoma", top_n=1)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    drug_id = body["ranked"]["candidates"][0]["drug_id"]

    resp = client.get("/api/candidate/graph", params={"disease_id": disease_id, "drug_id": drug_id})
    assert resp.status_code == 200
    graph = resp.json()
    assert graph["disease_id"] == disease_id
    assert graph["drug_id"] == drug_id
    assert graph["metadata"]["n_nodes"] == len(graph["nodes"])
    assert graph["metadata"]["n_edges"] == len(graph["edges"])


def test_candidate_graph_score_and_rank_not_recalculated():
    run_resp = _run("Glioblastoma", top_n=1)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    top = body["ranked"]["candidates"][0]

    resp = client.get("/api/candidate/graph", params={"disease_id": disease_id, "drug_id": top["drug_id"]})
    graph = resp.json()
    score_node = next(n for n in graph["nodes"] if n["type"] == "score")
    rank_node = next(n for n in graph["nodes"] if n["type"] == "rank")
    assert score_node["metadata"]["repurposing_score"] == top["repurposing_score"]
    assert rank_node["metadata"]["rank"] == top["rank"]


def test_candidate_graph_includes_explanation_node_by_default():
    run_resp = _run("Glioblastoma", top_n=1)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    drug_id = body["ranked"]["candidates"][0]["drug_id"]

    resp = client.get("/api/candidate/graph", params={"disease_id": disease_id, "drug_id": drug_id})
    graph = resp.json()
    assert any(n["type"] == "explanation" for n in graph["nodes"])


def test_candidate_graph_can_skip_explanation():
    run_resp = _run("Glioblastoma", top_n=1)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    drug_id = body["ranked"]["candidates"][0]["drug_id"]

    resp = client.get(
        "/api/candidate/graph",
        params={"disease_id": disease_id, "drug_id": drug_id, "include_explanation": False},
    )
    graph = resp.json()
    assert not any(n["type"] == "explanation" for n in graph["nodes"])


def test_candidate_graph_without_pipeline_run_returns_409():
    resp = client.get("/api/candidate/graph", params={"disease_id": "DIS:999999", "drug_id": "DRUG:000001"})
    assert resp.status_code == 409


def test_missing_evidence_handled_in_graph_and_explanation():
    """Every ranked candidate — even those with fewer available evidence
    components — must still produce a valid explanation/graph, not a crash."""
    run_resp = _run("Glioblastoma", top_n=10)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    candidates = body["ranked"]["candidates"]
    partial = next(
        (c for c in candidates if any(not comp["available"] for comp in c["fusion"]["components"])),
        None,
    )
    if partial is None:
        pytest.skip("no candidate in this top-10 has any unavailable evidence component")

    exp_resp = client.get("/api/candidate/explanation", params={"disease_id": disease_id, "drug_id": partial["drug_id"]})
    assert exp_resp.status_code == 200
    graph_resp = client.get("/api/candidate/graph", params={"disease_id": disease_id, "drug_id": partial["drug_id"]})
    assert graph_resp.status_code == 200


# --- no duplicate recomputation (performance) --------------------------------


def test_explanation_and_graph_reuse_cached_pipeline_run(monkeypatch):
    """/pipeline computes candidate generation once; subsequent
    /candidate/explanation and /candidate/graph calls for the same disease
    must NOT re-run Level 4 candidate generation."""
    calls = {"n": 0}

    import app.services.candidates as candidates_pkg

    original = candidates_pkg.generate_candidates

    def counting_generate_candidates(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    # run_pipeline() does `from app.services.candidates import generate_candidates`
    # freshly on every call, so patching the package attribute is enough.
    monkeypatch.setattr(candidates_pkg, "generate_candidates", counting_generate_candidates)

    run_resp = _run("Glioblastoma", top_n=3)
    body = run_resp.json()
    disease_id = body["disease"]["disease_id"]
    drug_id = body["ranked"]["candidates"][0]["drug_id"]
    assert calls["n"] == 1

    client.get("/api/candidate/explanation", params={"disease_id": disease_id, "drug_id": drug_id})
    client.get("/api/candidate/graph", params={"disease_id": disease_id, "drug_id": drug_id})
    client.get("/api/candidate/explanation", params={"disease_id": disease_id, "drug_id": drug_id})

    assert calls["n"] == 1, "explanation/graph endpoints must not re-run candidate generation"
