# Level 1 — Biomedical Data Foundation

This document covers the eight points the Level 1 brief requires: data sources,
dataset purpose, internal schemas, identifier strategy, the processing pipeline,
how to run ingestion, how to run validation, and known limitations / licensing.

> **No biomedical values are fabricated.** Every drug, disease, target, gene,
> pathway, side effect and every relationship comes from a real public source.
> Where a source cannot be reached, the affected datasets are skipped and the
> run report says so — nothing is filled in with synthetic replacements.

### As-built snapshot (reference run)

| Table | Rows | | Entity | Count |
|---|---:|---|---|---:|
| `drugs` | 1,430 | | drugs | 1,430 |
| `diseases` | 39 | | diseases | 39 |
| `drug_targets` | 548 | | genes | 3,123 |
| `drug_side_effects` | 145,321 | | targets | 1,518 |
| `disease_genes` | 7,800 | | pathways | 1,031 |
| `disease_pathways` | 7,120 | | side effects | 4,251 |

Identifier crosswalk: 15,120 rows. Drugs mapped to a ChEMBL id: 957 / 1,430
(67%). All four sources were reachable for this run; all cross-table
data-quality checks passed. Counts will vary as ChEMBL / Open Targets / Reactome
release updates.

---

## 1. Data sources

| Source | Used for | Access | Licence |
|---|---|---|---|
| **SIDER 4.1** (sideeffects.embl.de) | drugs, drug → side effect (MedDRA PT) | static TSV files | academic / non-commercial; MedDRA terms under MSSO licence |
| **ChEMBL** (ebi.ac.uk/chembl) | drug → target (mechanism of action), target metadata | REST API (paginated JSON) | CC BY-SA 3.0 |
| **PubChem** (pubchem.ncbi.nlm.nih.gov) | PubChem CID → ChEMBL id (via compound synonyms), scoped to the SIDER drug set | PUG-REST (batched JSON) | public domain (U.S. NLM) |
| **Open Targets Platform** (platform.opentargets.org) | diseases, disease → gene associations + scores | GraphQL API v4 | CC0 |
| **Reactome** (reactome.org) | pathway names, gene → pathway (human) | flat files | CC0 |

Snapshot note: SIDER 4.1 is a frozen 2015 release; ChEMBL / Open Targets /
Reactome are pulled from their *current* release at ingest time, so counts will
drift as those releases update. The exact snapshot string is recorded in every
run report (`data/processed/_reports/ingestion.json`).

### Disease scope

Diseases are **not** harvested wholesale. The file
`backend/app/data/resources/disease_seed.tsv` lists ~38 disease ontology ids
(EFO / MONDO) spanning oncology, neurology, psychiatry, metabolic,
cardiovascular and immune/inflammatory areas, including the flagship target
**glioblastoma (`MONDO_0018177`)**. That file is an *input parameter*: edit it
to change scope. Disease names and all associations come from Open Targets.

---

## 2. Dataset purpose

Six normalized tables, written to `data/processed/` as parquet (canonical) and
CSV (inspection). They are the join surface for every later level
(candidate generation, feature engineering, evidence fusion, explainability).

| Table | Grain | Feeds (later levels) |
|---|---|---|
| `drugs` | one row per drug | candidate drug universe |
| `diseases` | one row per disease | disease resolver / disease profile |
| `drug_targets` | drug × target | mechanistic overlap with disease genes |
| `drug_side_effects` | drug × side effect | side-effect → mechanism inference, safety context |
| `disease_genes` | disease × gene | disease molecular profile |
| `disease_pathways` | disease × pathway | pathway-level disease profile |

Plus `data/mappings/identifiers.parquet` — the internal ↔ external id crosswalk.

---

## 3. Internal schemas

Defined as Pydantic models in `backend/app/data/schemas.py`. Column order below
is the on-disk order. `*_id` columns hold **internal** ids
(e.g. `DRUG:000123`); external ids are kept in dedicated columns and in the
mapping table.

**drugs**: `drug_id, drug_name, canonical_identifier, pubchem_cid, chembl_id, source`

**diseases**: `disease_id, disease_name, ontology_id, source`

**drug_targets**: `drug_id, target_id, target_name, target_type, uniprot_id, action_type, source`

**drug_side_effects**: `drug_id, side_effect_id, side_effect_name, umls_cui, meddra_id, source`

**disease_genes**: `disease_id, gene_id, gene_name, ensembl_id, association_score, source`
(`association_score` ∈ [0, 1], Open Targets overall association score)

**disease_pathways**: `disease_id, pathway_id, pathway_name, reactome_id, gene_support_count, association_score, source`
(**derived** table — see §5; `source = derived:opentargets+reactome`)

**identifiers** (mapping table): `internal_id, entity_type, external_id, external_source, name, is_primary`

---

## 4. Identifier strategy

Primary entities are keyed on a **normalized external identifier, never a name
alone**. Names are kept for display and as secondary cross-references.

| Entity | Primary key | Normalization | Secondary xrefs |
|---|---|---|---|
| drug | PubChem CID | strip STITCH `CID0/1` prefix + leading zeros | ChEMBL id, name |
| disease | EFO / MONDO id | upper-case, `:` → `_` | name |
| gene | Ensembl gene id | upper-case, drop `.version` | approved symbol |
| target | ChEMBL target id | upper-case, `CHEMBL*` check | UniProt accession |
| pathway | Reactome stable id | upper-case, `R-*` check | name |
| side effect | UMLS CUI | upper-case, `C#######` check | MedDRA PT name |

