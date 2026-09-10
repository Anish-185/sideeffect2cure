# Phase 7 — Evidence Fusion + Repurposing Score

Phase 7 owns exactly this slice of the pipeline:

```
CandidateDrug + FeatureVector + (optional) PredictionResult
        ->  fuse_evidence(...)  ->  EvidenceFusionResult  (repurposing_score 0-100 + breakdown)
```

It does **not** rank, select top-N, recommend, explain in language, or draw a
graph — those are Phase 8+. It combines the *available* evidence into one
transparent number **while keeping every component visible**.

---

## Purpose

`repurposing_score` (0-100) is an **internal research prioritization score**:

> "How strongly does the available computational / biological evidence support
> prioritizing this existing drug for further investigation for this disease?"

It is **not**, and is never described as:

| ✗ not this | ✓ neutral wording used |
|---|---|
| clinical efficacy | computationally prioritized candidate |
| probability of treatment success | higher evidence-supported prioritization |
| probability of curing the disease | candidate for further investigation |
| patient-response probability | model / evidence output |
| medical or safety recommendation | — |

```
repurposing_score  ≠  clinical efficacy  ≠  treatment probability  ≠  medical recommendation
```

---

## Evidence streams — which genuinely exist

| family | exists? | used as a scoring component? |
|---|---|---|
| **gene-target** (disease gene == drug target, HGNC id) | yes (Level 4/5) | **yes** |
| **pathway** (shared Reactome pathway) | yes (Level 2 ∩ Level 3) | **yes** |
| **ML prediction** | yes (Phase 6) | **yes**, when a `PredictionResult` is supplied |
| **side effects** (SIDER) | yes | **no** — descriptive context only (see below) |
| **drug characterization** (target/pathway/mechanism counts) | yes | **no** — descriptive context only |

Only real evidence is used. No component is fabricated to fill a slot.

### Why side effects are not scored

No defensible *disease-relevant* side-effect relationship exists in the current
data (no disease-side-effect links, no validated side-effect→mechanism map).
Scoring side-effect burden would either (a) invent a relationship, or
(b) penalize a drug for having many side effects — the brief forbids both. So
`SideEffectContext` (`side_effect_count`, `has_sider_evidence`) is carried on
the result as **descriptive context only**, explicitly not a safety assessment.

### Why drug characterization is not scored

Rewarding well-studied drugs (more targets, more pathways) would bias the score
toward popular compounds rather than toward disease-relevant evidence.
`DrugCharacterizationContext` is descriptive only.

---

## Double-counting safeguard

Several Level 5 features describe the **same** biological relationship:

```
gene-target family : matched_gene_target_count, matched_disease_gene_count,
                     matched_drug_target_count,
                     fraction_of_drug_targets_matching_disease_genes,
                     fraction_of_disease_genes_targeted_by_drug,
                     generated_by_gene_target, gene_target_reason_count
pathway family      : matched_pathway_count, disease/drug pathway counts,
                     fraction_of_drug_pathways_matching_disease_pathways,
                     fraction_of_disease_pathways_matching_drug_pathways,
                     generated_by_pathway, pathway_reason_count
```

Each family is collapsed into **exactly one** `EvidenceComponent`. Within a
family, *count strength* and *specificity* are combined **once** (a single
blended value), not counted as separate evidence streams. The fusion mean is
over **independent families**, never over multiple representations of one
relationship. Tests assert `names.count("gene_target") == 1` etc. and that a
family's component value is unchanged when other families change.

---

## Component definitions & normalization formulas

Every component is normalized to `[0, 1]`. All tunables live in
`app.services.fusion.config.FusionConfig` — no magic numbers in the fusion code.

### gene_target

```
count_norm  = min(matched_gene_target_count, gene_target_count_cap) / gene_target_count_cap   # cap = 5
specificity = clip01(fraction_of_drug_targets_matching_disease_genes)
value       = count_subweight * count_norm  +  specificity_subweight * specificity            # 0.5 / 0.5
```

