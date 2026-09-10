# Architecture

SideEffect2Cure AI answers one question:

> For a given disease, which existing drugs are potentially promising candidates
> for repurposing, and **why**?

It is a **discovery / hypothesis-generation** tool. It must never claim a drug
cures a disease and must not be presented as clinical decision support.

## Canonical pipeline

```
User Disease Query
    -> Disease Resolver
    -> Disease Profile            (genes + pathways + molecular information)
    -> Candidate Drug Generation
    -> Drug Profile               (targets + side effects + mechanisms/pathways)
    -> Feature Engineering
    -> ML Prediction
    -> Evidence Fusion
    -> Candidate Ranking
    -> Explainability
    -> Dashboard
```

Optional evidence layers to integrate later: drug-induced gene-expression
signatures, drug-response evidence, literature evidence, knowledge-graph
relationships.

## Module map (`backend/app/`)

| Package          | Responsibility |
|------------------|----------------|
| `api`            | FastAPI routers, request/response wiring |
| `core`           | config, settings, disclaimers, shared constants |
| `models`         | Pydantic schemas (disease profile, drug profile, prediction, ranking) |
| `services`       | orchestration of pipeline stages |
| `data`           | dataset loading/access helpers (local CSV/parquet) |
| `features`       | feature engineering |
| `ml`             | lightweight interpretable models, train/inference |
| `explainability` | rationale generation from model output + evidence |

## Level status

- **Level 0 (done):** repository foundation, module skeleton, FastAPI app with
  `/api/health` and `/api/meta`, test harness.
- **Level 1 (done):** biomedical data foundation — see [`data.md`](data.md).
  Six normalized processed tables (`drugs`, `diseases`, `drug_targets`,
  `drug_side_effects`, `disease_genes`, `disease_pathways`) + identifier
  crosswalk, built from SIDER / ChEMBL / Open Targets / Reactome by a
  reproducible ingestion pipeline (`app.data.ingest`) with cross-table quality
  checks (`app.data.quality`).
- **Level 2 (done):** disease intelligence — see
  [`disease-intelligence.md`](disease-intelligence.md). `DiseaseResolver`
  (query → supported disease, no fuzzy matching) and the canonical
  `DiseaseProfile` (genes + pathways + provenance + deterministic summary),
  built from the Level 1 datasets. Business logic in `app.services.disease`,
  schemas in `app.models.disease`.
- **Level 3 (done):** drug intelligence — see
  [`drug-intelligence.md`](drug-intelligence.md). `DrugResolver`
  (query → supported drug; `AMBIGUOUS` for SIDER salt-name collisions) and the
  canonical `DrugProfile` (identity + side effects + targets + mechanisms +
  optional Reactome pathway context + provenance). Business logic in
  `app.services.drug`, schemas in `app.models.drug`. Optional sources chosen by
  usefulness: Reactome integrated; PubChem/UniProt reused from Level 1;
  Open Targets skipped.
- **Level 4 (done):** candidate drug generation — see
  [`candidate-generation.md`](candidate-generation.md). Two deterministic
  routes UNION-ed: **gene-target** (disease gene == drug target, joined on
  HGNC id via the HGNC complete set) and **pathway** (shared Reactome pathway,
  Level 2 disease pathways ∩ Level 3 drug pathways). Output is a
  `CandidateGenerationResult` where every candidate carries the exact
  relationship(s) that generated it — **no score, rank or probability**.
  Business logic in `app.services.candidates`, schemas in
  `app.models.candidate`.
- **Level 5 (done):** feature engineering — see
  [`feature-engineering.md`](feature-engineering.md). Turns each
  (`CandidateDrug`, `DiseaseProfile`, `DrugProfile`) into a deterministic
  `FeatureVector` — counts, documented ratios (null on zero denominator), and
  source-availability flags across generation / gene-target overlap / pathway
  overlap / side-effect / target-action / drug-structural groups. **No score,
  probability, rank, ML or fusion.** Business logic in
  `app.services.features`, schemas in `app.models.feature`.
- **Phase 6 (done):** ML prediction + interpretability — see
  [`ml-prediction.md`](ml-prediction.md). Supervised on a **real, defensible
  target** (Open Targets `drugAndClinicalCandidates` — "drug has a known
  clinical indication for this disease"; positive/unlabeled weak supervision).
  Baselines: logistic regression + random forest, **GroupKFold by disease_id**,
  selected by PR-AUC. Each `PredictionResult` carries the model output, its
  `baseline_output`, the top contributing **Level 5 features** for that row
  (exact tree-path / coefficient contributions, no SHAP dependency), and the
  ids for later graph wiring. **A model output is not a repurposing score and
  not clinical efficacy — no ranking, no fusion.** Business logic in
  `app.services.ml`, schemas in `app.models.prediction`.
- Phase 7+ : defined by upcoming instructions.
