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
    -> AI Explanation
    -> Evidence Graph           (Phase 10 — this milestone)
    -> Dashboard                (future)
    -> OCR                      (future)
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

`app.services.explanation` (Phase 9) is the AI-explanation business logic
package; `app.services.graph` (Phase 10) is the evidence-graph business logic
package; `explainability`/`ml` above are the original Level-0 placeholders
they grew out of.

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
- **Phase 7 (done):** evidence fusion + repurposing score — see
  [`evidence-fusion.md`](evidence-fusion.md). Collapses the Level 5 features
  into **3 independent evidence families** (gene-target, pathway, ML — no
  double counting), normalizes each to `[0,1]`, and combines them with an
  explicit prototype `FusionConfig` into a transparent **0-100
  `repurposing_score`** (weighted mean, weights **renormalized over available
  components** — missing evidence is never treated as negative). Every
  `EvidenceComponent` keeps its value / weight / formula / supporting data /
  provenance; side effects and drug characterization are descriptive context,
  not scored. The score is an **internal research prioritization score**, not
  clinical efficacy — **no ranking here**. Business logic in
  `app.services.fusion`, schemas in `app.models.fusion`.
- **Phase 8 (done):** candidate ranking — see
  [`candidate-ranking.md`](candidate-ranking.md). **Pure ordering** of the
  Phase 7 `EvidenceFusionResult`s: sort by `repurposing_score` descending,
  tie-break by `drug_id` ascending, assign a unique 1-based `rank`. Optional
  `top_n` presentation slice (never alters scores). Each `RankedCandidate`
  **embeds the full `EvidenceFusionResult`** — no evidence lost. No score
  recalculated, no biology touched, no new dependency. Business logic in
  `app.services.ranking`, schemas in `app.models.ranking`.
- **Phase 9 (done):** grounded AI-powered candidate explanation — see
  [`ai-explanation.md`](ai-explanation.md). `RankedCandidate` -> a compact
  `ExplanationContext` -> DeepSeek V4 Flash (via Featherless,
  OpenAI-compatible API) -> a validated `CandidateExplanation`. The LLM is an
  **explanation layer only**: every structural field (score, rank, evidence
  value/contribution/supporting ids) is built deterministically from Phase
  7/8; the model may only supply narrated prose, and only after it passes
  grounding validation (echoed identity matches, no fabricated identifiers, no
  banned clinical-claim language) — any failure falls back to a deterministic,
  template-based explanation (`DeterministicExplanationProvider`), so the
  pipeline never depends on the LLM being reachable. No new score, no
  reranking, no new biological relationships. Business logic in
  `app.services.explanation`, schemas in `app.models.explanation`.
- **Phase 10 (done):** evidence graph — see
  [`evidence-graph.md`](evidence-graph.md). A pure **representation** layer:
  turns one or an explicit top-N `RankedCandidate`s (+ the Level 4
  `CandidateDrug` each needs for its gene-target/pathway provenance, +
  optional Phase 9 `CandidateExplanation`s) into a frontend-ready
  `EvidenceGraph` (`nodes[]` + `edges[]`). Node types: disease, disease gene,
  drug, drug target, pathway, prediction, evidence component, score, rank,
  explanation — created only when the corresponding evidence actually
  exists. Every biological edge keeps the exact provenance string Level 4
  already recorded for it (`GeneTargetMatch`/`PathwayMatch` sources); no
  relationship is inferred, no score/rank is recalculated, ids are
  deterministic so identical evidence for two candidates dedups to one node.
  No graph database, no external call. Business logic in
  `app.services.graph`, schemas in `app.models.graph`.
- Phase 11+ (dashboard, OCR): defined by upcoming instructions.