*Available* iff `has_gene_target_bridge` **and** `drug_target_hgnc_mapped_count ≥ 1`
**and** `disease_gene_hgnc_mapped_count ≥ 1`. We use the **drug-side** fraction
(specificity: "how much of the drug's target repertoire is disease-relevant"),
not the disease-side fraction (coverage of a large, capped gene set), which is
kept in `supporting` for transparency.

### pathway

```
count_norm  = min(matched_pathway_count, pathway_count_cap) / pathway_count_cap               # cap = 10
specificity = clip01(fraction_of_drug_pathways_matching_disease_pathways)
value       = count_subweight * count_norm  +  specificity_subweight * specificity
```

*Available* iff `has_reactome_pathway_evidence` **and** `disease_pathways_available`
**and** `drug_pathway_count ≥ 1`.

### ml

```
value = clip01(PredictionResult.model_output)      # a [0,1] model output, used directly
```

*Available* iff a Phase 6 `PredictionResult` is supplied. `baseline_output`,
`model_name` and the top-3 contributing feature names are kept in `supporting`.
If Phase 6 had determined that no valid supervised prediction was possible, no
`PredictionResult` would be produced and this component would simply be
unavailable — nothing is fabricated.

`clip01` maps `None` / `NaN` / `±inf` / out-of-range inputs to a finite `[0,1]`
value, so no component can ever be `NaN`.

---

## Weighting scheme (prototype heuristic — NOT clinically validated)

`FusionConfig` (default):

| component | configured weight | rationale |
|---|---:|---|
| `gene_target` | **0.45** | most specific single mechanistic hypothesis (drug directly targets a disease-associated gene) |
| `ml` | **0.30** | data-driven prior from clinical-development history, but Phase 6's target is weak positive/unlabeled, so it contributes without dominating |
| `pathway` | **0.25** | loosest link (a broad signalling pathway is shared by many unrelated drugs) |

