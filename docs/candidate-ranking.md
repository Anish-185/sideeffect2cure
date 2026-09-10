# Phase 8 — Candidate Ranking

Phase 8 owns exactly this slice of the pipeline:

```
EvidenceFusionResult[]  ->  rank_candidates(...)  ->  RankedCandidateResult
```

It is **pure ordering**. It does not recalculate any biology, does not create a
new score, and does not modify the Phase 7 `repurposing_score`.

> Ranking is based on the Phase 7 **computational** `repurposing_score`.
> It does **not** establish clinical efficacy, treatment suitability, patient
> response, or safety, and is **not** a medical recommendation.

---

## Purpose

Turn the unordered set of Phase 7 `EvidenceFusionResult` objects for a disease
into an ordered list of **computationally prioritized candidates for further
investigation**, with a `rank` on each — while keeping every evidence component
so the later AI-explanation, evidence-graph and dashboard phases can answer
*"why did this candidate get this score / this rank?"*.

---

## Input

`list[EvidenceFusionResult]` (Phase 7). Each already carries `disease_id`,
`drug_id`, `repurposing_score`, the `components` breakdown
(gene-target / pathway / ML — value, configured & effective weight,
`contribution_points`, formula, supporting data, provenance), the matched
biological identifiers, and the `FusionProvenance`.

Phase 8 reads these; it never re-runs Levels 2-7.

---

## Ranking rule

1. **Sort by `repurposing_score` descending** (highest first) — the single
   ranking signal. No other score is introduced or computed.
2. **Tie-break: `drug_id` ascending** (lexicographic). Stable and deterministic;
   no randomness, no timestamps, no hash order, no arbitrary ordering.
3. **Assign `rank` = 1..N** by sorted position. Ranks are **always unique** — two
   candidates with identical scores get consecutive ranks ordered by `drug_id`
   (there is no "shared rank" / competition-style numbering).

```
score 91.2 → rank 1
score 84.7 → rank 2
score 84.7 → rank 3   (same score; ordered by drug_id)
score 73.5 → rank 4
```

Determinism: identical input list ⇒ byte-identical `RankedCandidateResult`
(tested, including on the real GBM pipeline).

---

## `top_n`

Optional presentation / selection parameter on `rank_candidates(results, top_n=…)`
and `rank_for_disease(query, top_n=…)`.

| value | behaviour |
|---|---|
| `None` (default) | return the **complete** ordered list |
| positive int ≤ N | return the first `top_n` ranked candidates (ranks `1..top_n`) |
| positive int > N | return all N (no error); `top_n_applied = N` |
| `0`, negative, non-int (`2.5`, `"3"`), `bool` | raise `InvalidTopNError` |

`top_n` is a **slice applied after ranking**. It never alters a
`repurposing_score` or the rank a candidate has in the full list. Both the
requested and the applied value are recorded in `RankingProvenance`.

---

## Input edge cases

| input | behaviour |
|---|---|
| empty list | `RankedCandidateResult` with `candidates == []`, `n_candidates == 0`, `disease_id = None` — **not** an error |
| one candidate | ranked at `rank == 1` |
| many candidates | fully ordered as above |
| **duplicate `drug_id`** | `DuplicateCandidateError` (with the offending ids). Candidates are unique per `(disease_id, drug_id)` in Levels 4-7, so a duplicate signals an upstream bug — ranking refuses rather than assign two ranks to one drug. |
| not a `list[EvidenceFusionResult]` | `TypeError` |

No candidates are ever fabricated.

---

## Output schema (`app.models.ranking`)