Internal ids are minted by `app.data.identifiers.IdRegistry` as
`<PREFIX>:<zero-padded counter>` (`DRUG`, `DIS`, `GENE`, `TGT`, `PATH`, `SE`).
The registry returns the same internal id for a repeated key and accumulates the
`identifiers` mapping table. External ids that cannot be normalized are **not**
silently dropped — the row is rejected with a logged reason.

Adding a new evidence layer later (LINCS, GDSC/DepMap, literature) means adding
a new source adapter + processed table that references these same internal ids —
no restructuring of existing tables.

---

## 5. Processing pipeline

Implemented in `app.data.ingest` (`run_ingestion`). Per source:

```
raw download            app.data.sources.*  ->  data/raw/<source>/
   |
validation              schema / required-field checks (app.data.validation)
   |
cleaning                strip whitespace, "" -> null
   |
identifier normalization  external ids -> canonical form (app.data.identifiers)
   |
deduplication           entities by primary key; relationships by (id, id)
   |
processed datasets      parquet + csv (app.data.writers)  ->  data/processed/
   |
data-quality checks     cross-table integrity (app.data.quality)
```

The orchestrator is **resilient**: if a source is unavailable, dependent tables
are skipped and reported; the rest still build. Dependencies:

- `drugs` ← SIDER (+ PubChem CID→ChEMBL for `chembl_id`)
- `drug_side_effects` ← SIDER + `drugs`
- `diseases`, `disease_genes` ← Open Targets
- `drug_targets` ← ChEMBL + `drugs`
- `disease_pathways` ← **derived**: `disease_genes` ⋈ Reactome gene→pathway,
  aggregated per (disease, pathway); kept only when
  `gene_support_count ≥ 3` (`DISEASE_PATHWAY_MIN_GENES`).

Every dropped or altered record is counted and categorized in the run report
(`data/processed/_reports/{ingestion,validation}.json`) and echoed to the
console. Nothing is discarded silently.

---

## 6. How to run ingestion

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..

python scripts/ingest_data.py                    # all sources, download as needed
python scripts/ingest_data.py --offline           # rebuild from existing data/raw/
python scripts/ingest_data.py --sources sider reactome
python scripts/ingest_data.py --force             # re-download raw inputs
```

Raw downloads are cached under `data/raw/`; re-runs reuse them unless `--force`.
Exit code is non-zero if a hard data-quality check fails.

---

## 7. How to run validation

```bash
python scripts/validate_data.py
```

Reads `data/processed/*.parquet` only (no network) and re-runs the checks:

- required id columns non-null / non-empty
- no duplicate primary-entity ids
- no duplicate relationships
- referential integrity (`drug_targets.drug_id ∈ drugs`, `disease_genes.disease_id ∈ diseases`, …)
- missing-value levels on optional columns (warning)

Hard failures → non-zero exit. Report written to
`data/processed/_reports/validation.json`.

---

## 8. Known limitations & licensing considerations

**Coverage / scope**

- SIDER 4.1 is from 2015; newer drugs and side effects are absent.
- Drug → target uses ChEMBL **mechanism of action** only (curated, high
  precision, ~7–8k rows) — not the full bioactivity table. Many drugs will have
  no target row.
- `disease_genes` is capped at the top `OPENTARGETS_TARGETS_PER_DISEASE` (200)
  associations per disease.
- `disease_pathways` is **derived**, not a primary source assertion. It reflects
  "pathways enriched among a disease's associated genes", not curated
  disease-pathway annotations.
- Only human data is retained from Reactome. The `Ensembl2Reactome.txt` download
  is large (~180 MB); it is cached in `data/raw/reactome/` after the first run.
- Drugs are joined to ChEMBL via PubChem-CID→ChEMBL-id (PubChem synonyms);
  ~2/3 of SIDER drugs map. Unmapped drugs keep a `CID:*` canonical identifier
  and no `chembl_id`, so they get no `drug_targets` rows. Consequently
  `drug_targets` only covers the SIDER∩ChEMBL-mechanism intersection
  (hundreds of pairs, not thousands).

**Environment / reproducibility**

- The EBI FTP-over-HTTPS endpoints (ChEMBL bulk files) can be very slow or
  flaky from some networks. Level 1 deliberately avoids the large UniChem
  whole-source mapping file in favour of scoped PubChem PUG-REST lookups for
  exactly the drugs in scope. Downloads that do happen are resumable
  (`app.data.net.download_file`) and size-verified.

**Licensing**

- **SIDER**: free for academic / non-commercial use. **MedDRA** terminology
  (side-effect names) is subject to MedDRA MSSO licensing — downstream
  redistribution may require a MedDRA subscription.
- **ChEMBL**: CC BY-SA 3.0 — attribution + share-alike.
- **Open Targets, Reactome**: CC0 1.0 (public domain).
- **PubChem**: U.S. Government work, public domain (NCBI/NLM data-usage policies apply).
- This repository does **not** commit any downloaded or derived data
  (`data/**` is git-ignored except `.gitkeep`). Each user regenerates it by
  running the ingestion script, subject to the source licences above.

**Not in Level 1** (later levels): disease resolver, disease molecular-profile
generation, candidate drug generation, feature engineering, ML, repurposing
score, evidence fusion, ranking, explainability, frontend/dashboard, knowledge
graph. LINCS / GDSC / DepMap / literature evidence layers are designed-for (add
a source adapter + table keyed on the same internal ids) but not implemented.
