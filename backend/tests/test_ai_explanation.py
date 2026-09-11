"""Phase 9 — grounded AI-powered candidate explanation tests.

No live network call is made anywhere in this file — the DeepSeek/Featherless
HTTP call is monkeypatched. The live smoke test (only run when
``FEATHERLESS_API_KEY`` is set locally) lives in
``test_ai_explanation_live_smoke.py`` and is skipped otherwise.
"""

from __future__ import annotations

import httpx
import pytest

from app.models.fusion import (
    DrugCharacterizationContext,
    EvidenceComponent,
    EvidenceFusionResult,
    FusionProvenance,
    SideEffectContext,
)
from app.models.ranking import RankedCandidate
from app.services.explanation import cache as explanation_cache
from app.services.explanation import service as explanation_service
from app.services.explanation.context import build_explanation_context
from app.services.explanation.deepseek_provider import DeepSeekFeatherlessProvider
from app.services.explanation.deterministic import DeterministicExplanationProvider
from app.services.explanation.errors import (
    ExplanationHTTPError,
    ExplanationNetworkError,
    ExplanationTimeoutError,
    ExplanationValidationError,
    MalformedResponseError,
    MissingAPIKeyError,
)
from app.services.explanation.prompts import SYSTEM_PROMPT
from app.services.explanation.service import explain_candidate, explain_top_n
from app.services.explanation.validate import validate_llm_payload
from app.services.ranking import rank_candidates

_DID = "DIS:000035"
_DRUG = "DRUG:000124"


def _comp(name: str, value: float | None, weight: float, avail: bool = True) -> EvidenceComponent:
    return EvidenceComponent(
        name=name,
        available=avail,
        value=value,
        configured_weight=weight,
        effective_weight=weight if avail else None,
        contribution_points=(round((value or 0.0) * weight * 100, 4) if avail else None),
        calculation_method=f"{name} formula",
        provenance=f"{name} source",
        supporting={"model_output": 0.8, "baseline_output": 0.5, "top_feature_names": ["f1", "f2"]}
        if name == "ml"
        else {"k": 1},
        unavailable_reason=None if avail else "not assessable",
    )


def _fusion(drug_id: str = _DRUG, score: float = 84.9, *, ml_available: bool = True) -> EvidenceFusionResult:
    comps = [_comp("gene_target", 0.87, 0.45), _comp("pathway", 0.74, 0.25)]
    comps.append(_comp("ml", 0.91, 0.30) if ml_available else _comp("ml", None, 0.30, avail=False))
    return EvidenceFusionResult(
        disease_id=_DID,
        drug_id=drug_id,
        disease_name="glioblastoma",
        drug_name="regorafenib",
        repurposing_score=score,
        components=comps,
        n_components_available=sum(c.available for c in comps),
        n_components_unavailable=sum(not c.available for c in comps),
        weights_configured={"gene_target": 0.45, "pathway": 0.25, "ml": 0.30},
        weights_renormalized_over_available=not ml_available,
        side_effect_context=SideEffectContext(side_effect_count=12, has_sider_evidence=True),
        drug_characterization=DrugCharacterizationContext(
            drug_target_count=4, drug_pathway_count=53, mechanism_count=4,
        ),
        matched_gene_hgnc_ids=["HGNC:1097", "HGNC:2731"],
        matched_disease_gene_ids=["GENE:000201", "GENE:000202"],
        matched_drug_target_ids=["TGT:000501", "TGT:000502"],
        matched_pathway_reactome_ids=["R-HSA-111", "R-HSA-222"],
        generation_methods=["gene_target", "pathway"],
        ml_model_name="random_forest" if ml_available else None,
        ml_model_output=0.91 if ml_available else None,
        ml_baseline_output=0.50 if ml_available else None,
        provenance=FusionProvenance(normalization="n", disclaimer="not clinical efficacy"),
    )


def _ranked_candidate(**kwargs) -> RankedCandidate:
    result = rank_candidates([_fusion(**kwargs)])
    return result.candidates[0]


# --- ExplanationContext construction -----------------------------------


def test_context_preserves_disease_and_drug_id():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    assert ctx.disease_id == _DID
    assert ctx.drug_id == _DRUG


def test_context_preserves_rank():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    assert ctx.rank == candidate.rank == 1


def test_context_preserves_score():
    candidate = _ranked_candidate(score=84.9)
    ctx = build_explanation_context(candidate)
    assert ctx.repurposing_score == 84.9


def test_context_preserves_matched_genes():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    assert ctx.matched_gene_hgnc_ids == ["HGNC:1097", "HGNC:2731"]


def test_context_preserves_matched_targets():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    assert ctx.matched_drug_target_ids == ["TGT:000501", "TGT:000502"]