Weights need not sum to 1. They are **validated** (`> 0`, finite; sub-weights
sum to 1) and echoed into `EvidenceFusionResult.weights_configured` and
`provenance.weight_scheme` (which states "prototype heuristic — NOT clinically
validated"). Pass a custom `FusionConfig` to `fuse_evidence(..., config=...)`.

---

## Missing evidence ≠ negative evidence

| situation | representation |
|---|---|
| component **could not be assessed** (no HGNC bridge, no drug pathway context, no ML model) | `available = False`, `value = None`, `unavailable_reason` set — **excluded from the score**, weights renormalized |
| component **was assessed, found no support** (bridge ran, drug has mappable targets, 0 overlap) | `available = True`, `value = 0.0` — **kept** in the weighted mean (a real weak/negative signal that pulls the score down) |

**Renormalization**: the score is `100 × weighted mean of the available
components`, with each available component's `effective_weight =
configured_weight / Σ(configured weights of available components)`.
`weights_renormalized_over_available` is `True` whenever ≥1 component is
unavailable. If **no** component is available, `repurposing_score = 0.0`
(never `NaN`).

Example (default weights, ML unavailable):

```
available: gene_target (0.45), pathway (0.25)   ->   effective: 0.643, 0.357
repurposing_score = 100 * (0.643 * gt_value + 0.357 * pw_value)
```

---

## Score formula

```
repurposing_score = clamp(0, 100,  100 * Σ_available( value_c * effective_weight_c ))
                  = Σ_available( contribution_points_c )        (up to rounding)
```

Each component exposes `contribution_points = value · effective_weight · 100`
(the points it added to the 0-100 score), so the breakdown reconstructs the
total. Deterministic: identical `(CandidateDrug, FeatureVector, PredictionResult,
FusionConfig)` → identical result. No randomness, no LLM, no live API.

---

## Output schema (`app.models.fusion.EvidenceFusionResult`)

```
EvidenceFusionResult
├── disease_id, drug_id, disease_name, drug_name
├── repurposing_score : float 0-100        score_scale = "0-100"
├── components : list[EvidenceComponent]
│     ├── name, available, value|None
│     ├── configured_weight, effective_weight|None, contribution_points|None
│     ├── calculation_method     (the exact formula)
│     ├── supporting {...}        (the Level 4/5/6 values that fed it)
│     ├── provenance             (which levels/sources)
│     └── unavailable_reason|None
├── n_components_available / n_components_unavailable
├── weights_configured {gene_target, pathway, ml}
├── weights_renormalized_over_available : bool
├── side_effect_context     -> SideEffectContext          (descriptive, NOT scored)
├── drug_characterization   -> DrugCharacterizationContext (descriptive, NOT scored)
├── matched_gene_hgnc_ids / matched_disease_gene_ids /
│   matched_drug_target_ids / matched_pathway_reactome_ids / generation_methods   <- graph-ready ids
├── ml_model_name / ml_model_output / ml_baseline_output   (None if ML unavailable)
├── scoring_version = "1.0"
├── provenance -> FusionProvenance
│     (feature/prediction schema versions, weight_scheme, normalization,
│      missing_evidence_policy, double_counting_policy, disclaimer)
└── interpretation   ("internal research prioritization score ... NOT clinical efficacy ...")
```

No `efficacy` / `treatment_probability` / `cure` / `recommendation` / `rank` /
`top_n` / `safety_score` field exists (enforced by test).

---

## Score bounds

`0.0 ≤ repurposing_score ≤ 100.0`, always finite. Guaranteed by: `clip01` on
every component value, a weighted mean of `[0,1]` values (⇒ `[0,1]`), and a
final `max(0, min(100, ·))` guard. Boundary cases tested (all components at 1.0
→ 100.0; all at 0.0 → 0.0; out-of-range feature inputs → still in `[0,100]`).

---

## Provenance for the future evidence graph

Every result preserves `disease_id`, `drug_id`, `matched_gene_hgnc_ids`,
`matched_disease_gene_ids`, `matched_drug_target_ids`,
`matched_pathway_reactome_ids`, `generation_methods`, and (via each component's
`supporting` + `provenance`) the source of every value. This is enough for a
later phase to draw:

```
Disease → Disease Gene → Drug Target → Pathway → Drug → ML Prediction → Repurposing Score
```

The graph itself is **not** built here.

---

## GBM example (`fuse_for_disease("Glioblastoma")`)

```
132 EvidenceFusionResults · scores 8.3 .. 84.9 · all in [0,100]
weights_configured: {gene_target: 0.45, pathway: 0.25, ml: 0.30}

regorafenib (DRUG:001322)   repurposing_score 84.9   methods [gene_target, pathway]
  gene_target  value 0.867  eff_w 0.45  -> 39.0 pts   (2+ matched HGNC genes, specificity 0.87)
  pathway      value 0.743  eff_w 0.25  -> 18.6 pts
  ml           value 0.912  eff_w 0.30  -> 27.3 pts   (model_output 0.91, baseline 0.50)
  side_effect_context: 85  (descriptive, not scored)

clobazam (DRUG:000223)      repurposing_score 15.8   methods [pathway]
  gene_target  value 0.0    ASSESSED, no overlap  -> 0.0 pts   (still weighted 0.45)
  pathway      value 0.300  -> 7.5 pts
  ml           value 0.278  -> 8.3 pts
```

Scores are derived from the real pipeline; nothing is hardcoded. A high score
means "more evidence supports investigating this candidate", **not** "this drug
treats GBM".

---

## Limitations

- **Prototype weights**, not validated against outcomes.
- Inherits every upstream limitation (SIDER∩ChEMBL targets, top-200 disease
  genes, HGNC/Reactome coverage, Phase 6's weak PU target).
- Only **3** independent evidence families exist today; more (e.g. gene-
  expression signatures, literature) would be added as new components, not by
  re-weighting the existing ones.
- The blend of count + specificity within a family, the caps (5 / 10), and the
  0.5/0.5 sub-weights are interpretable choices, not tuned.
- A single number necessarily loses information — which is why the full
  component breakdown is always returned.

---

## What Phase 8 will build

**Candidate Ranking.** Phase 8 takes the `EvidenceFusionResult`s for a disease
and produces an ordered list (and/or top-N view) for downstream AI explanation,
the evidence graph and the dashboard — using the `repurposing_score` and its
component breakdown. Phase 7 deliberately does **not** rank.