```
RankedCandidateResult
├── disease_id / disease_name        (the single disease shared by all candidates, else None)
├── candidates : list[RankedCandidate]
│     ├── rank                        1-based, unique
│     ├── disease_id, drug_id, disease_name, drug_name
│     ├── repurposing_score           UNCHANGED from Phase 7
│     ├── matched_gene_hgnc_ids / matched_disease_gene_ids /
│     │   matched_drug_target_ids / matched_pathway_reactome_ids / generation_methods   <- graph ids
│     └── fusion : EvidenceFusionResult   <- the COMPLETE Phase 7 record, nothing dropped
│           (components with values/weights/effective_weights/contribution_points/
│            calculation_method/supporting/provenance, weights_configured,
│            side_effect_context, drug_characterization, ml_model_*, FusionProvenance, ...)
├── n_candidates
└── provenance : RankingProvenance
      ├── ranking_version, ranking_signal, tie_breaker
      ├── scores_recalculated = False, biology_recalculated = False
      ├── n_input, n_ranked, top_n_requested, top_n_applied
      ├── scoring_version                 (echoed from the fusion results)
      ├── disclaimer
      └── interpretation                  ("... does NOT establish clinical efficacy ...
                                           not a medical recommendation")
```

`RankedCandidateResult.table_rows()` is a convenience flat projection
(`rank`, `drug_name`, `repurposing_score`, per-component value & points) for a
later table/dashboard view — the full model keeps all evidence regardless.

No `efficacy` / `treatment_probability` / `cure` / `recommendation` /
`safety_score` / `priority_score` / `new_score` field exists on any Phase 8
model (enforced by test).

---

## Evidence preservation

Every `RankedCandidate` embeds the whole `EvidenceFusionResult` in `.fusion`, so
all of this survives ranking unchanged:

`repurposing_score`, the gene-target / pathway / ML `EvidenceComponent`s
(value, `configured_weight`, `effective_weight`, `contribution_points`,
`calculation_method`, `supporting`, `provenance`, `unavailable_reason`),
`weights_configured`, `weights_renormalized_over_available`,
`side_effect_context`, `drug_characterization`, `ml_model_name` /
`ml_model_output` / `ml_baseline_output`, `matched_*` id lists,
`generation_methods`, `FusionProvenance`, `scoring_version`, `disease_id`,
`drug_id`.

A test asserts `ranked.candidates[i].fusion == input_fusion_result` (deep
equality) and that `Σ contribution_points ≈ repurposing_score` still holds.

---

## Determinism & cost

Pure local computation: one `sorted(...)` with a total-order key
`(-repurposing_score, drug_id)`, then index assignment. No randomness, no LLM,
no network, no new dependency, no dataset. `O(N log N)`.

---

## GBM example (`rank_for_disease("Glioblastoma", top_n=10)`)

```
132 fused -> 132 ranked (top_n_applied 10) · disease DIS:000035 · scoring_version 1.0
scores_recalculated: False

 rank  drug           score    gene_target   pathway   ML     contribution points
   1.  regorafenib    84.92    0.867         0.743     0.912  [39.0 + 18.6 + 27.3]
   2.  dasatinib      73.79    0.600         0.734     0.948  [27.0 + 18.4 + 28.4]
   3.  gefitinib      72.27    0.600         0.905     0.755  [27.0 + 22.6 + 22.6]
   ...
   6.  bcnu           71.29    0.600         n/a       0.882  [36.0 +  0.0 + 35.3]   (ML+gene-target only; pathway N/A -> weights renormalized)
```

Values come from the real pipeline; nothing is hardcoded. `rank 1` means the
**most computationally prioritized candidate for further investigation** — it
does **not** mean the drug treats GBM.

---

## Limitations

- Ranking is only as meaningful as the Phase 7 `repurposing_score` (a prototype
  weighting over 3 evidence families) and everything upstream of it.
- A single linear order loses the multi-dimensional nature of the evidence —
  which is why the full component breakdown is attached to every rank.
- `top_n` is a display cut, not a claim that candidate N+1 is uninteresting.
- No re-scoring, calibration, or diversity/novelty adjustment is applied.

---

## What Phase 9 will implement

**AI Explanation.** Phase 9 consumes each `RankedCandidate` (its `rank`,
`repurposing_score`, and the full evidence breakdown) and generates a
human-readable, grounded explanation of *why* the candidate is prioritized —
without changing the rank or the score. The evidence graph and dashboard follow.
