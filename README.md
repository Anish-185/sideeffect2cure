# SideEffect2Cure AI

AI-driven **drug repurposing discovery** platform.

**Core question:** for a given disease, which existing drugs are potentially
promising candidates for repurposing, and **why**?

> ⚠️ This is a research prototype. It does **not** diagnose, treat, or cure any
> disease, makes no claim that any drug cures any disease, and is **not** a
> clinical decision-support system. All output is hypothesis-generating only.

## Repository layout

```
sideeffect2cure/
├── backend/
│   ├── app/
│   │   ├── api/             FastAPI routers
│   │   ├── core/            config, disclaimers
│   │   ├── models/          schemas (disease L2, drug L3, candidate L4,
│   │   │                    feature L5, prediction P6)
│   │   ├── services/        business logic; disease/ (L2) drug/ (L3)
│   │   │                    candidates/ (L4) features/ (L5) ml/ (P6)
│   │   ├── data/            biomedical data foundation (Level 1): sources,
│   │   │                    schemas, identifier normalization, ingestion
│   │   ├── features/        feature engineering
│   │   ├── ml/              interpretable models
│   │   └── explainability/  rationale generation
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/                React + TypeScript dashboard (not yet scaffolded)
├── data/                    raw / processed / features (git-ignored contents)
├── notebooks/
├── scripts/                ingest_data.py, validate_data.py (L1), train_model.py (P6)
├── docs/architecture.md            canonical pipeline + level status
├── docs/data.md                    Level 1 data foundation (sources, schemas, licensing)
├── docs/disease-intelligence.md    Level 2 resolver + disease profile
├── docs/drug-intelligence.md       Level 3 resolver + drug profile
├── docs/candidate-generation.md    Level 4 candidate drug generation
├── docs/feature-engineering.md     Level 5 disease-drug feature vectors
├── docs/ml-prediction.md           Phase 6 ML prediction + interpretability
└── README.md
```

## Backend quickstart

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
pytest                             # run tests
```

## Data foundation (Level 1)

Builds six normalized tables (`drugs`, `diseases`, `drug_targets`,
`drug_side_effects`, `disease_genes`, `disease_pathways`) from real public
sources — SIDER, ChEMBL, Open Targets, Reactome — plus an internal↔external
identifier crosswalk. Nothing is fabricated; unreachable sources are reported,
not faked.

```bash
python scripts/ingest_data.py       # download + normalize -> data/processed/
python scripts/validate_data.py     # cross-table data-quality checks
```

Downloaded and generated data under `data/**` is git-ignored — regenerate it
with the script. Full details, schemas and licensing: **`docs/data.md`**.

## Disease intelligence (Level 2)

Resolves a disease name / id / ontology id / alias to a canonical
`DiseaseProfile` (associated genes + derived pathways + provenance + a
deterministic summary). No fuzzy matching — unknown queries return an explicit
"not supported" result.

```python
from app.services.disease import build_disease_profile
p = build_disease_profile("Glioblastoma")   # or "GBM", "MONDO_0018177"
[g.gene_name for g in p.genes[:5]]           # ['TP53', 'IDH1', 'EGFR', 'PTEN', 'BRAF']
```

Details: **`docs/disease-intelligence.md`**.

## Drug intelligence (Level 3)

Resolves a drug name / internal id / ChEMBL id / PubChem CID to a canonical
`DrugProfile` (side effects + targets + mechanisms + optional Reactome pathway
context + provenance). SIDER salt-name collisions return `AMBIGUOUS`, never a
guess.

```python
from app.services.drug import build_drug_profile
p = build_drug_profile("Aspirin")            # or "CHEMBL25", "2244", "DRUG:000124"
[(t.target_name, t.action_type) for t in p.targets]   # [('Cyclooxygenase', 'INHIBITOR')]
```

Optional sources are chosen by usefulness, not completeness — only Reactome was
integrated. Details: **`docs/drug-intelligence.md`**.

## Candidate generation (Level 4)

Reduces the 1,430-drug universe to the drugs biologically connected to a
disease, via two deterministic routes UNION-ed: **gene-target** (disease gene ==
drug target, joined on HGNC id) and **pathway** (shared Reactome pathway). Every
candidate keeps the exact relationship(s) that generated it. No score or rank.

```python
from app.services.disease import build_disease_profile
from app.services.candidates import generate_candidates
res = generate_candidates(build_disease_profile("Glioblastoma"))
res.candidate_count            # 132  (of 1430)
res.counts_by_method           # {'gene_target': 19, 'pathway': 131, 'both': 18, ...}
```

Details: **`docs/candidate-generation.md`**.

## Feature engineering (Level 5)

Turns each `(CandidateDrug, DiseaseProfile, DrugProfile)` into a deterministic
`FeatureVector` — counts, documented ratios (null on zero denominator), and
source-availability flags. No score, probability, ranking, ML, or fusion.

```python
from app.services.features import build_feature_vectors
vectors = build_feature_vectors(disease_profile, candidates)   # one per candidate
vectors[0].to_feature_dict()   # flat {name: number|bool|None} for Level 6
```

Details: **`docs/feature-engineering.md`**.

## ML prediction + interpretability (Phase 6)

Trains a small interpretable classifier (logistic regression / random forest,
GroupKFold by disease) on a **real** target — whether a candidate drug has a
known clinical indication for the disease (Open Targets, positive/unlabeled).
Each `PredictionResult` carries the model output, its baseline, and the top
contributing **Level 5 features** for that prediction.

```bash
python scripts/train_model.py        # build dataset, cross-validate, fit, save
```
```python
from app.services.ml import predict_for_disease
results = predict_for_disease("Glioblastoma")   # list[PredictionResult]
results[0].model_output, results[0].important_features
```

A model output is **not** a repurposing score and **not** clinical efficacy —
no ranking, no fusion. Details: **`docs/ml-prediction.md`**.

## Status

- **Level 0** — repository foundation.
- **Level 1** — biomedical data foundation.
- **Level 2** — disease intelligence.
- **Level 3** — drug intelligence.
- **Level 4** — candidate drug generation.
- **Level 5** — feature engineering.
- **Phase 6** — ML prediction + interpretability (this milestone).

See `docs/architecture.md` for the full pipeline and per-level status.

## Tech stack

Python · FastAPI · pandas / numpy / scikit-learn · NetworkX · React + TypeScript
