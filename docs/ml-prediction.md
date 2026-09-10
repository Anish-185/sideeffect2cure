# Phase 6 — ML Prediction + Model Interpretability

Phase 6 owns exactly this slice of the pipeline:

```
FeatureVector[]  ->  preprocessing  ->  model  ->  PredictionResult[]
                                                   + per-prediction feature contributions
```

It does **not** compute a repurposing score, fuse evidence, rank, or generate
language. It produces a **model output over the available dataset** plus a
structured record of *which Level 5 features drove that output*, for later
phases to consume.

> **A model output is not clinical efficacy.**
> It is not the probability the drug cures the disease, not the probability a
> patient responds, and not a treatment recommendation. Neutral terms only:
> *model prediction*, *predicted probability*, *model output*.
> It is **not** a repurposing score (Phase 7).

---

## ML objective

> "Among the biologically-plausible candidates for a disease, which have the
> Level 5 feature profile of drugs that have already been taken into the
> **clinic** for that disease?"

That is a well-posed, honestly-framed classification task. It is a *filter
signal* for downstream evidence fusion — not an efficacy estimate.

---

## Training-target decision — is there a defensible label?

**Yes.** We do **not** invent labels, and we do **not** label all candidates
positive / all non-candidates negative.

| | |
|---|---|
| **source** | Open Targets Platform `disease.drugAndClinicalCandidates` (aggregates ChEMBL drug indications + ClinicalTrials.gov). Free, public. |
| **positive (1)** | the candidate drug has a **known clinical indication** for this disease — any phase, from Phase 1 to Approval |
| **negative (0)** | the candidate drug has **no** known clinical indication for this disease |
| **join key** | the drug's ChEMBL id (Level 1 crosswalk) vs the disease's clinical-candidate ChEMBL-id set |

This is **positive / unlabeled weak supervision**, stated on every model:

- a `0` means *"not currently a known clinical drug for this disease"* — **not**
  *"known to be ineffective"*. Many `0`s are exactly the repurposing hypotheses
  we want. So recall against `0`s is not "false positives" in the usual sense.
- a `1` means the drug was *tried* (or approved) — `drugAndClinicalCandidates`
  **includes failed trials** — not that it *works*.

### Why it is not circular / leaking

Candidates come from **biology** (Level 4: HGNC target overlap, Reactome pathway
overlap). Labels come from **clinical-development history** (Open Targets).
These are independent. No Level 5 feature is derived from the label.

### As-built label statistics (reference run)

```
pooled training rows : 5561   (candidates across 39 ingested diseases)
positives            : ~690   (~12.4% prevalence — imbalanced, reported everywhere)
diseases with ≥1 positive : 38 / 39   (only the rare 'familial hypercholesterolemia 1' has 0)
```

If a legitimate target had **not** existed, Phase 6 would ship the preprocessing
+ feature-matrix pipeline and a documented "no supervised target" note rather
than a fabricated classifier. It exists, so we train.

---

## Feature inputs

The **Level 5 `FeatureVector`** only — no biology is recomputed in Phase 6.

`app.services.ml.preprocessing.FEATURE_COLUMNS` is a **fixed, ordered** list of
~31 scalar Level 5 features (all of `to_feature_dict()` except the variable-key
`target_action_type_counts` / `target_type_counts` dicts, which are left out to
keep the matrix fixed-width and interpretable — `inhibitor_target_count` etc.
already carry the action-type signal — and `unique_target_count`, which is
identical to `drug_target_count` by Level 5 construction).

### Preprocessing (identical for training and inference)

| input kind | handling |
|---|---|
| numeric feature | `float64` |
| `None` fraction (zero denominator in Level 5) | → `0.0` (biologically: "no overlap possible") |
| boolean feature | → `0.0` / `1.0` |
| any residual NaN / ±inf | → `0.0` (`np.nan_to_num`) — the matrix is finite-guaranteed |
| scaling | `StandardScaler` for `logistic_regression` only; the forest uses raw values |

The exact `feature_columns`, imputation rule and seed are recorded in the model
metadata so inference reproduces training.

---

## Model choices

Classical, interpretable, **no new dependency, no deep learning**:

| model | pipeline |
|---|---|
| `logistic_regression` | `StandardScaler` → `LogisticRegression(class_weight="balanced", max_iter=2000, random_state=42)` |
| `random_forest` | `RandomForestClassifier(n_estimators=400, max_depth=6, min_samples_leaf=10, class_weight="balanced", random_state=42)` |

XGBoost / LightGBM are **not** used — they are not in `requirements.txt` and the
two sklearn baselines are sufficient for ~5.5k rows / ~31 features. `class_weight
= "balanced"` handles the ~12% prevalence.

---

## Validation strategy

**`GroupKFold(n_splits=5)` grouped by `disease_id`.**

A random split would **leak**: every candidate of a disease shares that disease's
constant features (`disease_gene_count`, `disease_pathway_count`, …) and its base
rate, so a random-split model can memorise per-disease priors. GroupKFold holds
out **whole diseases**, forcing the model to generalise the *relationship*
pattern to diseases it has never seen — the correct test for repurposing.

### Metrics (not accuracy)

Per fold: **ROC-AUC**, **PR-AUC** (`average_precision_score`), precision, recall,
F1 at threshold 0.5. Reported as mean ± std across folds, for **both** models,
alongside the **no-skill PR-AUC = positive prevalence**. Class balance is in
every `PredictionModelMetadata`.

