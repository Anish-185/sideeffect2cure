# Phase 9 — Grounded AI-Powered Candidate Explanation

Phase 9 owns exactly this slice of the pipeline:

```
RankedCandidate  ->  ExplanationContext  ->  DeepSeek V4 Flash (Featherless)
        ->  validated CandidateExplanation
```

> The AI explanation layer summarizes computational evidence already produced
> by the pipeline. It does not establish clinical efficacy, safety, treatment
> suitability, or cure.

It does **not** recalculate the `repurposing_score`, does not rerank, does not
generate new features, does not compute pathway/gene similarity, and does not
discover new drug-disease relationships — those are Levels 4-8. Phase 9 only
**narrates** evidence that already exists.

---

## Purpose

Given a Phase 8 `RankedCandidate` and its full evidence trail, answer:

> "Why was this drug computationally prioritized for this disease?"

using only the structured evidence the deterministic pipeline already
produced.

---

## Architecture

```
RankedCandidate (Phase 8, embeds the full Phase 7 EvidenceFusionResult)
        |
        v
build_explanation_context()          app.services.explanation.context
        |  -> ExplanationContext      app.models.explanation
        v
ExplanationProvider.explain()        app.services.explanation.provider
        |
        +-- DeepSeekFeatherlessProvider   (LLM, if FEATHERLESS_API_KEY set)
        |       |
        |       +-- success + passes validation -> CandidateExplanation
        |       +-- any failure/validation rejection -----+
        |                                                  v
        +-- DeterministicExplanationProvider  <------------+  (always available)
                |
                v
        CandidateExplanation           app.models.explanation
```

Orchestration lives in `app.services.explanation.service`:
`explain_candidate`, `explain_top_n`, `explain_for_disease`.

**Key design choice — the LLM only supplies prose.** Every *structural* field
on `CandidateExplanation` (`value`, `contribution_points`, `supporting_ids`,
`status`, the `rank` and `repurposing_score` themselves) is built
deterministically from the Phase 7/8 evidence in
`app.services.explanation.descriptions`. The LLM may only contribute the
`summary`, per-evidence-family `description` text, and `limitations` — and
only after that text passes grounding validation. This is what makes "the
model must not recalculate/rerank/invent evidence" structurally true rather
than a prompting hope.

---

## DeepSeek V4 Flash provider (Featherless)

`app.services.explanation.deepseek_provider.DeepSeekFeatherlessProvider`
calls Featherless's OpenAI-compatible chat-completions endpoint:

* **Base URL:** `https://api.featherless.ai/v1`
* **Model:** `deepseek-ai/DeepSeek-V4-Flash-0731`
* **Request:** one `POST /chat/completions`, `response_format: {"type": "json_object"}`,
  `temperature=0.2`, `max_tokens=700` — one call per candidate explained.

It is isolated behind the `ExplanationProvider` protocol
(`app.services.explanation.provider`), so it can be swapped for a different
provider later without touching the context builder, validator, fallback, or
`service.py`.

### Environment configuration