def test_context_preserves_matched_pathways():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    assert ctx.matched_pathway_reactome_ids == ["R-HSA-111", "R-HSA-222"]


def test_context_preserves_ml_evidence():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    assert ctx.ml_model_name == "random_forest"
    assert ctx.ml_model_output == 0.91
    assert ctx.ml_baseline_output == 0.50


def test_context_marks_ml_unavailable_when_no_prediction():
    candidate = _ranked_candidate(ml_available=False)
    ctx = build_explanation_context(candidate)
    assert ctx.ml_model_name is None
    ml = ctx.component("ml")
    assert ml is not None and ml.available is False


def test_context_allowed_identifiers_covers_matched_ids():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    allowed = ctx.allowed_identifiers()
    for gid in ("HGNC:1097", "HGNC:2731", "R-HSA-111", "R-HSA-222"):
        assert gid in allowed
    assert ctx.disease_id in allowed and ctx.drug_id in allowed


# --- deterministic provider ---------------------------------------------


def test_deterministic_provider_no_score_recalculation():
    candidate = _ranked_candidate(score=84.9)
    ctx = build_explanation_context(candidate)
    explanation = DeterministicExplanationProvider().explain(candidate, ctx)
    assert explanation.repurposing_score == 84.9
    assert explanation.rank == candidate.rank


def test_deterministic_provider_no_reranking():
    ranked = rank_candidates([_fusion("DRUG:A", 40.0), _fusion("DRUG:B", 90.0)])
    explanations = explain_top_n(ranked, 2, provider=DeterministicExplanationProvider())
    assert [e.rank for e in explanations] == [1, 2]
    assert [e.drug_id for e in explanations] == [c.drug_id for c in ranked.candidates[:2]]


def test_deterministic_provider_preserves_evidence():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    explanation = DeterministicExplanationProvider().explain(candidate, ctx)
    kinds = {item.kind for item in explanation.biological_evidence}
    assert kinds == {"gene_target", "pathway"}
    gt = next(i for i in explanation.biological_evidence if i.kind == "gene_target")
    assert gt.supporting_ids == ["HGNC:1097", "HGNC:2731"]
    assert explanation.model_evidence.model_name == "random_forest"


def test_deterministic_provider_distinguishes_unavailable_from_no_support():
    candidate = _ranked_candidate(ml_available=False)
    ctx = build_explanation_context(candidate)
    explanation = DeterministicExplanationProvider().explain(candidate, ctx)
    assert explanation.model_evidence.status == "not_assessed"
    assert "unavailable" in explanation.model_evidence.description.lower()
    assert "no" not in explanation.model_evidence.description.lower().split("unavailable")[0]


def test_deterministic_provider_no_clinical_claims():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    explanation = DeterministicExplanationProvider().explain(candidate, ctx)
    text = " ".join(
        [explanation.summary, explanation.model_evidence.description, *explanation.limitations]
        + [i.description for i in explanation.biological_evidence]
    ).lower()
    for banned in ("cures", "will treat", "clinically proven", " safe ", "guaranteed"):
        assert banned not in f" {text} "


def test_deterministic_provider_is_provider_name():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    explanation = DeterministicExplanationProvider().explain(candidate, ctx)
    assert explanation.provenance.provider == "deterministic_fallback"


# --- provider abstraction -------------------------------------------------


def test_both_providers_satisfy_the_interface():
    for provider in (DeterministicExplanationProvider(), DeepSeekFeatherlessProvider(api_key="x")):
        assert hasattr(provider, "name") and isinstance(provider.name, str)
        assert callable(provider.explain)


# --- grounding / system prompt --------------------------------------------


def test_system_prompt_forbids_fabrication_and_clinical_claims():
    lowered = SYSTEM_PROMPT.lower()
    assert "do not invent" in lowered
    assert "do not claim" in lowered
    assert "unavailable" in lowered
    assert "only" in lowered


# --- DeepSeekFeatherlessProvider: failure handling (mocked HTTP) ---------


def test_missing_api_key_raises():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key=None)
    with pytest.raises(MissingAPIKeyError):
        provider.explain(candidate, ctx)


def test_missing_api_key_never_in_error_message():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key=None)
    try:
        provider.explain(candidate, ctx)
    except MissingAPIKeyError as exc:
        assert "FEATHERLESS_API_KEY" in str(exc)  # the var name, not a value


def test_http_error_raises(monkeypatch):
    class FakeResponse:
        status_code = 500
        is_error = True
        reason_phrase = "Internal Server Error"

    monkeypatch.setattr(
        "app.services.explanation.deepseek_provider.httpx.post", lambda *a, **k: FakeResponse()
    )
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="secret-test-key")
    with pytest.raises(ExplanationHTTPError):
        provider.explain(candidate, ctx)


