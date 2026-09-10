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
- Level 3+ : defined by upcoming instructions.
