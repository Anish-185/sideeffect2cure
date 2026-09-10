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
│   │   ├── models/          Pydantic schemas (disease.py — Level 2)
│   │   ├── services/        business logic; services/disease/ — Level 2
│   │   │                    resolver + profile builder
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
├── scripts/                ingest_data.py / validate_data.py (Level 1)
├── docs/architecture.md            canonical pipeline + level status
├── docs/data.md                    Level 1 data foundation (sources, schemas, licensing)
├── docs/disease-intelligence.md    Level 2 resolver + disease profile
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

## Status

- **Level 0** — repository foundation.
- **Level 1** — biomedical data foundation.
- **Level 2** — disease intelligence (this milestone).

See `docs/architecture.md` for the full pipeline and per-level status.

## Tech stack

Python · FastAPI · pandas / numpy / scikit-learn · NetworkX · React + TypeScript