def test_http_error_never_exposes_api_key(monkeypatch):
    class FakeResponse:
        status_code = 401
        is_error = True
        reason_phrase = "Unauthorized"

    monkeypatch.setattr(
        "app.services.explanation.deepseek_provider.httpx.post", lambda *a, **k: FakeResponse()
    )
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="super-secret-value")
    try:
        provider.explain(candidate, ctx)
    except ExplanationHTTPError as exc:
        assert "super-secret-value" not in str(exc)


def test_rate_limit_raises_http_error(monkeypatch):
    class FakeResponse:
        status_code = 429
        is_error = True
        reason_phrase = "Too Many Requests"

    monkeypatch.setattr(
        "app.services.explanation.deepseek_provider.httpx.post", lambda *a, **k: FakeResponse()
    )
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="x")
    with pytest.raises(ExplanationHTTPError) as excinfo:
        provider.explain(candidate, ctx)
    assert excinfo.value.status_code == 429


def test_timeout_raises(monkeypatch):
    def _raise(*a, **k):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("app.services.explanation.deepseek_provider.httpx.post", _raise)
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="x")
    with pytest.raises(ExplanationTimeoutError):
        provider.explain(candidate, ctx)


def test_network_failure_raises(monkeypatch):
    def _raise(*a, **k):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr("app.services.explanation.deepseek_provider.httpx.post", _raise)
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="x")
    with pytest.raises(ExplanationNetworkError):
        provider.explain(candidate, ctx)


def test_malformed_response_raises(monkeypatch):
    class FakeResponse:
        status_code = 200
        is_error = False

        def json(self):
            return {"unexpected": "shape"}

    monkeypatch.setattr(
        "app.services.explanation.deepseek_provider.httpx.post", lambda *a, **k: FakeResponse()
    )
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="x")
    with pytest.raises(MalformedResponseError):
        provider.explain(candidate, ctx)


def test_non_json_content_raises_malformed(monkeypatch):
    class FakeResponse:
        status_code = 200
        is_error = False

        def json(self):
            return {"choices": [{"message": {"content": "not json at all"}}]}

    monkeypatch.setattr(
        "app.services.explanation.deepseek_provider.httpx.post", lambda *a, **k: FakeResponse()
    )
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="x")
    with pytest.raises(MalformedResponseError):
        provider.explain(candidate, ctx)


def _valid_payload(candidate: RankedCandidate) -> dict:
    return {
        "disease_id": candidate.disease_id,
        "drug_id": candidate.drug_id,
        "rank": candidate.rank,
        "repurposing_score": candidate.repurposing_score,
        "summary": "This candidate was computationally prioritized based on the supplied evidence.",
        "evidence_notes": {
            "gene_target": "Shared gene targets were found, supporting further investigation.",
            "pathway": None,
            "ml": None,
        },
        "limitations": ["This score is not a measure of clinical efficacy."],
    }


def test_valid_response_produces_explanation(monkeypatch):
    import json as _json

    candidate = _ranked_candidate()
    payload = _valid_payload(candidate)

    class FakeResponse:
        status_code = 200
        is_error = False

        def json(self):
            return {"choices": [{"message": {"content": _json.dumps(payload)}}]}

    monkeypatch.setattr(
        "app.services.explanation.deepseek_provider.httpx.post", lambda *a, **k: FakeResponse()
    )
    ctx = build_explanation_context(candidate)
    provider = DeepSeekFeatherlessProvider(api_key="x")
    explanation = provider.explain(candidate, ctx)
    assert explanation.provenance.provider == "deepseek_featherless"
    assert explanation.rank == candidate.rank
    assert explanation.repurposing_score == candidate.repurposing_score


# --- validation ------------------------------------------------------------


def test_validation_rejects_wrong_drug_id():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    payload["drug_id"] = "DRUG:999999"
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")


def test_validation_rejects_wrong_disease_id():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    payload["disease_id"] = "DIS:999999"
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")


def test_validation_rejects_wrong_rank():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    payload["rank"] = candidate.rank + 1
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")


def test_validation_rejects_wrong_score():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    payload["repurposing_score"] = candidate.repurposing_score + 10.0
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")


def test_validation_rejects_fabricated_identifier():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    payload["evidence_notes"]["gene_target"] = "Also involves HGNC:99999999 which was not supplied."
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")


def test_validation_accepts_supplied_identifier():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    payload["evidence_notes"]["gene_target"] = "Involves HGNC:1097, which was in the supplied evidence."
    explanation = validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")
    assert explanation is not None