### Selection

Highest **mean PR-AUC** (appropriate for the imbalanced target), ROC-AUC as
tie-breaker. Recorded as `selection_criterion`.

### Honest reading of the metrics

The target is weak (PU, "tried in clinic" not "works"), so metrics measure *"does
the feature profile resemble clinically-developed drugs for this disease"*, not
*"predicts efficacy"*. `PredictionModelMetadata.leakage_notes` and
`target_definition` say this on every model. Metrics are never presented without
the prevalence baseline and these caveats.

---

## Interpretability

Every `PredictionResult` carries `important_features`: the top-k Level 5 features
by absolute contribution **for that row**, each a `FeatureContribution`
(`feature_name`, `feature_value`, signed `contribution`, `direction`).

| model | global importance | per-prediction contribution |
|---|---|---|
| `logistic_regression` | \|coefficient\| | `coef_i · (x_i − mean_i) / std_i` (a log-odds term). Sum + `logit(baseline)` = `logit(model_output)`. |
| `random_forest` | `feature_importances_` | **exact decision-path contributions** ("treeinterpreter"): per tree, sum `P(class1\|child) − P(class1\|node)` along the sample's path; average over trees. Sum = `model_output − baseline`. |

No external interpretability library (no SHAP / treeinterpreter dependency) — the
forest algorithm is ~15 lines in `app.services.ml.model`. Contributions refer
**only** to real Level 5 features; no biological narrative is invented here (the
future AI layer does language).

---

## Prediction schema (`app.models.prediction`)

```
PredictionResult
├── disease_id, drug_id, disease_name, drug_name        <- preserved for the evidence graph
├── model_name, model_version, feature_schema_version, prediction_schema_version
├── model_output          float in [0,1]  (predicted probability over the dataset)
├── model_output_type     "predicted_probability"
├── baseline_output       the model's constant-feature output (base rate)
├── important_features[]  -> FeatureContribution(feature_name, feature_value, contribution, direction)
├── matched_gene_hgnc_ids / matched_drug_target_ids /
│   matched_pathway_reactome_ids / generation_methods   <- from the CandidateDrug, for graph wiring
└── model_metadata -> PredictionModelMetadata
      ├── target_definition, training_source, n_training_rows, n_training_positive,
      │   positive_prevalence, n_training_diseases, feature_columns, preprocessing,
      │   imputation, random_seed, selection_criterion, leakage_notes, disclaimer
      └── validation -> ValidationSummary(method, n_splits, group_by, positive_prevalence,
            no_skill_pr_auc, roc_auc_mean/std, pr_auc_mean/std, precision/recall/f1_mean,
            per_model{...})
```

There is **no** `repurposing_score`, `score`, `rank`, `efficacy`, `confidence`,
`recommendation` or `fusion` field anywhere (enforced by a test).

---

## Reproducibility (lightweight, local)

- `random_seed = 42` everywhere; `train(dataset)` is deterministic.
- The fitted pipeline + `feature_names` + full metadata + training mean/std are
  persisted with `joblib` to `data/models/prediction_model.joblib`
  (+ `.meta.json` for inspection). Git-ignored — regenerate with
  `python scripts/train_model.py`.
- No MLOps system, no model registry, no experiment tracker.

```bash
python scripts/train_model.py                # build dataset, CV, fit, save
python scripts/train_model.py --refresh-labels   # re-pull Open Targets clinical candidates
```

---

## Leakage considerations (summary)

1. **Disease-constant features** → handled by GroupKFold(disease_id).
2. **Label independence** → labels are clinical history, features are biology; no
   feature touches the label.
3. **`1` ≠ "works"** → the target is "entered the clinic", incl. failed trials —
   this deliberately weakens any efficacy implication.
4. **No post-prediction information** → nothing downstream (fusion, ranking, AI
   text) feeds back into features or labels.

---

## Limitations

- **Weak / PU target**: negatives are "not-yet-known", not "ineffective". The
  model learns *clinical-development resemblance*, not efficacy.
- **Small, imbalanced** dataset (~5.5k rows, ~12% positive, 39 diseases). Metrics
  carry real uncertainty (reported as ± std) — treat as directional.
- **Coverage inherited** from Levels 1-5 (SIDER∩ChEMBL targets, top-200 disease
  genes, HGNC/Reactome bridge coverage).
- The forest's max-depth/leaf constraints are chosen for interpretability and to
  limit overfitting on a small set, not tuned.
- Phase 6 output is **one number per candidate + its feature reasons**. Turning
  many evidence signals into a single defensible answer is Phase 7's job.

---

## `ML prediction ≠ repurposing score ≠ clinical efficacy`

| term | what it is | phase |
|---|---|---|
| **model prediction** | one model's output on the Level 5 features, vs a weak clinical-history target | **Phase 6 (here)** |
| **repurposing score** | a fused, calibrated score combining the model output with other evidence layers | Phase 7 |
| **clinical efficacy** | whether the drug actually helps patients — established by trials, **not produced by this system at all** | — |

---

## What Phase 7 will build

**Evidence Fusion → Repurposing Score → Ranking.** Phase 7 combines the Phase 6
`PredictionResult` with the other evidence signals (candidate-generation
reasons, feature vector, provenance) into a single calibrated **repurposing
score** per candidate and produces a **ranking**. The AI explanation layer and
graph visualisation come after that.