Read via `app.core.config.Settings` (see `.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `FEATHERLESS_API_KEY` | *(none)* | **Required** to enable the LLM provider. Unset -> deterministic provider is used automatically, no error. |
| `FEATHERLESS_BASE_URL` | `https://api.featherless.ai/v1` | |
| `FEATHERLESS_MODEL` | `deepseek-ai/DeepSeek-V4-Flash-0731` | |
| `FEATHERLESS_TIMEOUT_SECONDS` | `30` | |

These are read by their bare names (no `SE2C_` prefix, unlike the rest of
`Settings`) so they match the vendor's own naming and a plain `.env` /
shell-exported key works with no translation. **The key is never hardcoded,
never logged, and never returned to a caller** — `ExplanationHTTPError`
messages are built only from an HTTP status code and reason phrase, never
from request/response bodies or headers.

---

## Structured evidence context

`app.models.explanation.ExplanationContext`, built by
`build_explanation_context(candidate)` — a pure projection of the
`RankedCandidate` already in hand. No new database/repository lookup, no
extra dataset, nothing beyond what Levels 4-8 already computed for this one
candidate:

* disease: `disease_id`, `disease_name`
* drug: `drug_id`, `drug_name`
* rank, `repurposing_score`, `score_scale`
* `generation_methods`, matched gene / disease-gene / drug-target / pathway
  ids (Level 4)
* the 3 Phase 7 `EvidenceComponent`s verbatim (gene_target / pathway / ml —
  value, weight, `contribution_points`, formula, `supporting` data,
  `unavailable_reason`)
* `drug_characterization` / `side_effect_context` (Phase 7 descriptive
  context)
* ML model name/output/baseline (Phase 6)
* `weights_configured`, `scoring_version`, `ranking_version`, `disclaimer`

This is deliberately compact — one candidate's evidence, not the 1,430-drug
universe, not the full disease/drug profile, not the repository.

---

## Grounding rules (system prompt)

The system prompt (`app.services.explanation.prompts.SYSTEM_PROMPT`) instructs
the model to:

* use **only** the structured evidence in the user message;
* never invent a gene, target, pathway, mechanism, study, or clinical trial;
* never claim a drug treats, cures, prevents, or is clinically effective, safe,
  or clinically proven;
* never interpret the score as a probability of treatment success;
* explicitly say "unavailable" for unassessed evidence — **never** reframe
  that as "no relationship" or negative evidence (Phase 7's
  missing-evidence-is-not-negative-evidence rule carries through to Phase 9);
* use language like "computationally prioritized", "supported by the
  available evidence", "candidate for further investigation";
* respond with **one JSON object only** (`disease_id`, `drug_id`, `rank`,
  `repurposing_score` echoed; `summary`; `evidence_notes` per evidence family;
  `limitations`).

---

## Response validation

`app.services.explanation.validate.validate_llm_payload` is deliberately
lightweight — no general NLP fact-checking pipeline:

1. **Required keys present** (`disease_id`, `drug_id`, `rank`,
   `repurposing_score`, `summary`, `limitations`).
2. **Echoed identity matches the input** — `disease_id`, `drug_id`, `rank`,
   `repurposing_score` (`math.isclose`, `abs_tol=0.05`) must equal the actual
   candidate. A mismatch (e.g. the model confusing which candidate it was
   given) fails validation.
3. **No fabricated identifiers** — every `HGNC:`, `TGT:`, `GENE:`, `DIS:`,
   `DRUG:`, `R-HSA-` id mentioned in any prose field must be one of the ids
   `ExplanationContext.allowed_identifiers()` actually supplied.
4. **No banned clinical-claim language** — whole-word/phrase match (favouring
   false positives) against `effective`, `will treat`, `treats`, `cure(s)`,
   `curing`, `treatment probability`, `safe(ly)`, `clinically proven`,
   `proven`, `guarantee(d)`.

**Any single failure discards the entire response** — Phase 9 never patches
in a partially-valid answer; `service.explain_candidate` falls back to the
deterministic provider as a unit. On success, only the prose
(`summary`/`evidence_notes`/`limitations`) is taken from the LLM; every
numeric/structural field is still the deterministic one built from Phase 7/8.

---

## Deterministic fallback

`app.services.explanation.deterministic.DeterministicExplanationProvider`
builds the exact same `CandidateExplanation` shape directly from the
structured evidence (via `app.services.explanation.descriptions`), with no
network call. It is used whenever:

* `FEATHERLESS_API_KEY` is not set (`default_provider()` skips the LLM
  entirely — no doomed network call);
* the HTTP request fails, times out, or returns a non-2xx status;
* the response body/JSON is malformed;
* the response fails grounding validation (§ above).

`CandidateExplanation.provenance.provider` is always either
`"deepseek_featherless"` or `"deterministic_fallback"`, and
`provenance.fallback_reason` is set whenever the LLM was tried and rejected —
so a caller can always tell which path produced an explanation. The pipeline
never crashes and never blocks on the explanation layer being reachable.

---

## Failure handling

| Failure | Behaviour |
|---|---|
| `FEATHERLESS_API_KEY` unset | `default_provider()` returns the deterministic provider directly (no request attempted) |
| Explicit LLM provider + missing key | `MissingAPIKeyError` -> caught by `service.py` -> deterministic fallback |
| Timeout | `ExplanationTimeoutError` -> fallback |
| Network failure | `ExplanationNetworkError` -> fallback |
| Non-2xx HTTP (incl. 429 rate limit) | `ExplanationHTTPError` (status + reason phrase only) -> fallback |
| Malformed JSON / unexpected response shape | `MalformedResponseError` -> fallback |
| Response fails grounding validation | `ExplanationValidationError` -> fallback |

All of the above are caught in `service.explain_candidate` — nothing upstream
(the ranking pipeline, an API route, a script) ever has to handle a Phase 9
exception.

---

## Cost-conscious usage

* **No new paid dependency.** Only the configured Featherless endpoint is
  used; no other LLM/RAG/vector/search API is added.
* **Explicit, not automatic.** `explain_candidate` explains one candidate;
  `explain_top_n` explains an explicitly requested N (a demo script defaults
  to 3). Nothing calls the LLM for an entire ranked list, and nothing calls it
  on a schedule or in a background loop.
* **One request per candidate explained** — the system+user prompt is small
  (one candidate's `ExplanationContext`, not the 1,430-drug universe).
* **Caching** (below) avoids repeat calls for the same candidate.

## Caching

`app.services.explanation.cache` is a small in-memory, process-local
dict keyed by `(disease_id, drug_id, repurposing_score, scoring_version,
ranking_version, provider_name)`. `explain_candidate(..., use_cache=True)`
(the default) checks it before calling a provider and stores the result
(LLM or fallback) after. No database, no disk persistence — it exists purely
so a demo/dashboard re-rendering the same candidate doesn't re-call the LLM
within one process lifetime, and clears on restart.

---

## Top-3 GBM demo

```bash
cd backend
python scripts/explain_candidates.py                 # Glioblastoma, top 3 (default)
python scripts/explain_candidates.py "Alzheimer disease" --top-n 5
```

Runs the real pipeline (Levels 4-8, unchanged) for the query, then Phase 9 for
the top-N ranked candidates, printing for each: rank, drug, repurposing score,
**why prioritized**, **biological evidence**, **ML evidence**, and
**limitations**. Uses DeepSeek via Featherless when `FEATHERLESS_API_KEY` is
set; otherwise (or on any API failure) it prints the deterministic fallback —
the script always produces output.

---

## Testing

`backend/tests/test_ai_explanation.py` — context construction, both providers
(mocked HTTP for the LLM one: missing key, HTTP error incl. 429, timeout,
network failure, malformed response, valid response), grounding validation
(id/rank/score mismatch, fabricated identifiers, banned clinical language,
missing keys), service orchestration (fallback on failure, no exception ever
raised, caching, `explain_top_n` order/ranks preserved), and that structural
fields cannot be altered by even a *valid* LLM response. No live network call.

`backend/tests/test_ai_explanation_live_smoke.py` — one real call to
Featherless, **only** when `FEATHERLESS_API_KEY` is set locally
(`pytest -m live`); skipped, never faked, otherwise.

---

## Future graph compatibility (not implemented here)

Every identifier Phase 10's evidence graph will need is already preserved
end-to-end and visible in `ExplanationContext` / `CandidateExplanation`:
disease -> disease gene -> drug target -> pathway -> drug -> ML prediction ->
evidence -> repurposing score -> rank -> **AI explanation**. Phase 9 does not
build the graph, a visualization, a dashboard, OCR, literature retrieval, RAG,
embeddings, or any new scoring/ranking — those remain later phases.

---

## Limitations

* The explanation is a **narration of existing computational evidence**, not
  an independent scientific assessment — the LLM cannot see anything the
  deterministic pipeline did not already compute.
* It does **not** establish clinical efficacy, safety, treatment suitability,
  or cure, and must never be presented as doing so.
* Grounding validation is intentionally lightweight (structured-field checks
  + a banned-phrase/identifier scan), not a general fact-checking system — it
  catches the identifier/score/claim classes of error this phase cares about,
  not arbitrary prose errors.
* The cache is per-process and in-memory; it is a courtesy, not a guarantee,
  and holds no data across restarts.