@pytest.mark.parametrize(
    "phrase",
    [
        "This drug is effective for the disease.",
        "This will treat the disease.",
        "This candidate cures the condition.",
        "This drug is safe for patients.",
        "This is clinically proven to work.",
        "Efficacy is guaranteed.",
    ],
)
def test_validation_rejects_clinical_claim_language(phrase):
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    payload["summary"] = phrase
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")


def test_validation_rejects_missing_required_key():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    del payload["summary"]
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")


def test_validation_rejects_non_dict_payload():
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    with pytest.raises(ExplanationValidationError):
        validate_llm_payload("not a dict", candidate, ctx, provider_name="p", model_name="m")


def test_validation_does_not_alter_structural_fields():
    """Even a well-formed, valid LLM payload cannot change the deterministic
    numbers — only prose is taken from it."""
    candidate = _ranked_candidate()
    ctx = build_explanation_context(candidate)
    payload = _valid_payload(candidate)
    explanation = validate_llm_payload(payload, candidate, ctx, provider_name="p", model_name="m")
    gt = next(i for i in explanation.biological_evidence if i.kind == "gene_target")
    expected_gt = next(
        i for i in DeterministicExplanationProvider().explain(candidate, ctx).biological_evidence
        if i.kind == "gene_target"
    )
    assert gt.value == expected_gt.value
    assert gt.contribution_points == expected_gt.contribution_points
    assert gt.supporting_ids == expected_gt.supporting_ids


# --- service orchestration / fallback --------------------------------------


class _AlwaysFailsProvider:
    name = "always_fails"
    calls = 0

    def explain(self, candidate, context):
        type(self).calls += 1
        raise ExplanationHTTPError(503, "Service Unavailable")


class _CountingGoodProvider:
    name = "counting_good"

    def __init__(self) -> None:
        self.calls = 0

    def explain(self, candidate, context):
        self.calls += 1
        payload = _valid_payload(candidate)
        return validate_llm_payload(
            payload, candidate, context, provider_name=self.name, model_name="fake-model"
        )


@pytest.fixture(autouse=True)
def _clear_explanation_cache():
    explanation_cache.clear()
    yield
    explanation_cache.clear()


def test_service_falls_back_to_deterministic_on_provider_error():
    candidate = _ranked_candidate()
    explanation = explain_candidate(candidate, provider=_AlwaysFailsProvider(), use_cache=False)
    assert explanation.provenance.provider == "deterministic_fallback"
    assert explanation.provenance.fallback_reason is not None
    assert "ExplanationHTTPError" in explanation.provenance.fallback_reason


def test_service_never_raises_on_provider_error():
    candidate = _ranked_candidate()
    # Should not raise even though the provider always fails.
    explanation = explain_candidate(candidate, provider=_AlwaysFailsProvider(), use_cache=False)
    assert explanation is not None


def test_service_uses_llm_provider_when_valid():
    candidate = _ranked_candidate()
    provider = _CountingGoodProvider()
    explanation = explain_candidate(candidate, provider=provider, use_cache=False)
    assert explanation.provenance.provider == "counting_good"
    assert explanation.provenance.fallback_reason is None


def test_cache_avoids_second_provider_call():
    candidate = _ranked_candidate()
    provider = _CountingGoodProvider()
    explain_candidate(candidate, provider=provider, use_cache=True)
    explain_candidate(candidate, provider=provider, use_cache=True)
    assert provider.calls == 1


def test_no_cache_calls_provider_each_time():
    candidate = _ranked_candidate()
    provider = _CountingGoodProvider()
    explain_candidate(candidate, provider=provider, use_cache=False)
    explain_candidate(candidate, provider=provider, use_cache=False)
    assert provider.calls == 2


def test_explain_top_n_only_calls_provider_n_times():
    ranked = rank_candidates(
        [_fusion(f"DRUG:{i}", float(i)) for i in range(10)]
    )
    provider = _CountingGoodProvider()
    explanations = explain_top_n(ranked, 3, provider=provider, use_cache=False)
    assert len(explanations) == 3
    assert provider.calls == 3


def test_explain_top_n_preserves_rank_order():
    ranked = rank_candidates([_fusion("DRUG:A", 10.0), _fusion("DRUG:B", 90.0), _fusion("DRUG:C", 50.0)])
    explanations = explain_top_n(ranked, 3, provider=DeterministicExplanationProvider(), use_cache=False)
    assert [e.rank for e in explanations] == [1, 2, 3]
    assert [e.drug_id for e in explanations] == ["DRUG:B", "DRUG:C", "DRUG:A"]


def test_default_provider_is_deterministic_without_api_key(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    explanation_service.reset_default_provider()
    try:
        provider = explanation_service.default_provider()
        assert provider is explanation_service._deterministic_provider
    finally:
        get_settings.cache_clear()
        explanation_service.reset_default_provider()
