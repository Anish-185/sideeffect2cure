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
│   │   ├── models/          Pydantic schemas
│   │   ├── services/        pipeline orchestration
│   │   ├── data/            dataset loaders (local files)
│   │   ├── features/        feature engineering
│   │   ├── ml/              interpretable models
│   │   └── explainability/  rationale generation
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/                React + TypeScript dashboard (not yet scaffolded)
├── data/                    raw / processed / features (git-ignored contents)
├── notebooks/
├── scripts/
├── docs/architecture.md
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

## Status

Level 0 — repository foundation only. See `docs/architecture.md` for the full
pipeline and per-level status.

## Tech stack

Python · FastAPI · pandas / numpy / scikit-learn · NetworkX · React + TypeScript
